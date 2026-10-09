import platform
import sys
import unittest
from pathlib import Path

from flying_circus.bench import digest
from flying_circus.startup import measure


class StartupTests(unittest.TestCase):
    def run_metadata(self):
        return {'configuration': {'binary': sys.executable},
                'binary_sha256': digest(Path(sys.executable)), 'revision': 'test',
                'machine': platform.node(), 'platform': platform.platform(),
                'architecture': platform.machine()}

    def test_fresh_empty_command_processes(self):
        result = measure({'cpython': self.run_metadata()}, 2, 30)
        entry = result['engines']['cpython']
        self.assertEqual(entry['command'][-2:], ['-c', ''])
        self.assertEqual(len(entry['wall_seconds']), 2)
        self.assertGreater(entry['median_wall_seconds'], 0)
        self.assertEqual(result['scenario'], 'empty_command_process')

    def test_rejects_changed_binary_or_host(self):
        for field in ('binary_sha256', 'machine'):
            run = self.run_metadata()
            run[field] = 'changed'
            with self.assertRaises(ValueError):
                measure({'cpython': run}, 2, 30)
