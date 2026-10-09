import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from flying_circus.custom import prepare_benchmarks
from flying_circus.matrix import main


class CustomTests(unittest.TestCase):
    def test_custom_run_validates_both_modes_and_snapshots_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'optimization.py'
            source.write_text('values = [str(i) for i in range(100)]\nassert len(values) == 100\nprint(len(values))\n')
            output = root / 'results'
            with contextlib.redirect_stdout(io.StringIO()):
                status = main(['--quick', '-r', 'python=' + sys.executable, '--benchmark', str(source),
                               '--memory-samples', '0', '--format', 'json', '--output', str(output)])
            self.assertEqual(status, 0)
            for mode in ('one-shot', 'repeated'):
                result = json.loads((output / mode / 'python.json').read_text())
                self.assertEqual(list(result['benchmarks']), ['optimization'])
                record = result['benchmarks']['optimization']
                self.assertEqual(record['status'], 'ok')
                self.assertEqual(len(record['wall_seconds']), 3)
                self.assertEqual(record['original_source'], str(source.resolve()))
            snapshot = output / 'workloads/optimization.py'
            original = snapshot.read_text()
            source.write_text('print("changed")\n')
            self.assertEqual(snapshot.read_text(), original)
            manifest = json.loads((output / 'workloads.json').read_text())
            self.assertEqual(manifest['optimization']['stdout'], '100\n')

    def test_extend_and_reject_duplicate_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'custom.py'
            source.write_text('print(42)\n')
            defaults = {'builtin': {'file': 'builtin.py'}}
            manifest = prepare_benchmarks([source], root, 5, defaults)
            self.assertEqual(list(manifest), ['builtin', 'custom'])
            with self.assertRaisesRegex(ValueError, 'Duplicate benchmark name'):
                prepare_benchmarks([source], root, 5, {'custom': {}})

    def test_reference_stderr_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'custom.py'
            source.write_text('import sys\nprint("warning", file=sys.stderr)\n')
            with self.assertRaisesRegex(ValueError, 'stderr'):
                prepare_benchmarks([source], root, 5, {})
