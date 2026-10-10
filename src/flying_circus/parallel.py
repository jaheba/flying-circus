import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import warm
from .bench import ROOT
from .compatibility import select_workloads


def run(argv, runtimes, manifest, output, jobs):
    manifest = manifest if manifest is not None else json.loads((ROOT / 'workloads/manifest.json').read_text())
    names = select_workloads(manifest, 'all', None)
    count = min(jobs, len(names))
    shards = output.parent / (output.name + '-shards')
    shards.mkdir()
    requests = []
    for index in range(count):
        selected = names[index::count]
        folder = shards / str(index + 1)
        arguments = argv + ['--output', str(folder)]
        for name in selected:
            arguments += ['--workload', name]
        request = shards / f'{index + 1}.json'
        request.write_text(json.dumps({'argv': arguments, 'runtimes': runtimes, 'manifest': manifest}, default=str))
        requests.append(request)

    def execute(request):
        return subprocess.run([sys.executable, '-m', 'flying_circus.parallel', str(request)]).returncode

    with ThreadPoolExecutor(max_workers=count) as executor:
        statuses = list(executor.map(execute, requests))
    output.mkdir()
    for key in runtimes:
        records = [json.loads((shards / str(index + 1) / f'{key}.json').read_text()) for index in range(count)]
        merged = dict(records[0])
        combined = {name: record for part in records for name, record in part['benchmarks'].items()}
        merged['benchmarks'] = {name: combined[name] for name in names}
        merged['configuration'] = dict(merged['configuration'], parallel_jobs=jobs, active_shards=count)
        merged['schedule'] = [item for part in records for item in part['schedule']]
        merged['shards'] = [{'path': str(shards / str(index + 1)),
                             'worker_ready_seconds': part.get('worker_ready_seconds'),
                             'run_error': part.get('run_error')} for index, part in enumerate(records)]
        merged['run_error'] = next((part['run_error'] for part in records if part.get('run_error')), None)
        (output / f'{key}.json').write_text(json.dumps(merged, indent=2) + '\n')
    return int(any(statuses))


if __name__ == '__main__':
    request = json.loads(Path(sys.argv[1]).read_text())
    raise SystemExit(warm.main(request['argv'], runtimes=request['runtimes'], manifest_override=request['manifest']))
