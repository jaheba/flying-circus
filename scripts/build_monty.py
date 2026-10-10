"""Build a checked-out Monty main revision and record its provenance."""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def build(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    destination = output / 'monty-main'
    destination.mkdir(parents=True, exist_ok=False)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    command = ['cargo', 'build', '--locked', '--release', '-p', 'monty-runtime', '--bin', 'monty']
    subprocess.run(command, cwd=source, check=True)
    scripts = destination / 'bin'
    scripts.mkdir()
    binary = scripts / 'monty'
    shutil.copy2(source / 'target/release/monty', binary)
    response = subprocess.run([str(binary), '--version'], capture_output=True, text=True, check=True)
    metadata = {
        'label': 'monty-main', 'source_repository': 'https://github.com/pydantic/monty',
        'source_ref': 'main', 'revision': revision, 'build_command': command,
        'rustc_version': subprocess.check_output(['rustc', '--version'], cwd=source, text=True).strip(),
        'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
        'version': (response.stdout + response.stderr).strip(),
    }
    (destination / 'package.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print(f'monty-main: {metadata["version"]} ({revision})', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    build(args.source, args.output)
