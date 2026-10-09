import argparse
import hashlib
import json
import math
import platform
import random
import statistics
import subprocess
import sys
import time
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

from .bench import ROOT, digest, validate
from .compatibility import probe_workload, select_workloads
from .workload_source import split_source, prepare
from .machine import cpu_info
from .memory_collect import METHOD, collect, helper_hash
from .workers import CPythonWorker, MontyWorker, PROTOCOL_VERSION


def one_shot_worker(cls, binary, timeout, code, filename, setup=""):
    started = time.perf_counter_ns()
    with cls(binary, timeout) as worker:
        worker.ready()
        ready = time.perf_counter_ns()
        worker.configure(filename)
        prepare(worker, setup, filename)
        configured = time.perf_counter_ns()
        stdout, stderr = worker.run(code, filename)
        completed = time.perf_counter_ns()
    return stdout, stderr, (completed - configured) / 1e9, (configured - ready) / 1e9, (ready - started) / 1e9


def main(argv=None, runtimes=None):
    parser = argparse.ArgumentParser(description='Compare one-shot and repeated applications on Monty, CPython and optional PyPy')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('--monty', type=Path, required=runtimes is None)
    parser.add_argument('--cpython', type=Path)
    parser.add_argument('--candidate', type=Path, help='Compare a second Monty binary instead of CPython')
    parser.add_argument('--candidate-revision', default='candidate')
    parser.add_argument('--candidate-build-info', default='')
    parser.add_argument('--pypy', type=Path)
    parser.add_argument('--pypy-revision')
    parser.add_argument('--pypy-build-info', default='')
    parser.add_argument('--monty-revision', required=runtimes is None)
    parser.add_argument('--cpython-revision', default='unverified-local')
    parser.add_argument('--monty-build-info', default='')
    parser.add_argument('--cpython-build-info', default='')
    parser.add_argument('--samples', type=int, default=20)
    parser.add_argument('--memory-samples', type=int)
    parser.add_argument('--scenario', choices=('cold_process_one_shot', 'warm_worker_one_shot', 'repeated_requests'),
                        default='warm_worker_one_shot')
    parser.add_argument('--warmups', type=int)
    parser.add_argument('--legacy-cli-summary', action='store_true', help='Strip old Monty CLI stdout summary in cold runs')
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--workload', action='append')
    parser.add_argument('--suite', choices=('applications', 'benchmark_game', 'pyperformance', 'text', 'memory', 'all'), default='applications')
    parser.add_argument('--output', type=Path, required=True, help='New directory for per-engine result files')
    args = parser.parse_args(argv)
    if runtimes is None and bool(args.cpython) == bool(args.candidate):
        parser.error('Provide exactly one of --cpython or --candidate')
    if args.candidate and args.pypy:
        parser.error('--candidate cannot be combined with --pypy')
    if args.memory_samples is None:
        args.memory_samples = 0 if args.scenario == 'repeated_requests' or sys.platform not in ('linux', 'darwin') else 3
    if args.memory_samples < 0:
        parser.error('memory-samples must be nonnegative')
    if args.memory_samples and (args.scenario == 'repeated_requests' or sys.platform not in ('linux', 'darwin')):
        parser.error('Peak RSS collection supports one-shot scenarios on Linux/macOS')
    if args.warmups is None:
        args.warmups = 1 if args.scenario == 'repeated_requests' else 0
    if args.scenario != 'repeated_requests' and args.warmups:
        parser.error('one-shot scenarios do not allow workload warmups')
    if args.samples < 2 or args.warmups < 0 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('samples >= 2, warmups >= 0 and finite timeout > 0 required')
    if args.pypy and not args.pypy_revision:
        parser.error('--pypy-revision is required with --pypy')
    if args.pypy_revision and not args.pypy:
        parser.error('--pypy is required with --pypy-revision')
    if args.output.exists():
        parser.error('output directory already exists')
    manifest = json.loads((ROOT / 'workloads/manifest.json').read_text())
    try:
        names = select_workloads(manifest, args.suite, args.workload)
    except ValueError as error:
        parser.error(str(error))
    sources = {name: (ROOT / 'workloads' / manifest[name]['file']).read_text() for name in names}
    setups = {name: split_source(source)[0] for name, source in sources.items()}
    code = {name: split_source(source)[1] for name, source in sources.items()}
    if runtimes is None:
        runtimes = {'monty': {'binary': args.monty, 'engine': 'monty',
                             'revision': args.monty_revision, 'build_info': args.monty_build_info}}
        other = 'candidate' if args.candidate else 'cpython'
        for engine in [other] + (['pypy'] if args.pypy else []):
            runtimes[engine] = {'binary': getattr(args, engine), 'engine': 'monty' if engine == 'candidate' else engine,
                               'revision': getattr(args, engine + '_revision'),
                               'build_info': getattr(args, engine + '_build_info')}
    binaries = {key: Path(runtime['binary']).resolve(strict=True) for key, runtime in runtimes.items()}
    labels = {key: runtime.get('label', key) for key, runtime in runtimes.items()}
    def log(message):
        if args.verbose:
            print(message, flush=True)

    engine_types = {key: runtime['engine'] for key, runtime in runtimes.items()}
    def legacy(key):
        return runtimes[key].get('legacy_cli_summary', args.legacy_cli_summary) and engine_types[key] == 'monty'
    schedule = [(engine, name) for engine in binaries for name in names] * args.samples
    random.Random(0).shuffle(schedule)
    harness_files = ['warm.py', 'compatibility.py', 'workers.py', 'cpython_worker.py', 'protocol/monty_pb2.py', 'workload_source.py']
    harness_hash = hashlib.sha256(''.join(digest(ROOT / name) for name in harness_files).encode()).hexdigest()
    cpu = cpu_info()
    results = {}
    for engine, binary in binaries.items():
        results[engine] = {
            'schema_version': 1, 'revision': runtimes[engine]['revision'], 'runtime_label': runtimes[engine].get('label', engine),
            'build_info': runtimes[engine]['build_info'], 'engine': engine_types[engine],
            'runtime_version': runtimes[engine].get('version', runtimes[engine]['revision']),
            'binary_sha256': digest(binary), 'manifest_sha256': digest(ROOT / 'workloads/manifest.json'),
            'harness_sha256': harness_hash, 'memory_helper_sha256': helper_hash(ROOT),
            'timestamp': datetime.now(timezone.utc).isoformat(), 'machine': platform.node(),
            'cpu': cpu, 'platform': platform.platform(), 'architecture': platform.machine(),
            'harness_python': platform.python_version(), 'memory_method': METHOD if args.memory_samples else None,
            'protocol_version': PROTOCOL_VERSION if engine_types[engine] == 'monty' else None,
            'configuration': {'samples': args.samples, 'memory_samples': args.memory_samples, 'warmups': args.warmups, 'timeout': args.timeout,
                              'legacy_cli_summary': legacy(engine),
                              'scenario': args.scenario, 'suite': args.suite, 'binary': str(binary)},
            'schedule_seed': 0, 'schedule': schedule, 'benchmarks': {},
        }
        for name in names:
            results[engine]['benchmarks'][name] = {
                'source_file': manifest[name]['file'], 'input_bytes': manifest[name].get('input_bytes'), 'fixture_sha256': manifest[name].get('fixture_sha256'),
                'fixture_setup': 'outside request timing' if setups[name] and args.scenario != 'cold_process_one_shot' else 'included in process timing',
                'scenario': args.scenario, 'upstream': manifest[name].get('upstream'),
                'workload_sha256': digest(ROOT / 'workloads' / manifest[name]['file']),
                'expected_sha256': hashlib.sha256(manifest[name]['stdout'].encode()).hexdigest(),
                'wall_seconds': [], 'worker_ready_seconds': [], 'warmup_wall_seconds': [], 'session_setup_seconds': [], 'session_reset_seconds': [],
                'peak_rss_bytes': [], 'median_peak_rss_bytes': None, 'errors': [],
            }

    for engine, binary in binaries.items():
        cls = MontyWorker if engine_types[engine] == 'monty' else CPythonWorker
        for name in names:
            spec = manifest[name]
            if not spec.get('compatibility_probe'):
                continue
            log(f'{labels[engine]}/{name}: checking compatibility')
            check = probe_workload(cls, binary, args.timeout, sources[name], spec['file'], spec['stdout'],
                                   spec.get('known_missing', ()))
            record = results[engine]['benchmarks'][name]
            record['compatibility'] = check
            if check['status'] == 'failed':
                record['errors'].append(check['reason'])
            log(f"{labels[engine]}/{name}: {check['status']} {check['reason']}")

    def supported(engine, name):
        check = results[engine]['benchmarks'][name].get('compatibility')
        return not results[engine]['benchmarks'][name]['errors'] and (check is None or check['status'] == 'supported')

    def execute(worker, name):
        start = time.perf_counter_ns()
        worker.configure(manifest[name]['file'])
        prepare(worker, setups[name], manifest[name]['file'])
        configured = time.perf_counter_ns()
        stdout, stderr = worker.run(code[name], manifest[name]['file'])
        completed = time.perf_counter_ns()
        if stdout != manifest[name]['stdout'] or stderr:
            raise ValueError(f'{name}: unexpected output: stdout={stdout!r}, stderr={stderr!r}')
        reset_start = time.perf_counter_ns()
        worker.reset()
        reset_end = time.perf_counter_ns()
        return ((completed - configured) / 1e9, (configured - start) / 1e9,
                (reset_end - reset_start) / 1e9)

    failure = None
    with ExitStack() as stack:
        workers = {}
        try:
            for engine in binaries if args.scenario == 'repeated_requests' else ():
                cls = MontyWorker if engine_types[engine] == 'monty' else CPythonWorker
                start = time.perf_counter_ns()
                worker = stack.enter_context(cls(binaries[engine], args.timeout))
                worker.ready()
                results[engine]['worker_ready_seconds'] = (time.perf_counter_ns() - start) / 1e9
                workers[engine] = worker
            for warmup in range(1, args.warmups + 1):
                for engine in workers:
                    for name in names:
                        if not supported(engine, name):
                            continue
                        log(f'{labels[engine]}/{name}: warmup {warmup}/{args.warmups}')
                        try:
                            elapsed, _, _ = execute(workers[engine], name)
                            results[engine]['benchmarks'][name]['warmup_wall_seconds'].append(elapsed)
                        except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.SubprocessError) as error:
                            results[engine]['benchmarks'][name]['errors'].append(str(error))
                            failure = str(error)
                            workers[engine].close()
                            cls = MontyWorker if engine_types[engine] == 'monty' else CPythonWorker
                            workers[engine] = stack.enter_context(cls(binaries[engine], args.timeout))
                            workers[engine].ready()
            for engine, name in schedule:
                if not supported(engine, name):
                    continue
                record = results[engine]['benchmarks'][name]
                log(f'{labels[engine]}/{name}: timing sample {len(record["wall_seconds"]) + 1}/{args.samples}')
                try:
                    if args.scenario == 'repeated_requests':
                        elapsed, setup, reset = execute(workers[engine], name)
                    elif args.scenario == 'warm_worker_one_shot':
                        cls = MontyWorker if engine_types[engine] == 'monty' else CPythonWorker
                        stdout, stderr, elapsed, setup, ready = one_shot_worker(
                            cls, binaries[engine], args.timeout, code[name], manifest[name]['file'], setups[name])
                        if stdout != manifest[name]['stdout'] or stderr:
                            raise ValueError(f'{name}: unexpected output: stdout={stdout!r}, stderr={stderr!r}')
                        record['worker_ready_seconds'].append(ready)
                        reset = None
                    else:
                        source = ROOT / 'workloads' / manifest[name]['file']
                        started = time.perf_counter_ns()
                        response = subprocess.run([str(binaries[engine]), str(source)], capture_output=True,
                                                  text=True, timeout=args.timeout)
                        elapsed = (time.perf_counter_ns() - started) / 1e9
                        validate(response, manifest[name]['stdout'], legacy(engine))
                        if response.stderr:
                            # Interpreter startup warnings are retained rather than treated as application output.
                            record.setdefault('process_stderr', []).append(response.stderr)
                        setup = reset = None
                except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.SubprocessError) as error:
                    record['errors'].append(str(error))
                    failure = str(error)
                    if args.scenario == 'repeated_requests':
                        workers[engine].__exit__(None, None, None)
                        cls = MontyWorker if engine_types[engine] == 'monty' else CPythonWorker
                        replacement = stack.enter_context(cls(binaries[engine], args.timeout))
                        replacement.ready()
                        workers[engine] = replacement
                    continue
                record['wall_seconds'].append(elapsed)
                log(f'{labels[engine]}/{name}: {elapsed * 1000:.3g} ms')
                if setup is not None:
                    record['session_setup_seconds'].append(setup)
                if reset is not None:
                    record['session_reset_seconds'].append(reset)
        except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.SubprocessError) as error:
            failure = str(error)
    for engine, result in results.items():
        for name, record in result['benchmarks'].items():
            if record['errors'] or len(record['wall_seconds']) != args.samples:
                continue
            spec = manifest[name]
            try:
                for sample in range(1, args.memory_samples + 1):
                    log(f'{labels[engine]}/{name}: RSS sample {sample}/{args.memory_samples}')
                    record['peak_rss_bytes'].append(collect(
                        binaries[engine], engine_types[engine], args.scenario, ROOT / 'workloads' / spec['file'],
                        spec['stdout'], args.timeout, legacy(engine)))
                    log(f'{labels[engine]}/{name}: RSS {record["peak_rss_bytes"][-1] / 1048576:.3g} MiB')
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                record['errors'].append({'phase': 'memory', 'message': str(error)})
            if args.memory_samples:
                record['memory_scope'] = 'Whole interpreter process, including startup, in separate one-shot runs'
            values = record['peak_rss_bytes']
            record['median_peak_rss_bytes'] = statistics.median(values) if values else None
    args.output.mkdir(parents=True)
    for engine, result in results.items():
        result['run_error'] = failure
        for name, record in result['benchmarks'].items():
            values = record['wall_seconds']
            if record.get('compatibility', {}).get('status') == 'unsupported':
                record['status'] = 'unsupported'
            else:
                record['status'] = 'ok' if not record['errors'] and len(values) == args.samples else 'failed'
            record['median_wall_seconds'] = statistics.median(values) if values else None
            record['stdev_wall_seconds'] = statistics.stdev(values) if len(values) > 1 else None
            readiness = record['worker_ready_seconds']
            record['median_worker_ready_seconds'] = statistics.median(readiness) if readiness else None
            for phase in ('setup', 'reset'):
                durations = record[f'session_{phase}_seconds']
                record[f'median_session_{phase}_seconds'] = statistics.median(durations) if durations else None
            median = record['median_wall_seconds']
            timing = f'{median * 1000:.3g} ms' if median is not None else 'n/a'
            log(f"{labels[engine]}/{name}: {record['status']}, median {timing}")
            if record['status'] == 'failed':
                print(f"{labels[engine]}/{name}: failed: {record['errors']}", file=sys.stderr, flush=True)
        with (args.output / f'{engine}.json').open('x') as destination:
            json.dump(result, destination, indent=2)
            destination.write('\n')
    if failure:
        print(f'Benchmark failure: {failure}', file=sys.stderr)
    return int(failure is not None or any(
        record['status'] == 'failed' for result in results.values() for record in result['benchmarks'].values()))


if __name__ == '__main__':
    sys.exit(main())
