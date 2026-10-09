import json
import tempfile
import unittest
from pathlib import Path

from flying_circus.overview import render
from test_compare import run


class OverviewTests(unittest.TestCase):
    def results(self, root):
        for mode, scenario in (('one-shot', 'warm_worker_one_shot'), ('repeated', 'repeated_requests')):
            folder = root / mode
            folder.mkdir()
            for engine in ('monty', 'cpython'):
                result = run()
                result.update(binary_sha256=engine, revision='test', timestamp='test', build_info='',
                              configuration={'samples': 20, 'warmups': 3 if mode == 'repeated' else 0})
                result['benchmarks']['app']['scenario'] = scenario
                result['benchmarks']['app']['median_wall_seconds'] = (
                    0.01 if engine == 'monty' else 0.02) if mode == 'one-shot' else (
                    0.005 if engine == 'monty' else 0.002)
                if mode == 'repeated':
                    result['memory_method'] = None
                    result['benchmarks']['app']['median_peak_rss_bytes'] = None
                (folder / f'{engine}.json').write_text(json.dumps(result))

    def test_combines_modes_with_versions_and_key_facts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.results(root)
            document = render(root)
            self.assertEqual(document.count('<table'), 2)
            self.assertIn('data-one-shot=', document)
            self.assertIn('data-repeated=', document)
            self.assertIn('<strong>10.0</strong>', document)
            self.assertIn('<strong>10.0</strong> / 5.00', document)
            self.assertIn('runtime-info', document)
            self.assertIn('<strong>2.00</strong>', document)
            self.assertIn('CPU</dt><dd>Not recorded', document)
            self.assertNotIn('Median application request latency.', document)

    def test_rejects_different_binaries_across_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.results(root)
            path = root / 'repeated/monty.json'
            result = json.loads(path.read_text())
            result['binary_sha256'] = 'changed'
            path.write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError, 'binary_sha256'):
                render(root)

    def test_startup_is_a_separate_section(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.results(root)
            startup = {'scenario': 'empty_command_process', 'samples': 50, 'machine': 'test',
                       'platform': 'test', 'architecture': 'test',
                       'engines': {engine: {'binary_sha256': engine, 'median_wall_seconds': 0.002}
                                   for engine in ('monty', 'cpython')}}
            (root / 'startup.json').write_text(json.dumps(startup))
            document = render(root)
            self.assertEqual(document.count('<table'), 3)
            self.assertLess(document.index('Process startup · ms'), document.index('<h2>Runtime'))
            self.assertIn('50 samples · measured separately', document)
