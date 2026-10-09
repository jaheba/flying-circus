import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

RELEASES = {'monty': None}


def install(output, python):
    output = Path(output)
    for label, version in RELEASES.items():
        environment = output / label
        if environment.exists():
            raise ValueError(f'Runtime environment already exists: {environment}')
        subprocess.run(['uv', 'venv', '--python', str(python), str(environment)], check=True)
        scripts = environment / ('Scripts' if os.name == 'nt' else 'bin')
        interpreter = scripts / ('python.exe' if os.name == 'nt' else 'python')
        binary = scripts / ('monty.exe' if os.name == 'nt' else 'monty')
        package = 'pydantic-monty-runtime'
        command = ['uv', 'pip', 'install', '--python', str(interpreter), '--only-binary', ':all:',
                   '--index-url', 'https://pypi.org/simple', '--refresh-package', package, f'{package}=={version}' if version else package]
        subprocess.run(command, check=True)
        installed = subprocess.check_output([str(interpreter), '-c',
            'from importlib.metadata import version; print(version("pydantic-monty-runtime"))'], text=True).strip()
        if version and installed != version:
            raise ValueError(f'Expected {version}, installed {installed}')
        response = subprocess.run([str(binary), '--version'], capture_output=True, text=True, check=True)
        metadata = {'label': label, 'package': package, 'package_version': installed,
                    'index': 'https://pypi.org/simple', 'install_command': command,
                    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                    'version': (response.stdout + response.stderr).strip()}
        (environment / 'package.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
        print(f'{label}: {metadata["version"]} ({binary})', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Install released Monty executables from binary-only PyPI wheels')
    parser.add_argument('--python', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    install(args.output, args.python)
