import unittest
from unittest.mock import patch

from flying_circus import export, matrix_report


class DiffLayoutTests(unittest.TestCase):
    def data(self):
        index = {'runtimes': {key: {'label': key, 'engine': 'monty', 'revision': 'monty 1.0'}
                              for key in ('baseline', 'candidate')}}
        runs = {}
        for mode in ('one-shot', 'repeated'):
            runs[mode] = {}
            for key in index['runtimes']:
                benchmarks = {}
                for name in ('changed', 'unchanged'):
                    value = .005 if key == 'candidate' and name == 'changed' else .01
                    rss = 1048576 if key == 'candidate' and name == 'changed' else 2097152
                    benchmarks[name] = {'status': 'ok', 'median_wall_seconds': value,
                                        'wall_seconds': [value] * 20, 'median_peak_rss_bytes': rss,
                                        'peak_rss_bytes': [rss] * 20 if mode == 'one-shot' else [], 'errors': []}
                runs[mode][key] = {'engine': 'monty', 'revision': 'monty 1.0', 'platform': 'test',
                                  'binary_sha256': key, 'build_info': '',
                                  'configuration': {'samples': 20, 'warmups': 3, 'binary': '/path/monty'},
                                  'benchmarks': benchmarks}
        startup = {'engines': {key: {'median_wall_seconds': value, 'wall_seconds': [value] * 20, 'errors': []}
                               for key, value in [('baseline', .002), ('candidate', .001)]}}
        return index, runs, startup

    def test_diff_has_normal_tables_and_baseline_bars(self):
        data = self.data()
        with patch.object(matrix_report, 'load', return_value=data):
            document, changes = matrix_report.render('unused', diff=True)
            markdown = export.markdown(export.report_data('unused', diff=True))
        self.assertEqual(document.count('<table'), 3)
        self.assertIn('data-paired="true"', document)
        self.assertIn('vs baseline runtime', document)
        self.assertIn('vs baseline RSS', document)
        self.assertIn('<th>baseline</th><th>candidate</th>', document)
        self.assertIn('<td>unchanged</td>', document)
        self.assertIn('id="significant-only"', document)
        self.assertIn('data-benchmark="unchanged" data-significant="false"', document)
        self.assertIn('data-benchmark="changed" data-significant="true"', document)
        self.assertNotIn('id="significant-only" checked', document)
        self.assertNotIn('Bounds / reason', document)
        self.assertIn('Runtime · ms · one-shot / repeated', markdown)
        self.assertIn('Peak RSS', markdown)
        self.assertNotIn('| unchanged |', markdown)
        self.assertTrue(any(row['status'] == 'unchanged' for row in changes))

    def test_unchanged_metric_remains_available_to_toggle(self):
        index, runs, startup = self.data()
        for mode in runs:
            record = runs[mode]['candidate']['benchmarks']['changed']
            record['median_peak_rss_bytes'] = 2097152
            record['peak_rss_bytes'] = [2097152] * 20 if mode == 'one-shot' else []
        startup = {'engines': {}}
        with patch.object(matrix_report, 'load', return_value=(index, runs, startup)):
            document, _ = matrix_report.render('unused', diff=True)
        self.assertEqual(document.count('<table'), 2)
        self.assertIn('<h2>Peak RSS', document)
        memory_section = document.split('<h2>Peak RSS', 1)[1]
        self.assertIn('data-benchmark="changed" data-significant="false"', memory_section)
        self.assertIn('vs baseline runtime', document)
