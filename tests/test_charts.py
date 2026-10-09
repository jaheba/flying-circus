import math
import unittest

from flying_circus.charts import advantage_order, inline_chart, relative_values


class ChartTests(unittest.TestCase):
    def test_ratios_use_shared_asinh_scale(self):
        index = {'runtimes': {'python': {'engine': 'cpython'}, 'monty': {'engine': 'monty'}}}
        mode = {'python': {'benchmarks': {'work': {'status': 'ok', 'median_wall_seconds': 2},
                                        'missing': {'status': 'ok', 'median_wall_seconds': 1}}},
                'monty': {'benchmarks': {'work': {'status': 'ok', 'median_wall_seconds': 1},
                                       'missing': {'status': 'unsupported', 'median_wall_seconds': None}}}}
        ratios, extent = relative_values(index, {'one-shot': mode, 'repeated': mode})
        self.assertEqual(ratios['one-shot', 'monty', 'work'], .5)
        self.assertEqual(ratios['one-shot', 'python', 'work'], 1)
        self.assertNotIn(('one-shot', 'monty', 'missing'), ratios)
        self.assertAlmostEqual(extent, math.asinh(10))
        self.assertIn('bottom:50.000000%;height:50.000000%', inline_chart(.5, extent, 'one-shot'))
        self.assertIn('bottom:0.000000%;height:50.000000%', inline_chart(1.5, extent, 'repeated'))
        self.assertIn('height:0.000000%', inline_chart(1, extent, 'one-shot'))
        self.assertIn('inline-chart better', inline_chart(.5, extent, 'one-shot'))
        self.assertIn('inline-chart worse', inline_chart(2, extent, 'repeated'))
        self.assertEqual(inline_chart(None, extent, 'one-shot'), '')

    def test_no_cpython_has_no_chart(self):
        self.assertEqual(relative_values({'runtimes': {'m': {'engine': 'monty'}}}, {}), ({}, 1))

    def test_memory_ratios_use_rss_and_memory_tooltips(self):
        index = {'runtimes': {'python': {'engine': 'cpython'}, 'monty': {'engine': 'monty'}}}
        runs = {'one-shot': {key: {'benchmarks': {'work': {'status': 'ok', 'median_peak_rss_bytes': value}}}
                             for key, value in [('python', 100), ('monty', 200)]}}
        ratios, extent = relative_values(index, runs, 'median_peak_rss_bytes')
        self.assertEqual(ratios['one-shot', 'monty', 'work'], 2)
        chart = inline_chart(2, extent, 'one-shot', 'RSS')
        self.assertIn('inline-chart worse', chart)
        self.assertIn('CPython RSS (2×); lower is less memory', chart)

    def test_small_changes_get_more_space_than_log_scale(self):
        extent = math.asinh(20)
        offset = 50 * math.asinh(.01 / .05) / extent
        self.assertGreater(offset, 50 * math.log2(1.01))
        self.assertIn('+1.00% vs CPython', inline_chart(1.01, extent, 'one-shot'))

    def test_advantage_order_uses_ratios_and_ignores_baseline(self):
        names = ['small_gain', 'large_gain', 'missing', 'regression']
        ratios = {('one-shot', 'monty', 'small_gain'): .9,
                  ('one-shot', 'monty', 'large_gain'): .2,
                  ('one-shot', 'monty', 'regression'): 1.2,
                  ('one-shot', 'python', 'missing'): 1}
        self.assertEqual(advantage_order(names, ratios, 'python'),
                         ['large_gain', 'small_gain', 'regression', 'missing'])
        self.assertEqual(advantage_order(names, {}, None), names)
