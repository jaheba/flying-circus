import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from flying_circus.matrix import main


class ParallelTests(unittest.TestCase):
    def test_four_jobs_merge_custom_results_without_missing_samples(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            argv = ['--quick', '-x4', '-r', 'python=' + sys.executable,
                    '--format', 'json', '--output', str(root / 'results')]
            for number in range(4):
                source = root / f'work_{number}.py'
                source.write_text(f'print(sum(range({number + 10})))\n')
                argv += ['--benchmark', str(source)]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(argv + ['--memory-samples', '0']), 0)
            for mode in ('one-shot', 'repeated'):
                data = json.loads((root / 'results' / mode / 'python.json').read_text())
                self.assertEqual(len(data['benchmarks']), 4)
                self.assertEqual(data['configuration']['parallel_jobs'], 4)
                self.assertEqual(data['configuration']['active_shards'], 4)
                self.assertEqual(len(data['shards']), 4)
                for record in data['benchmarks'].values():
                    self.assertEqual(record['status'], 'ok')
                    self.assertEqual(len(record['wall_seconds']), 3)
                    self.assertEqual(len(record['warmup_wall_seconds']), 1 if mode == 'repeated' else 0)
            report = json.loads((root / 'results/report.json').read_text())
            self.assertEqual(report['run']['options']['x'], 4)

    def test_zero_jobs_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['-r', sys.executable, '-x0'])
