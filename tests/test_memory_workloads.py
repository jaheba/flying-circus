import contextlib
import io
import json
import unittest

from flying_circus.bench import ROOT


class MemoryWorkloadTests(unittest.TestCase):
    def test_retained_allocations_and_expected_outputs(self):
        manifest = json.loads((ROOT / 'workloads/manifest.json').read_text())
        for name, spec in manifest.items():
            if spec.get('suite') != 'memory':
                continue
            with self.subTest(name=name):
                namespace = {}
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    exec((ROOT / 'workloads' / spec['file']).read_text(), namespace)
                self.assertEqual(output.getvalue(), spec['stdout'])
                retained = namespace.get('values', namespace.get('records'))
                self.assertEqual(len(retained), namespace['COUNT'])
                if 'WIDTH' in namespace:
                    self.assertTrue(all(len(value) == namespace['WIDTH'] for value in retained))
                else:
                    self.assertIsNot(retained[0]['region'], retained[100]['region'])
                    self.assertEqual(retained[0]['region'], retained[100]['region'])
