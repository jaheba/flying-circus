import hashlib
import json
import subprocess
import sys
from pathlib import Path


def prepare_benchmarks(paths, output, timeout, defaults):
    manifest = dict(defaults)
    sources = []
    names = set(manifest)
    for argument in paths:
        source = Path(argument).expanduser().resolve(strict=True)
        if not source.is_file() or source.suffix != '.py':
            raise ValueError(f'Custom benchmark must be a Python file: {source}')
        name = source.stem
        if name in names:
            raise ValueError(f'Duplicate benchmark name: {name}; rename the custom file')
        names.add(name)
        sources.append((name, source, source.read_bytes()))
    folder = output / 'workloads'
    folder.mkdir()
    for name, source, contents in sources:
        snapshot = folder / source.name
        snapshot.write_bytes(contents)
        response = subprocess.run([sys.executable, '-I', str(snapshot)], capture_output=True,
                                  text=True, timeout=timeout, check=True)
        if response.stderr:
            raise ValueError(f'{name}: reference run wrote stderr: {response.stderr}')
        manifest[name] = {'file': str(snapshot), 'suite': 'custom', 'stdout': response.stdout,
                          'compatibility_probe': True, 'original_source': str(source),
                          'reference_python': sys.version, 'reference_binary': sys.executable,
                          'source_sha256': hashlib.sha256(contents).hexdigest()}
    (output / 'workloads.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest
