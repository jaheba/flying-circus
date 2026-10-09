import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('publish_results', Path(__file__).resolve().parents[1] / 'scripts/publish_results.py')
publishing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publishing)


class PublishingTests(unittest.TestCase):
    def test_archives_runs_and_updates_latest_without_overwriting_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            results = root / 'results'
            results.mkdir()
            (results / 'run.json').write_text(json.dumps({'timestamp': '2026-10-09T12:00:00Z'}))
            (results / 'report.html').write_text('<html><main>first</main></html>')
            site = root / 'site'
            with patch.object(publishing, 'write_reports'):
                publishing.publish(results, site, 'first-run')
                (results / 'report.html').write_text('<html><main>second</main></html>')
                publishing.publish(results, site, 'second-run')
                with self.assertRaisesRegex(ValueError, 'already published'):
                    publishing.publish(results, site, 'first-run')
            self.assertIn('first', (site / 'runs/first-run/report.html').read_text())
            latest = (site / 'index.html').read_text()
            self.assertIn('second', latest)
            self.assertIn('runs/second-run/report.json', latest)
            self.assertEqual([entry['id'] for entry in json.loads((site / 'history.json').read_text())], ['second-run', 'first-run'])
            self.assertIn('runs/first-run/report.html', (site / 'archive.html').read_text())
            self.assertTrue((site / '.nojekyll').exists())

    def test_rejects_invalid_run_id(self):
        with self.assertRaisesRegex(ValueError, 'Invalid run ID'):
            publishing.publish('/unused', '/unused', '../escape')

    def test_each_monty_runtime_keeps_its_own_package_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            results, builds = root / 'results', root / 'builds'
            results.mkdir()
            index = {'timestamp': '2026-10-09T12:00:00Z', 'runtimes': {}}
            for key, label in [('old', 'monty-1.0'), ('new', 'monty-1.1')]:
                index['runtimes'][key] = {'engine': 'monty', 'label': label}
                folder = builds / label
                folder.mkdir(parents=True)
                metadata = {'label': label, 'package': 'pydantic-monty-runtime', 'package_version': key * 10, 'version': label, 'binary_sha256': key}
                (folder / 'package.json').write_text(json.dumps(metadata))
                for mode in ('one-shot', 'repeated'):
                    (results / mode).mkdir(exist_ok=True)
                    (results / mode / f'{key}.json').write_text(json.dumps({'binary_sha256': key}))
            (results / 'run.json').write_text(json.dumps(index))
            (results / 'report.html').write_text('<main>reports</main>')
            with patch.object(publishing, 'write_reports'):
                publishing.publish(results, root / 'site', 'versions', builds)
            saved = json.loads((results / 'run.json').read_text())
            self.assertEqual(saved['runtimes']['old']['version'], 'monty-1.0')
            self.assertEqual(saved['runtimes']['new']['revision'], 'new' * 10)
            self.assertEqual(len(json.loads((results / 'build.json').read_text())['monty_packages']), 2)
            for key in ('old', 'new'):
                data = json.loads((results / 'repeated' / f'{key}.json').read_text())
                self.assertEqual(data['revision'], key * 10)
