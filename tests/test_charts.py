import unittest

from flying_circus.charts import runtime_chart


class ChartTests(unittest.TestCase):
    def test_ratios_and_unavailable_results(self):
        index = {'runtimes': {'python': {'engine': 'cpython', 'label': 'Python'},
                              'monty': {'engine': 'monty', 'label': 'Monty'}}}
        benches = {'python': {'work': {'status': 'ok', 'median_wall_seconds': 2},
                              'missing': {'status': 'ok', 'median_wall_seconds': 1}},
                   'monty': {'work': {'status': 'ok', 'median_wall_seconds': 1},
                             'missing': {'status': 'unsupported', 'median_wall_seconds': None}}}
        mode = {key: {'benchmarks': value} for key, value in benches.items()}
        document = runtime_chart(index, {'one-shot': mode, 'repeated': mode})
        self.assertIn('0.5×', document)
        self.assertIn('n/a', document)
        self.assertIn('CPython = 1×', document)
        self.assertIn('One-shot', document)
        self.assertIn('Repeated', document)
        self.assertNotIn('None', document)

    def test_no_cpython_has_no_chart(self):
        self.assertEqual(runtime_chart({'runtimes': {'m': {'engine': 'monty'}}}, {}), '')
