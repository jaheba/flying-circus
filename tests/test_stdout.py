import contextlib
import io
import json
import unittest

from flying_circus.bench import ROOT


class StdoutTests(unittest.TestCase):
    def test_many_small_prints_match_expected_output(self):
        spec = json.loads((ROOT / 'workloads/manifest.json').read_text())['stdout_lines']
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec((ROOT / 'workloads' / spec['file']).read_text(), {})
        text = output.getvalue()
        self.assertEqual(text, spec['stdout'])
        self.assertEqual(len(text.splitlines()), 10000)
        self.assertEqual(len(text.encode()), 330000)
