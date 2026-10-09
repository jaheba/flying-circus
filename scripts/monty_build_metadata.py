import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

source, output = map(Path, sys.argv[1:])
binary = output.parent / 'monty'
metadata = {
    'label': os.environ['MONTY_LABEL'], 'ref': os.environ['MONTY_REF'],
    'repository': 'https://github.com/pydantic/monty',
    'commit': subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip(),
    'rustc': subprocess.check_output(['rustc', '--version', '--verbose'], text=True).strip(),
    'command': 'cargo build --locked --release -p monty-runtime',
    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
    'version': subprocess.check_output([str(binary.resolve()), '--version'], text=True).strip(),
}
output.write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
