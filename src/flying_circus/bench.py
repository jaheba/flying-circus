import argparse
import hashlib
import json
import math
import platform
import random
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .compatibility import probe_workload, select_workloads
from .workers import CPythonWorker, MontyWorker

ROOT = Path(__file__).resolve().parent


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def validate(result, expected, legacy):
    if result.returncode:
        raise RuntimeError(f'exit {result.returncode}: {result.stderr}')
    output = result.stdout
    if legacy:
        output = re.sub(r'(?m)^\d+(?:\.\d+)?(?:ns|µs|μs|us|ms|s) ❯ None\n?\Z', '', output)
    if output != expected:
        raise ValueError(f'Expected {expected!r}, received {output!r}; stderr: {result.stderr}')


def memory_sample(command, timeout):
    result = subprocess.run(
        [sys.executable, '-m', 'flying_circus.memory', str(timeout), *command],
        capture_output=True, text=True, timeout=timeout + 5, check=True,
    )
    return json.loads(result.stdout)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Black-box Monty application benchmarks')
    parser.add_argument('--monty', '--binary', dest='monty', type=Path, required=True,
                        help='Monty binary or CPython executable')
    parser.add_argument('--revision', required=True)
    parser.add_argument('--engine', choices=('monty', 'cpython', 'pypy'), default='monty')
    parser.add_argument('--suite', choices=('applications', 'benchmark_game', 'pyperformance', 'text', 'all'), default='applications')
    parser.add_argument('--build-info', default='', help='Compiler, profile and build flags')
    parser.add_argument('--samples', type=int, default=20)
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--memory-samples', type=int, default=3)
    parser.add_argument('--workload', action='append', help='Workload name; repeat to select several')
    parser.add_argument('--legacy-cli-summary', action='store_true', help='Strip old CLI stdout timing summary')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.samples < 2 or args.memory_samples < 0 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('samples >= 2, memory-samples >= 0 and finite timeout > 0 required')
    if args.output.exists():
        parser.error('output already exists')
    if args.memory_samples and sys.platform not in ('linux', 'darwin'):
        parser.error('peak RSS accounting supports Linux/macOS; use --memory-samples 0 elsewhere')
    binary = args.monty.resolve(strict=True)
    manifest_path = ROOT / 'workloads' / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    try:
        selected = select_workloads(manifest, args.suite, args.workload)
    except ValueError as error:
        parser.error(str(error))
    records = {}
    commands = {}
    for name in dict.fromkeys(selected):
        spec = manifest[name]
        source = ROOT / 'workloads' / spec['file']
        commands[name] = [str(binary), str(source)]
        records[name] = {
            'scenario': 'fresh_process', 'upstream': spec.get('upstream'), 'workload_sha256': digest(source),
            'expected_sha256': hashlib.sha256(spec['stdout'].encode()).hexdigest(),
            'wall_seconds': [], 'peak_rss_bytes': [], 'errors': [],
        }
    for name, record in records.items():
        spec = manifest[name]
        if spec.get('compatibility_probe'):
            cls = MontyWorker if args.engine == 'monty' else CPythonWorker
            source = ROOT / 'workloads' / spec['file']
            check = probe_workload(cls, binary, args.timeout, source.read_text(), spec['file'], spec['stdout'],
                                   spec.get('known_missing', ()))
            record['compatibility'] = check
            if check['status'] == 'failed':
                record['errors'].append({'phase': 'compatibility', 'message': check['reason']})

    def supported(record):
        return record.get('compatibility', {}).get('status', 'supported') == 'supported'

    seed = 0
    schedule = list(records) * args.samples
    random.Random(seed).shuffle(schedule)
    started = datetime.now(timezone.utc).isoformat()
    for name in schedule:
        if not supported(records[name]):
            continue
        start = time.perf_counter_ns()
        try:
            result = subprocess.run(commands[name], capture_output=True, text=True, timeout=args.timeout)
            elapsed = (time.perf_counter_ns() - start) / 1e9
            validate(result, manifest[name]['stdout'], args.legacy_cli_summary)
            records[name]['wall_seconds'].append(elapsed)
        except (subprocess.TimeoutExpired, ValueError, RuntimeError) as error:
            records[name]['errors'].append({'phase': 'latency', 'message': str(error)})
    for name, record in records.items():
        for _ in range(args.memory_samples if supported(record) else 0):
            try:
                sample = memory_sample(commands[name], args.timeout)
                validate(subprocess.CompletedProcess(commands[name], sample['returncode'], sample['stdout'], sample['stderr']),
                         manifest[name]['stdout'], args.legacy_cli_summary)
                record['peak_rss_bytes'].append(sample['peak_rss_bytes'])
            except (subprocess.SubprocessError, ValueError, RuntimeError) as error:
                record['errors'].append({'phase': 'memory', 'message': str(error)})
        values = record['wall_seconds']
        if record.get('compatibility', {}).get('status') == 'unsupported':
            record['status'] = 'unsupported'
        else:
            record['status'] = 'failed' if record['errors'] else 'ok'
        record['median_wall_seconds'] = statistics.median(values) if values else None
        record['stdev_wall_seconds'] = statistics.stdev(values) if len(values) > 1 else None
        record['median_peak_rss_bytes'] = statistics.median(record['peak_rss_bytes']) if record['peak_rss_bytes'] else None
        print(f"{name}: {record['status']}, median={record['median_wall_seconds']} s")
    output = {
        'schema_version': 1, 'engine': args.engine, 'revision': args.revision, 'build_info': args.build_info,
        'binary_sha256': digest(binary), 'manifest_sha256': digest(manifest_path),
        'harness_sha256': hashlib.sha256(''.join(digest(ROOT / name) for name in
            ('bench.py', 'compatibility.py', 'workers.py', 'cpython_worker.py')).encode()).hexdigest(), 'memory_helper_sha256': digest(ROOT / 'memory.py'),
        'timestamp': started, 'machine': platform.node(), 'platform': platform.platform(),
        'architecture': platform.machine(), 'harness_python': platform.python_version(),
        'configuration': vars(args) | {'monty': str(binary), 'output': str(args.output)},
        'schedule_seed': seed, 'schedule': schedule, 'memory_method': 'RUSAGE_CHILDREN.ru_maxrss' if args.memory_samples else None,
        'benchmarks': records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as destination:
        json.dump(output, destination, indent=2)
        destination.write('\n')
    return int(any(record['errors'] for record in records.values()))


if __name__ == '__main__':
    sys.exit(main())
