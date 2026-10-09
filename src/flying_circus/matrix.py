import argparse
import json
import math
import os
import platform
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import export, runtimes, startup, warm
from .bench import digest


def default_output():
    if sys.platform == 'darwin':
        base = Path.home() / 'Library/Application Support'
    elif sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local'))
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    return base / 'flying-circus/results' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8])


def main(argv=None):
    parser = argparse.ArgumentParser(description='Compare application performance across Monty, CPython and PyPy binaries')
    parser.add_argument('-r', '--runtime', action='append', required=True, metavar='[LABEL=]EXECUTABLE',
                        help='Repeat for each runtime; executables may be on PATH. First runtime is the diff reference.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show benchmark progress, individual measurements and results')
    parser.add_argument('--diff', action='store_true', help='Show meaningful differences, failures and compatibility changes')
    parser.add_argument('--output', type=Path, help='New result directory; defaults to the user application-data directory')
    parser.add_argument('--format', choices=('html', 'markdown', 'json'), action='append',
                        help='Report format; repeat to write multiple formats (default: html)')
    parser.add_argument('--quick', action='store_true',
                        help='Quick full-suite run: 3 timing samples, 5 startup samples, 1 warmup and 1 RSS sample; explicit counts override these defaults')
    parser.add_argument('--samples', type=int, help='Timing samples per workload, runtime and scenario (default: 20; quick: 3)')
    parser.add_argument('--memory-samples', type=int, help='Separate RSS samples (default: 3, or 10 with --diff; quick: 1)')
    parser.add_argument('--startup-samples', type=int, help='Empty-command startup samples per runtime (default: 50; quick: 5)')
    parser.add_argument('--warmups', type=int, help='Untimed requests per workload for repeated measurements (default: 3; quick: 1)')
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--threshold', type=float, default=5, help='Minimum percentage change shown by --diff')
    parser.add_argument('--absolute-threshold-ms', type=float, default=0.01)
    args = parser.parse_args(argv)
    for name, standard, quick in (('samples', 20, 3), ('startup_samples', 50, 5), ('warmups', 3, 1)):
        if getattr(args, name) is None:
            setattr(args, name, quick if args.quick else standard)
    if args.diff and len(args.runtime) < 2:
        parser.error('--diff requires at least two runtimes')
    if args.memory_samples is None:
        args.memory_samples = 0 if sys.platform not in ('linux', 'darwin') else (1 if args.quick else (10 if args.diff else 3))
    if args.samples < 2 or args.startup_samples < 2 or args.warmups < 0 or args.memory_samples < 0:
        parser.error('samples and startup-samples must be >= 2; warmups and memory-samples must be >= 0')
    if any(not math.isfinite(v) or v < 0 for v in (args.threshold, args.absolute_threshold_ms)) or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('thresholds must be finite and nonnegative; timeout must be finite and positive')
    if args.memory_samples and sys.platform not in ('linux', 'darwin'):
        parser.error('RSS collection supports Linux and macOS; use --memory-samples 0')
    output = (args.output or default_output()).expanduser().resolve()
    if output.exists():
        parser.error('output directory already exists')
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        resolved = runtimes.resolve_all(args.runtime, args.timeout)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.error(str(error))
    output.mkdir(parents=True)
    if args.quick:
        print('Quick run: reduced sampling for a rough comparison; repeat with default settings to confirm changes.', flush=True)
    if args.diff and args.samples < 10:
        print('Diff needs at least 10 timing samples per runtime to classify meaningful changes; smaller runs report them as inconclusive.', flush=True)
    index = {'runtimes': resolved, 'timestamp': started_at, 'options': vars(args)}
    (output / 'run.json').write_text(json.dumps(index, indent=2, default=str) + '\n')
    failed = False
    runs = {key: {'configuration': {'binary': str(runtime['binary']), 'legacy_cli_summary': runtime['legacy_cli_summary']},
                  'binary_sha256': digest(runtime['binary']), 'revision': runtime['revision'], 'runtime_label': runtime['label'],
                  'machine': platform.node(), 'platform': platform.platform(), 'architecture': platform.machine()}
            for key, runtime in resolved.items()}
    print('Measuring empty-command startup', flush=True)
    timings = startup.measure(runs, args.startup_samples, args.timeout, tolerate_errors=True, verbose=args.verbose)
    (output / 'startup.json').write_text(json.dumps(timings, indent=2) + '\n')
    failed |= any(entry['errors'] for entry in timings['engines'].values())
    for mode, scenario in (('one-shot', 'warm_worker_one_shot'), ('repeated', 'repeated_requests')):
        print(f'Running {mode}: {", ".join(runtime["label"] for runtime in resolved.values())}', flush=True)
        failed |= bool(warm.main(['--suite', 'all', '--scenario', scenario, '--samples', str(args.samples),
                                  '--warmups', str(args.warmups if mode == 'repeated' else 0),
                                  '--memory-samples', str(args.memory_samples if mode == 'one-shot' else 0),
                                  '--timeout', str(args.timeout), '--output', str(output / mode)] + (['--verbose'] if args.verbose else []), runtimes=resolved))
    index['completed_at'] = datetime.now(timezone.utc).isoformat()
    index['elapsed_seconds'] = time.perf_counter() - started
    (output / 'run.json').write_text(json.dumps(index, indent=2, default=str) + '\n')
    paths, changes = export.write_reports(output, args.format or ['html'], args.diff, args.threshold, args.absolute_threshold_ms)
    if changes is not None:
        for status in ('regression', 'improvement', 'inconclusive', 'failure', 'compatibility change'):
            print(f'{status}: {sum(row["status"] == status for row in changes)}')
    for path in paths:
        print(f'Report: {path}')
    return int(bool(failed))
