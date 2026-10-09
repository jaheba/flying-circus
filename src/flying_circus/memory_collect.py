import argparse
import hashlib
import json
import math
import platform
from datetime import datetime, timezone
import statistics
import subprocess
import sys
from pathlib import Path

METHOD = 'RUSAGE_CHILDREN.ru_maxrss'


def helper_hash(root):
    return hashlib.sha256(b''.join((root / name).read_bytes() for name in
                                 ('memory.py', 'worker_memory.py', 'memory_collect.py', 'workers.py', 'workload_source.py'))).hexdigest()


def collect(binary, engine, scenario, source, expected, timeout, legacy=False):
    from .bench import memory_sample, validate

    if scenario in ('cold_process_one_shot', 'fresh_process'):
        sample = memory_sample([str(binary), str(source)], timeout)
        validate(subprocess.CompletedProcess([], sample['returncode'], sample['stdout'], sample['stderr']), expected, legacy)
    elif scenario == 'warm_worker_one_shot':
        request = {'engine': engine, 'binary': str(binary), 'code': source.read_text(),
                   'filename': source.name, 'timeout': timeout}
        result = subprocess.run([sys.executable, '-m', 'flying_circus.worker_memory'],
                                input=json.dumps(request), capture_output=True, text=True,
                                timeout=timeout * 3 + 5, check=True)
        sample = json.loads(result.stdout)
        if sample['stdout'] != expected or sample['stderr']:
            raise ValueError('Memory sample output mismatch')
    else:
        raise ValueError('Memory collection supports one-shot scenarios only')
    return sample['peak_rss_bytes']


def main(argv=None):
    from .bench import ROOT, digest

    parser = argparse.ArgumentParser(description='Add separate peak-RSS samples to existing one-shot results')
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='New directory; original results are preserved')
    parser.add_argument('--samples', type=int, default=3)
    parser.add_argument('--timeout', type=float, default=30)
    args = parser.parse_args(argv)
    if sys.platform not in ('linux', 'darwin'):
        parser.error('Peak RSS accounting supports Linux and macOS')
    if args.samples < 1 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('Positive samples and timeout required')
    if args.output.exists():
        parser.error('Output directory already exists')
    manifest = json.loads((ROOT / 'workloads/manifest.json').read_text())
    runs = {}
    for engine in ('monty', 'candidate', 'cpython', 'pypy'):
        path = args.directory / f'{engine}.json'
        if not path.exists():
            continue
        run = json.loads(path.read_text())
        if run['schema_version'] != 1:
            parser.error('Unsupported result schema')
        if (run['machine'], run['platform'], run['architecture']) != (platform.node(), platform.platform(), platform.machine()):
            parser.error(f'{engine}: memory must be collected on the original machine and OS')
        binary = Path(run['configuration'].get('binary', run['configuration'].get('monty', '')))
        if digest(binary) != run['binary_sha256']:
            parser.error(f'{engine}: binary changed since latency collection')
        for name, record in run['benchmarks'].items():
            spec = manifest[name]
            if digest(ROOT / 'workloads' / spec['file']) != record['workload_sha256']:
                parser.error(f'{name}: workload changed since latency collection')
            if hashlib.sha256(spec['stdout'].encode()).hexdigest() != record['expected_sha256']:
                parser.error(f'{name}: expected output changed since latency collection')
            if record['scenario'] not in ('warm_worker_one_shot', 'cold_process_one_shot', 'fresh_process'):
                parser.error('Memory collection supports one-shot scenarios only')
        runs[engine] = (run, binary)
    if not runs:
        parser.error('No engine result files found')
    failed = False
    args.output.mkdir(parents=True)
    for engine, (run, binary) in runs.items():
        run['memory_collected_at'] = datetime.now(timezone.utc).isoformat()
        run['memory_method'] = METHOD
        run['memory_helper_sha256'] = helper_hash(ROOT)
        run['configuration']['memory_samples'] = args.samples
        for name, record in run['benchmarks'].items():
            if record['status'] != 'ok':
                continue
            spec = manifest[name]
            values = []
            try:
                for _ in range(args.samples):
                    values.append(collect(binary, run.get('engine', engine), record['scenario'], ROOT / 'workloads' / spec['file'],
                                          spec['stdout'], args.timeout,
                                          run['configuration'].get('legacy_cli_summary', False)))
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                record.setdefault('errors', []).append({'phase': 'memory', 'message': str(error)})
                record['status'] = 'failed'
                failed = True
            record['peak_rss_bytes'] = values
            record['median_peak_rss_bytes'] = statistics.median(values) if values else None
            record['memory_scope'] = 'Whole interpreter process, including startup, in separate one-shot runs'
            print(f"{engine}/{name}: peak RSS {record['median_peak_rss_bytes']} bytes", flush=True)
        with (args.output / f'{engine}.json').open('x') as destination:
            json.dump(run, destination, indent=2)
            destination.write('\n')
    return int(failed)
