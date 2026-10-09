import argparse
import sys

from . import bench, compare, report


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description='Black-box application benchmarks for Monty')
    parser.add_argument('command', choices=('bench', 'report', 'compare', 'warm', 'run', 'memory', 'overview', 'startup'))
    if not argv or argv[0] not in ('bench', 'report', 'compare', 'warm', 'run', 'memory', 'overview', 'startup'):
        from .matrix import main as matrix_main
        return matrix_main(argv)
    command, *arguments = argv
    if command == 'startup':
        from .startup import main as startup_main
        return startup_main(arguments)
    if command == 'overview':
        from .overview import main as overview_main
        return overview_main(arguments)
    if command == 'memory':
        from .memory_collect import main as memory_main
        return memory_main(arguments)
    if command in ('warm', 'run'):
        from .warm import main as warm_main
        return warm_main(arguments)
    if command == 'bench':
        return bench.main(arguments)
    if command == 'compare':
        return compare.main(arguments)
    return report.main(arguments)
