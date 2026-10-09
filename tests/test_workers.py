import io
import sys
import time
import unittest

from flying_circus.workers import CPythonWorker, read_exact


class WorkerTests(unittest.TestCase):
    def test_partial_frame_eof(self):
        with self.assertRaises(EOFError):
            read_exact(io.BytesIO(b'ab'), 4)
        self.assertEqual(read_exact(io.BytesIO(b'abcd'), 4), b'abcd')

    def test_cpython_session_reset_and_output(self):
        with CPythonWorker(sys.executable, 5) as worker:
            worker.ready()
            worker.configure('test.py')
            self.assertEqual(worker.run("value = 42\nprint(value)", 'test.py'), ('42\n', ''))
            worker.configure('test.py')
            self.assertEqual(worker.run("print('value' in globals())", 'test.py'), ('False\n', ''))
            with self.assertRaisesRegex(RuntimeError, 'ValueError: expected'):
                worker.run("raise ValueError('expected')", 'test.py')
        self.assertIsNotNone(worker.process.poll())

    def test_deadline_kills_worker(self):
        with CPythonWorker(sys.executable, 5) as worker:
            worker.ready()
            worker.configure('test.py')
            worker.timeout = 0.05
            started = time.perf_counter()
            with self.assertRaises(TimeoutError):
                worker.run('while True: pass', 'test.py')
            self.assertLess(time.perf_counter() - started, 2)
            self.assertIsNotNone(worker.process.poll())
