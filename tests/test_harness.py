import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flying_circus import bench


class HarnessTests(unittest.TestCase):
    def test_validation_rejects_bad_output_and_exit(self):
        for result in [subprocess.CompletedProcess([], 0, 'wrong', ''),
                       subprocess.CompletedProcess([], 1, 'ready\n', 'failure')]:
            with self.assertRaises((RuntimeError, ValueError)):
                bench.validate(result, 'ready\n', False)

    def test_legacy_summary_requires_explicit_option(self):
        result = subprocess.CompletedProcess([], 0, 'ready\n2.5ms ❯ None\n', '')
        with self.assertRaises(ValueError):
            bench.validate(result, 'ready\n', False)
        bench.validate(result, 'ready\n', True)

    def test_run_and_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'results.json'
            command = [sys.executable, '-m', 'flying_circus', 'bench', '--monty', sys.executable,
                       '--engine', 'cpython', '--revision', 'test-cpython', '--samples', '2', '--memory-samples', '0',
                       '--output', str(output)]
            subprocess.run(command, check=True, capture_output=True)
            result = json.loads(output.read_text())
            self.assertEqual(set(result['benchmarks']), {
                'expense_report', 'order_cleanup', 'api_report',
                'capacity_planning', 'portfolio_risk', 'ticket_search', 'stdout_lines',
            })
            for sample in result['benchmarks'].values():
                self.assertEqual(sample['status'], 'ok')
                self.assertEqual(len(sample['wall_seconds']), 2)
            report = Path(directory) / 'history.html'
            subprocess.run([sys.executable, '-m', 'flying_circus', 'report', str(output),
                            '--output', str(report)], check=True)
            self.assertIn('test-cpython', report.read_text())
            duplicate = subprocess.run(command, capture_output=True)
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertEqual(json.loads(output.read_text()), result)

    def test_timeout_is_recorded_and_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'timeout.json'
            result = subprocess.run(
                [sys.executable, '-m', 'flying_circus', 'bench', '--monty', sys.executable,
                 '--revision', 'timeout', '--workload', 'startup', '--samples', '2',
                 '--memory-samples', '0', '--timeout', '0.000001', '--output', str(output)],
                capture_output=True,
            )
            self.assertEqual(result.returncode, 1)
            sample = json.loads(output.read_text())['benchmarks']['startup']
            self.assertEqual(sample['status'], 'failed')
            self.assertEqual(len(sample['errors']), 2)
            self.assertIsNone(sample['median_wall_seconds'])

    @unittest.skipUnless(sys.platform in ('linux', 'darwin'), 'OS accounting')
    def test_memory_collector(self):
        sample = bench.memory_sample([sys.executable, '-c', "print('ready')"], 10)
        self.assertEqual(sample['returncode'], 0)
        self.assertEqual(sample['stdout'], 'ready\n')
        self.assertGreater(sample['peak_rss_bytes'], 0)


if __name__ == '__main__':
    unittest.main()
