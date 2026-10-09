import sys
import unittest
from unittest.mock import patch

from flying_circus.differences import difference
from flying_circus.runtimes import resolve_all
from flying_circus.matrix_report import diff_results


class MatrixTests(unittest.TestCase):
    def test_runtime_label_is_independent_of_type(self):
        values = resolve_all(['baseline=' + sys.executable, 'optimized=' + sys.executable])
        self.assertEqual(list(values), ['baseline', 'optimized'])
        self.assertEqual([v['label'] for v in values.values()], ['baseline', 'optimized'])
        self.assertTrue(all(v['engine'] == 'cpython' for v in values.values()))
        self.assertTrue(all(v['version'].startswith('Python ') for v in values.values()))
        with self.assertRaisesRegex(ValueError, 'Duplicate runtime label'):
            resolve_all(['same=' + sys.executable] * 2)

    def test_clear_changes_and_low_sample_counts(self):
        self.assertEqual(difference([1] * 10, [2] * 10)['status'], 'regression')
        self.assertEqual(difference([2] * 10, [1] * 10)['status'], 'improvement')
        self.assertEqual(difference([1] * 2, [1] * 2)['status'], 'unchanged')
        self.assertEqual(difference([1] * 2, [2] * 2)['status'], 'inconclusive')
        self.assertEqual(difference([1] * 10, [1.01] * 10)['status'], 'unchanged')
        self.assertEqual(difference([], [1])['status'], 'unavailable')
        with self.assertRaises(ValueError):
            difference([float('nan')], [1])

    def test_labels_survive_numeric_difference_results(self):
        index = {'runtimes': {'a': {'label': 'before'}, 'b': {'label': 'after'}}}
        records = {'a': {'status': 'ok', 'wall_seconds': [1] * 10},
                   'b': {'status': 'ok', 'wall_seconds': [2] * 10}}
        with patch('flying_circus.matrix_report.entries', return_value=[('work', 'repeated', 'ms', records, 'wall_seconds', 1000)]):
            row, = diff_results(index, {}, {}, 5, .01)
        self.assertEqual(row['candidate_label'], 'after')
        self.assertEqual(row['candidate'], 2000)
        self.assertEqual(row['status'], 'regression')

    def test_failures_and_compatibility_are_always_visible(self):
        index = {'runtimes': {'a': {'label': 'before'}, 'b': {'label': 'after'}}}
        for status, expected in [('failed', 'failure'), ('unsupported', 'compatibility change')]:
            records = {'a': {'status': 'ok'}, 'b': {'status': status, 'errors': ['broken']}}
            with patch('flying_circus.matrix_report.entries', return_value=[('work', 'repeated', 'ms', records, 'wall_seconds', 1000)]):
                row, = diff_results(index, {}, {}, 5, .01)
            self.assertEqual(row['status'], expected)

    def test_standalone_cli_generates_both_report_modes(self):
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        from flying_circus import matrix, warm
        from test_scenarios import FakeWorker

        original = warm.main
        def tiny_run(argv, runtimes):
            return original(argv + ['--workload', 'startup'], runtimes=runtimes)

        for diff, formats in ((False, []), (True, []),
                              (False, ['html', 'markdown', 'json']), (True, ['html', 'markdown', 'json']),
                              (False, ['json']), (True, ['markdown'])):
            with self.subTest(diff=diff, formats=formats), tempfile.TemporaryDirectory() as temporary, \
                    patch.object(matrix.warm, 'main', side_effect=tiny_run), \
                    patch.object(warm, 'CPythonWorker', FakeWorker), \
                    contextlib.redirect_stdout(io.StringIO()):
                output = Path(temporary) / 'results'
                argv = ['-r', 'before=' + sys.executable, '-r', 'after=' + sys.executable,
                        '--samples', '2', '--startup-samples', '2', '--memory-samples', '0',
                        '--warmups', '0', '--output', str(output)]
                for format in formats:
                    argv += ['--format', format]
                self.assertEqual(matrix.main(argv + (['--diff'] if diff else [])), 0)
                expected = set(formats or ['html'])
                for format, extension in [('html', 'html'), ('markdown', 'md'), ('json', 'json')]:
                    path = output / ('report.' + extension)
                    self.assertEqual(path.exists(), format in expected)
                    if path.exists():
                        document = path.read_text()
                        self.assertIn('before', document)
                        self.assertIn('after', document)
                        if format == 'json':
                            data = json.loads(document)
                            self.assertEqual(data['schema_version'], 1)
                            self.assertEqual(data['mode'], 'diff' if diff else 'comparison')
                            self.assertEqual(len(data['results']['one-shot']['before']['benchmarks']['startup']['wall_seconds']), 2)
                            self.assertEqual(len(data['startup']['engines']['before']['wall_seconds']), 2)
                            self.assertEqual(data['diff'] is not None, diff)
                        elif not diff:
                            self.assertIn('Peak RSS', document)
                            self.assertIn('one-shot / repeated', document)
                            self.assertLess(document.index('Process startup'), document.index('Runtime · ms'))
                            self.assertIn('<strong>' if format == 'html' else '**', document)
                            self.assertIn('Python ', document)
                self.assertTrue((output / 'startup.json').is_file())
                if diff:
                    self.assertTrue(json.loads((output / 'diff.json').read_text()))

    def test_quick_presets_and_explicit_overrides(self):
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        from flying_circus import matrix, warm
        from test_scenarios import FakeWorker

        original = warm.main
        def tiny_run(argv, runtimes):
            return original(argv + ['--workload', 'startup'], runtimes=runtimes)

        cases = [(['--quick'], 3, 5, 1, 1),
                 (['--samples', '10', '--startup-samples', '7', '--warmups', '2', '--memory-samples', '1', '--quick'], 10, 7, 2, 1)]
        for flags, samples, startup_samples, warmups, memory in cases:
            with self.subTest(flags=flags), tempfile.TemporaryDirectory() as temporary, \
                    patch.object(matrix.warm, 'main', side_effect=tiny_run), \
                    patch.object(warm, 'CPythonWorker', FakeWorker), \
                    patch.object(warm, 'collect', return_value=1048576), \
                    contextlib.redirect_stdout(io.StringIO()):
                output = Path(temporary) / 'results'
                self.assertEqual(matrix.main(['-r', sys.executable, '--output', str(output)] + flags), 0)
                index = json.loads((output / 'run.json').read_text())
                self.assertTrue(index['options']['quick'])
                for mode in ('one-shot', 'repeated'):
                    result = json.loads((output / mode / (Path(sys.executable).name + '.json')).read_text())
                    record = result['benchmarks']['startup']
                    self.assertEqual(len(record['wall_seconds']), samples)
                    self.assertEqual(len(record['warmup_wall_seconds']), warmups if mode == 'repeated' else 0)
                    self.assertEqual(len(record['peak_rss_bytes']), memory if mode == 'one-shot' else 0)
                self.assertEqual(len(json.loads((output / 'startup.json').read_text())['engines'][Path(sys.executable).name]['wall_seconds']), startup_samples)
                self.assertIn('Quick run', (output / 'report.html').read_text())

