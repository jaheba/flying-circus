import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flying_circus import warm


class FakeWorker:
    instances = []

    def __init__(self, binary, timeout):
        self.calls = []
        self.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.calls.append('close')

    def ready(self):
        self.calls.append('ready')

    def configure(self, filename):
        self.calls.append('configure')

    def run(self, code, filename):
        self.calls.append('run')
        return 'ready\n', ''

    def reset(self):
        self.calls.append('reset')


class ScenarioTests(unittest.TestCase):
    def arguments(self, directory):
        return ['--monty', sys.executable, '--cpython', sys.executable,
                '--monty-revision', 'test', '--cpython-revision', 'test', '--memory-samples', '0', '--samples', '2',
                '--workload', 'startup', '--output', str(Path(directory) / 'result')]

    def test_one_shot_creates_fresh_worker_per_sample(self):
        FakeWorker.instances = []
        with tempfile.TemporaryDirectory() as directory, patch.object(warm, 'MontyWorker', FakeWorker), \
                patch.object(warm, 'CPythonWorker', FakeWorker), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(warm.main(self.arguments(directory)), 0)
            self.assertEqual(len(FakeWorker.instances), 4)
            for worker in FakeWorker.instances:
                self.assertEqual(worker.calls, ['ready', 'configure', 'run', 'close'])
            result = json.loads((Path(directory) / 'result/monty.json').read_text())
            self.assertEqual(result['configuration']['warmups'], 0)
            benchmark = result['benchmarks']['startup']
            self.assertEqual(benchmark['scenario'], 'warm_worker_one_shot')
            self.assertEqual(len(benchmark['worker_ready_seconds']), 2)
            self.assertEqual(benchmark['warmup_wall_seconds'], [])

    def test_repeated_requests_reuse_workers(self):
        FakeWorker.instances = []
        with tempfile.TemporaryDirectory() as directory, patch.object(warm, 'MontyWorker', FakeWorker), \
                patch.object(warm, 'CPythonWorker', FakeWorker), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(warm.main(self.arguments(directory) + ['--scenario', 'repeated_requests']), 0)
            self.assertEqual(len(FakeWorker.instances), 2)
            for worker in FakeWorker.instances:
                self.assertEqual(worker.calls.count('run'), 3)
                self.assertEqual(worker.calls.count('ready'), 1)
            result = json.loads((Path(directory) / 'result/monty.json').read_text())
            self.assertEqual(result['benchmarks']['startup']['scenario'], 'repeated_requests')
            self.assertEqual(len(result['benchmarks']['startup']['warmup_wall_seconds']), 1)

    def test_one_shot_rejects_warmups(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                warm.main(self.arguments(directory) + ['--warmups', '1'])
            self.assertEqual(error.exception.code, 2)

    def test_cold_process_runs_no_protocol_worker(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(warm, 'MontyWorker') as monty, \
                patch.object(warm, 'CPythonWorker') as cpython, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(warm.main(self.arguments(directory) + ['--scenario', 'cold_process_one_shot']), 0)
            monty.assert_not_called()
            cpython.assert_not_called()
            result = json.loads((Path(directory) / 'result/monty.json').read_text())
            self.assertEqual(result['benchmarks']['startup']['scenario'], 'cold_process_one_shot')
            self.assertEqual(result['benchmarks']['startup']['worker_ready_seconds'], [])

class MontyVersionTests(unittest.TestCase):
    def test_candidate_uses_monty_worker_and_memory_collector(self):
        FakeWorker.instances = []
        with tempfile.TemporaryDirectory() as directory, patch.object(warm, 'MontyWorker', FakeWorker), \
                patch.object(warm, 'CPythonWorker', side_effect=AssertionError('Wrong interpreter')), \
                patch.object(warm, 'collect', return_value=1048576) as memory, \
                contextlib.redirect_stdout(io.StringIO()):
            args = ['--monty', sys.executable, '--candidate', sys.executable,
                    '--monty-revision', 'before', '--candidate-revision', 'after',
                    '--samples', '2', '--memory-samples', '1', '--workload', 'startup',
                    '--output', str(Path(directory) / 'result')]
            self.assertEqual(warm.main(args), 0)
            self.assertEqual(len(FakeWorker.instances), 4)
            self.assertEqual([call.args[1] for call in memory.call_args_list], ['monty', 'monty'])
            result = json.loads((Path(directory) / 'result/candidate.json').read_text())
            self.assertEqual(result['engine'], 'monty')
            self.assertEqual(result['revision'], 'after')
            self.assertEqual(result['benchmarks']['startup']['median_peak_rss_bytes'], 1048576)
