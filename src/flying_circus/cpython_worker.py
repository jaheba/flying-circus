import contextlib
import io
import json
import sys


def main():
    namespace = {'__name__': '__main__'}
    print(json.dumps({'ready': True}), flush=True)
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if request['kind'] == 'reset':
                namespace = {'__name__': '__main__'}
                response = {'ok': True}
            elif request['kind'] == 'run':
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exec(compile(request['code'], request['filename'], 'exec'), namespace)
                response = {'ok': True, 'stdout': stdout.getvalue(), 'stderr': stderr.getvalue()}
            else:
                raise ValueError('Unknown request')
        except Exception as error:
            response = {'ok': False, 'exc_type': type(error).__name__, 'error': str(error)}
        print(json.dumps(response), flush=True)


if __name__ == '__main__':
    main()
