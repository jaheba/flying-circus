import json
import subprocess
import sys


def main():
    import resource

    # One collector process per sample keeps child high-water marks independent.
    result = subprocess.run(sys.argv[2:], capture_output=True, text=True, timeout=float(sys.argv[1]))
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    print(json.dumps({
        'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr,
        'peak_rss_bytes': peak if sys.platform == 'darwin' else peak * 1024,
    }))


if __name__ == '__main__':
    main()
