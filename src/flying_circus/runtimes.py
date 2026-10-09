import os
import re
import shutil
import subprocess
from pathlib import Path

from .bench import validate


def resolve(spec, timeout=30):
    if '=' in spec:
        label, executable = spec.split('=', 1)
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', label):
            raise ValueError('Runtime labels must contain letters, numbers, dots, hyphens or underscores')
    else:
        executable = spec
        label = Path(executable).name
    executable = os.path.expanduser(executable)
    found = shutil.which(executable)
    if not found:
        raise ValueError(f'Runtime executable not found: {executable}')
    binary = Path(found).resolve(strict=True)
    response = subprocess.run([str(binary), '--version'], capture_output=True, text=True, timeout=timeout, check=True)
    version = (response.stdout + response.stderr).strip()
    if 'monty' in version.lower():
        engine = 'monty'
    else:
        response = subprocess.run([str(binary), '-c', 'import sys; print(sys.implementation.name)'],
                                  capture_output=True, text=True, timeout=timeout, check=True)
        engine = response.stdout.strip()
        if engine not in ('cpython', 'pypy'):
            raise ValueError(f'Unsupported runtime type: {engine or version}')
    response = subprocess.run([str(binary), '-c', ''], capture_output=True, text=True, timeout=timeout)
    validate(response, '', engine == 'monty')
    return {'label': label, 'binary': binary, 'engine': engine, 'version': version, 'revision': version,
            'build_info': 'Source revision and compiler flags unverified',
            'legacy_cli_summary': engine == 'monty' and bool(response.stdout)}


def resolve_all(specs, timeout=30):
    runtimes = {}
    labels = set()
    for index, spec in enumerate(specs):
        runtime = resolve(spec, timeout)
        if runtime['label'] in labels:
            raise ValueError(f'Duplicate runtime label: {runtime["label"]}; use distinct label=executable arguments')
        labels.add(runtime['label'])
        runtimes[f'runtime_{index}'] = runtime
    return runtimes
