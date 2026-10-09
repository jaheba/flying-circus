import copy
import unittest

from flying_circus.compare import compare_runs


def run():
    return {
        'schema_version': 1, 'machine': 'test', 'platform': 'test', 'architecture': 'test',
        'harness_sha256': 'h', 'memory_helper_sha256': 'm', 'harness_python': '3.14',
        'memory_method': 'rss', 'benchmarks': {'app': {
            'scenario': 'fresh_process', 'workload_sha256': 'w', 'expected_sha256': 'e',
            'status': 'ok', 'median_wall_seconds': 0.01, 'median_peak_rss_bytes': 1048576,
        }},
    }


class ComparisonTests(unittest.TestCase):
    def test_ratios_and_memory(self):
        monty, cpython = run(), run()
        cpython['benchmarks']['app']['median_wall_seconds'] = 0.02
        row, = compare_runs(monty, cpython)
        self.assertEqual(row['latency_ratio'], 0.5)
        self.assertEqual(row['monty_ms'], 10)
        self.assertEqual(row['monty_rss_mib'], 1)

    def test_rejects_incompatible_or_failed_runs(self):
        original = run()
        for field in ('machine', 'harness_sha256', 'memory_method'):
            other = copy.deepcopy(original)
            other[field] = 'different'
            with self.assertRaises(ValueError):
                compare_runs(original, other)
        for field, value in [('workload_sha256', 'different'), ('status', 'failed'), ('scenario', 'warm_worker_new_session')]:
            other = copy.deepcopy(original)
            other['benchmarks']['app'][field] = value
            with self.assertRaises(ValueError):
                compare_runs(original, other)


class PyPyComparisonTests(unittest.TestCase):
    def test_three_engines(self):
        monty, cpython, pypy = run(), run(), run()
        cpython['benchmarks']['app']['median_wall_seconds'] = 0.02
        pypy['benchmarks']['app']['median_wall_seconds'] = 0.005
        row, = compare_runs(monty, cpython, pypy)
        self.assertEqual(row['pypy_ms'], 5)
        self.assertEqual(row['monty_pypy_ratio'], 2)
        self.assertEqual(row['latency_ratio'], 0.5)
        self.assertEqual(row['pypy_rss_mib'], 1)

    def test_pypy_is_validated(self):
        pypy = run()
        pypy['benchmarks']['app']['status'] = 'failed'
        with self.assertRaises(ValueError):
            compare_runs(run(), run(), pypy)

class WinnerRenderingTests(unittest.TestCase):
    def test_winners_are_selected_per_metric(self):
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        from flying_circus.compare import main

        baseline, candidate = run(), run()
        for result in (baseline, candidate):
            result.update(revision='test', timestamp='test', build_info='', configuration={}, engine='monty')
        candidate['benchmarks']['app']['median_wall_seconds'] = 0.005
        candidate['benchmarks']['app']['median_peak_rss_bytes'] = 2097152
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            (root / 'baseline.json').write_text(json.dumps(baseline))
            (root / 'candidate.json').write_text(json.dumps(candidate))
            main(['--monty-results', str(root / 'baseline.json'),
                  '--candidate-results', str(root / 'candidate.json'), '--output', str(root / 'report.html')])
            document = (root / 'report.html').read_text()
            self.assertIn('<strong>5</strong>', document)
            self.assertIn('<strong>1.00</strong>', document)
            self.assertNotIn('<strong>10</strong>', document)
            self.assertNotIn('<strong>2.00</strong>', document)
