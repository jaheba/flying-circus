import json
import sys

from .workload_source import split_source, prepare
from .workers import CPythonWorker, MontyWorker


def main():
    import resource

    request = json.load(sys.stdin)
    cls = MontyWorker if request['engine'] == 'monty' else CPythonWorker
    with cls(request['binary'], request['timeout'], arguments=request.get('arguments', [])) as worker:
        worker.ready()
        worker.configure(request['filename'])
        setup, code = split_source(request['code'])
        prepare(worker, setup, request['filename'])
        stdout, stderr = worker.run(code, request['filename'])
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    print(json.dumps({'stdout': stdout, 'stderr': stderr,
                      'peak_rss_bytes': peak if sys.platform == 'darwin' else peak * 1024}))


if __name__ == '__main__':
    main()