class VerboseTests(unittest.TestCase):
    def test_verbose_progress_and_quiet_default(self):
        import contextlib
        import io
        import tempfile
        from pathlib import Path
        from flying_circus import matrix, warm
        from test_scenarios import FakeWorker

        original = warm.main
        def tiny_run(argv, runtimes):
            return original(argv + ['--workload', 'startup'], runtimes=runtimes)

        for verbose in (False, True):
            with self.subTest(verbose=verbose), tempfile.TemporaryDirectory() as folder:
                output = io.StringIO()
                with patch.object(matrix.warm, 'main', side_effect=tiny_run), \
                     patch.object(warm, 'CPythonWorker', FakeWorker), \
                     patch.object(warm, 'collect', return_value=1048576), \
                     contextlib.redirect_stdout(output):
                    status = matrix.main(['-r', 'test=' + sys.executable, '--quick',
                                          '--output', str(Path(folder) / 'results')]
                                         + (['-v'] if verbose else []))
                self.assertEqual(status, 0)
                text = output.getvalue()
                self.assertIn('Report:', text)
                for progress in ('test: startup sample 1/5', 'test/startup: timing sample 1/3',
                                 'test/startup: warmup 1/1', 'test/startup: RSS sample 1/1',
                                 'RSS 1 MiB', 'median '):
                    self.assertEqual(progress in text, verbose, progress)
