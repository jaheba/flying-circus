import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flying_circus import matrix, workers


class RuntimeArgumentTests(unittest.TestCase):
    def test_worker_arguments_reach_interpreter(self):
        with workers.CPythonWorker(sys.executable, 5, arguments=['-B', '-X', 'dev']) as worker:
            worker.ready()
            worker.configure('flags.py')
            output, error = worker.run('import sys\nprint(sys.dont_write_bytecode, sys.flags.dev_mode)\n', 'flags.py')
        self.assertEqual(output, 'True True\n')
        self.assertEqual(error, '')

    def test_monty_arguments_precede_subcommand(self):
        with patch.object(workers.Worker, '__init__', return_value=None) as constructor:
            workers.MontyWorker('/path/monty', 5, arguments=['--opt', '--size=2'])
        constructor.assert_called_once_with(['/path/monty', '--opt', '--size=2', 'subprocess'], 5, True)

    def test_arguments_are_preserved_in_startup_timing_and_memory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'sample.py'
            source.write_text('print(42)\n')
            output = root / 'results'
            memory = '1' if sys.platform in ('linux', 'darwin') else '0'
            with contextlib.redirect_stdout(io.StringIO()):
                status = matrix.main(['--quick', '-r', 'python=' + sys.executable,
                                      '--runtime-arg', 'python=-B', '--runtime-arg', 'python=-X',
                                      '--runtime-arg', 'python=dev', '--benchmark', str(source),
                                      '--memory-samples', memory, '--format', 'json', '--output', str(output)])
            self.assertEqual(status, 0)
            arguments = ['-B', '-X', 'dev']
            startup = json.loads((output / 'startup.json').read_text())
            self.assertEqual(startup['engines']['python']['command'][1:-2], arguments)
            for mode in ('one-shot', 'repeated'):
                data = json.loads((output / mode / 'python.json').read_text())
                self.assertEqual(data['configuration']['arguments'], arguments)
                self.assertEqual(data['benchmarks']['sample']['status'], 'ok')
            one = json.loads((output / 'one-shot/python.json').read_text())
            self.assertEqual(len(one['benchmarks']['sample']['peak_rss_bytes']), int(memory))

    def test_unknown_runtime_label_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                matrix.main(['-r', 'python=' + sys.executable, '--runtime-arg', 'missing=--opt',
                             '--output', str(Path(temporary) / 'results')])
