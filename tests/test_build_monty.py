import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('build_monty', Path(__file__).resolve().parents[1] / 'scripts/build_monty.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class MontyBuildTests(unittest.TestCase):
    def test_snapshots_release_binary_and_source_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            binary = source / 'target/release/monty'
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b'monty executable')
            output = root / 'runtimes'
            with patch.object(builder.subprocess, 'check_output', side_effect=['a' * 40 + '\n', 'rustc test\n']), \
                    patch.object(builder.subprocess, 'run', return_value=CompletedProcess([], 0, 'Monty test\n', '')) as run:
                builder.build(source, output)
            run.assert_any_call(['cargo', 'build', '--locked', '--release', '-p', 'monty-runtime', '--bin', 'monty'],
                                cwd=source.resolve(), check=True)
            snapshot = output / 'monty-main'
            self.assertEqual((snapshot / 'bin/monty').read_bytes(), binary.read_bytes())
            metadata = json.loads((snapshot / 'package.json').read_text())
            self.assertEqual(metadata['revision'], 'a' * 40)
            self.assertEqual(metadata['version'], 'Monty test')
            self.assertEqual(metadata['binary_sha256'], builder.hashlib.sha256(binary.read_bytes()).hexdigest())
            with self.assertRaises(FileExistsError):
                builder.build(source, output)
