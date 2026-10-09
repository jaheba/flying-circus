import unittest

from flying_circus.formatting import milliseconds


class TimingFormatTests(unittest.TestCase):
    def test_submillisecond_values_never_round_to_zero(self):
        for value in (0.12, 0.004, 0.0000001):
            self.assertGreater(float(milliseconds(value)), 0)
        self.assertEqual(milliseconds(12.345), '12')
        self.assertEqual(milliseconds(0.12345), '0.12')
        self.assertEqual(milliseconds(None), 'n/a')


class RuntimeFormatTests(unittest.TestCase):
    def test_extracts_the_runtime_version_without_build_metadata(self):
        from flying_circus.formatting import runtime_version

        self.assertEqual(runtime_version('monty', 'monty-runtime 1.1.0'), '1.1.0')
        self.assertEqual(runtime_version('cpython', 'Python 3.14.2'), '3.14.2')
        self.assertEqual(runtime_version('pypy', 'Python 3.10.14 (75b3de9d, May 28 2024)\n[PyPy 7.3.16 with GCC Apple LLVM 15.0.0]'), '7.3.16')
        self.assertEqual(runtime_version('cpython', 'Python 3.15.0rc1'), '3.15.0rc1')
        self.assertEqual(runtime_version('monty', 'unverified-local'), 'unknown')

    def test_headers_keep_labels_and_descriptions_keep_versions(self):
        from flying_circus.formatting import runtime_description, runtime_label

        runtime = {'label': 'pypy3', 'engine': 'pypy', 'version': 'Python 3.10.14\n[PyPy 7.3.16 with GCC Apple LLVM 15.0.0]'}
        self.assertEqual(runtime_label(runtime), 'PyPy')
        self.assertEqual(runtime_description(runtime, {'engine': 'pypy'}), 'PyPy 7.3.16')
        self.assertEqual(runtime_label({'label': 'monty-1.0'}), 'Monty 1.0')
        self.assertEqual(runtime_label({'label': 'baseline'}), 'baseline')
