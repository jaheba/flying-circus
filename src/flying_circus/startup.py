import argparse
import json
import math
import platform
import random
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .bench import digest, validate
from .machine import cpu_info


def measure(runs, samples, timeout, tolerate_errors=False, verbose=False):
    schedule = list(runs) * samples
    random.Random(0).shuffle(schedule)
    results = {}
    for engine, run in runs.items():
        binary = Path(run['configuration']['binary']).resolve(strict=True)
        if digest(binary) != run['binary_sha256']:
            raise ValueError(f'{engine}: binary changed since application measurements')
        for field, current in (('machine', platform.node()), ('platform', platform.platform()),
                               ('architecture', platform.machine())):
            if run[field] != current:
                raise ValueError(f'{engine}: startup must be measured on the application benchmark host')
        results[engine] = {'binary_sha256': run['binary_sha256'], 'revision': run['revision'],
                           'command': [str(binary), *run['configuration'].get('arguments', []), '-c', ''], 'wall_seconds': [], 'errors': []}
    for engine in schedule:
        record = results[engine]
        if record['errors']:
            continue
        label = runs[engine].get('runtime_label', engine)
        if verbose:
            print(f'{label}: startup sample {len(record["wall_seconds"]) + 1}/{samples}', flush=True)
        try:
            started = time.perf_counter_ns()
            result = subprocess.run(record['command'], capture_output=True, text=True, timeout=timeout)
            elapsed = (time.perf_counter_ns() - started) / 1e9
            validate(result, '', runs[engine]['configuration'].get('legacy_cli_summary', False))
            record['wall_seconds'].append(elapsed)
            if verbose:
                print(f'{label}: startup {elapsed * 1000:.3g} ms', flush=True)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            if not tolerate_errors:
                raise
            record['errors'].append(str(error))
            print(f'{label}: startup failed: {error}', file=sys.stderr, flush=True)
    for record in results.values():
        record['median_wall_seconds'] = statistics.median(record['wall_seconds']) if record['wall_seconds'] else None
    return {'schema_version': 1, 'scenario': 'empty_command_process', 'samples': samples,
            'timestamp': datetime.now(timezone.utc).isoformat(), 'machine': platform.node(),
            'platform': platform.platform(), 'architecture': platform.machine(), 'cpu': cpu_info(),
            'scope': 'Fresh process launch through exit; empty -c command; no shell; normal interpreter defaults',
            'engines': results}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Measure empty-command process startup separately')
    parser.add_argument('directory', type=Path, help='Application result directory, or its parent containing one-shot/')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=50)
    parser.add_argument('--timeout', type=float, default=30)
    args = parser.parse_args(argv)
    if args.samples < 2 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('samples >= 2 and finite timeout > 0 required')
    if args.output.exists():
        parser.error('output already exists')
    folder = args.directory / 'one-shot' if (args.directory / 'one-shot').is_dir() else args.directory
    runs = {path.stem: json.loads(path.read_text()) for path in folder.glob('*.json')
            if path.stem in ('monty', 'cpython', 'pypy', 'candidate')}
    if not runs:
        parser.error('No interpreter result files found')
    try:
        result = measure(runs, args.samples, args.timeout)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as destination:
        json.dump(result, destination, indent=2)
        destination.write('\n')
