import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flying_circus import cache, runtimes


class CacheTests(unittest.TestCase):
    def test_snapshot_survives_rebuild_and_requires_explicit_replace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'build'
            source.write_bytes(b'first')
            runtime = {'binary': source, 'engine': 'monty', 'version': 'Monty test'}
            with patch.object(cache, 'cache_root', return_value=root / 'cache'), \
                 patch.object(runtimes, 'resolve', return_value=runtime):
                binary = cache.save('main', source)
                source.write_bytes(b'second')
                self.assertEqual(cache.cached_binary('main').read_bytes(), b'first')
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    cache.save('main', source)
                cache.save('main', source, replace=True)
                self.assertEqual(binary.read_bytes(), b'second')
                binary.write_bytes(b'corrupted')
                with self.assertRaisesRegex(ValueError, 'has changed'):
                    cache.cached_binary('main')

    def test_invalid_name(self):
        for name in ('../main', '', '/tmp/main', '..'):
            with self.assertRaises(ValueError):
                cache.entry(name)

    def test_runtime_reference_keeps_readable_label(self):
        import subprocess
        import sys
        with patch.object(cache, 'cached_binary', return_value=Path(sys.executable)), \
             patch.object(runtimes.subprocess, 'run', side_effect=[
                 subprocess.CompletedProcess([], 0, 'monty 1.2', ''),
                 subprocess.CompletedProcess([], 0, '', '')]):
            result = runtimes.resolve('@main')
            self.assertEqual(result['label'], 'main')
            self.assertEqual(result['engine'], 'monty')
