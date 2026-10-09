import contextlib
import io
import itertools
import runpy
import unittest

from flying_circus.bench import ROOT


class CapacityPlanningTests(unittest.TestCase):
    def test_optimum_matches_exhaustive_search(self):
        with contextlib.redirect_stdout(io.StringIO()):
            namespace = runpy.run_path(str(ROOT / 'workloads/capacity_planning.py'))
        allocate = namespace['allocate']
        projects = [(3, 5), (4, 8), (7, 13), (2, 4), (5, 11)]
        for budget in (0, 1, 5, 10, 21):
            subsets = (subset for size in range(len(projects) + 1)
                       for subset in itertools.combinations(range(len(projects)), size))
            expected = max(sum(projects[i][1] for i in subset) for subset in subsets
                           if sum(projects[i][0] for i in subset) <= budget)
            benefit, selected = allocate(projects, budget)
            self.assertEqual(benefit, expected)
            self.assertEqual(len(selected), len(set(selected)))
            self.assertLessEqual(sum(projects[i][0] for i in selected), budget)
            self.assertEqual(sum(projects[i][1] for i in selected), benefit)
