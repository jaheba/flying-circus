import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flying_circus import warm
from flying_circus.bench import ROOT
from flying_circus.compare import compare_runs
from flying_circus.compatibility import probe_workload, select_workloads
from flying_circus.workers import WorkloadError
from test_compare import run


class ProbeWorker:
    result = ('expected\n', '')
    error = None

    def __init__(self, *args):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def ready(self):
        pass

    def configure(self, filename):
        pass

    def run(self, *args):
        if self.error:
            raise self.error
        return self.result


class CompatibilityTests(unittest.TestCase):
    def probe(self, error=None, result=('expected\n', ''), known_missing=()):
        with patch.object(ProbeWorker, 'error', error), patch.object(ProbeWorker, 'result', result):
            return probe_workload(ProbeWorker, 'unused', 1, 'unused', 'test.py', 'expected\n', known_missing)

    def test_missing_features_are_unsupported(self):
        for exc_type in ('NotImplementedError', 'ModuleNotFoundError', 'ImportError'):
            self.assertEqual(self.probe(WorkloadError(exc_type, 'missing'))['status'], 'unsupported')
        error = WorkloadError('AttributeError', "'list' object has no attribute 'insert'")
        self.assertEqual(self.probe(error)['status'], 'failed')
        known = [{'type': error.exc_type, 'message': error.message}]
        self.assertEqual(self.probe(error, known_missing=known)['status'], 'unsupported')

    def test_bad_results_timeouts_and_crashes_are_failures(self):
        self.assertEqual(self.probe(result=('wrong\n', ''))['status'], 'failed')
        for error in (TimeoutError('timeout'), RuntimeError('crashed'), WorkloadError('ValueError', 'bug')):
            self.assertEqual(self.probe(error)['status'], 'failed')

    def test_selection_keeps_applications_default_and_supports_game_suite(self):
        manifest = json.loads((ROOT / 'workloads/manifest.json').read_text())
        self.assertEqual(len(select_workloads(manifest, 'applications', None)), 7)
        games = select_workloads(manifest, 'benchmark_game', None)
        self.assertEqual(set(games), {'game_fannkuch', 'game_nbody', 'game_pidigits',
                                    'game_spectral_norm', 'game_regex_dna', 'game_meteor_contest'})
        self.assertEqual(len(select_workloads(manifest, 'pyperformance', None)), 5)
        self.assertNotIn('perf_gc_traversal', select_workloads(manifest, 'all', None))
        self.assertEqual(len(select_workloads(manifest, 'memory', None)), 5)
        self.assertEqual(len(select_workloads(manifest, 'all', None)), 37)

    def test_unsupported_engine_does_not_hide_other_timings(self):
        monty, cpython, pypy = run(), run(), run()
        monty['benchmarks']['app'].update(status='unsupported', median_wall_seconds=None,
                                         compatibility={'reason': 'yield is missing'})
        row, = compare_runs(monty, cpython, pypy)
        self.assertIsNone(row['monty_ms'])
        self.assertIsNone(row['latency_ratio'])
        self.assertIsNone(row['monty_pypy_ratio'])
        self.assertEqual(row['monty_reason'], 'yield is missing')
        self.assertEqual(row['cpython_ms'], 10)
        self.assertEqual(row['pypy_ms'], 10)

    def test_unsupported_workload_is_skipped_without_failing_run(self):
        class MontyProbe(ProbeWorker):
            pass

        class PythonProbe(ProbeWorker):
            def run(self, *args):
                return '30\n', ''

        def check(cls, *args):
            return {'status': 'unsupported', 'reason': 'missing insert'} if cls is MontyProbe else {
                'status': 'supported', 'reason': ''}

        with tempfile.TemporaryDirectory() as directory, patch.object(warm, 'MontyWorker', MontyProbe), \
                patch.object(warm, 'CPythonWorker', PythonProbe), patch.object(warm, 'probe_workload', side_effect=check), \
                contextlib.redirect_stdout(io.StringIO()):
            output = Path(directory) / 'results'
            result = warm.main(['--monty', sys.executable, '--cpython', sys.executable,
                                '--monty-revision', 'test', '--cpython-revision', 'test',
                                '--workload', 'game_fannkuch', '--memory-samples', '0', '--samples', '2', '--output', str(output)])
            self.assertEqual(result, 0)
            monty = json.loads((output / 'monty.json').read_text())['benchmarks']['game_fannkuch']
            cpython = json.loads((output / 'cpython.json').read_text())['benchmarks']['game_fannkuch']
            self.assertEqual(monty['status'], 'unsupported')
            self.assertEqual(monty['wall_seconds'], [])
            self.assertEqual(cpython['status'], 'ok')
            self.assertEqual(len(cpython['wall_seconds']), 2)
