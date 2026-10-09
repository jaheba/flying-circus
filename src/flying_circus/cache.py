import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .bench import digest


def cache_root():
    if sys.platform == 'darwin':
        base = Path.home() / 'Library/Caches'
    elif sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local'))
    else:
        base = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
    return base / 'flying-circus/runtimes'


def entry(name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name):
        raise ValueError('Cache names must contain letters, numbers, dots, hyphens or underscores')
    return cache_root() / name


def cached_binary(name):
    folder = entry(name)
    metadata = json.loads((folder / 'metadata.json').read_text())
    binary = folder / ('monty.exe' if os.name == 'nt' else 'monty')
    if digest(binary) != metadata['sha256']:
        raise ValueError(f'Cached runtime {name} has changed; cache it again with --replace')
    return binary


def save(name, executable, replace=False):
    from .runtimes import resolve

    destination = entry(name)
    if destination.exists() and not replace:
        raise ValueError(f'Cache {name} already exists; use --replace to update it')
    runtime = resolve(str(executable))
    if runtime['engine'] != 'monty':
        raise ValueError('Only Monty binaries can be saved in the build cache')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staged = Path(temporary) / 'runtime'
        staged.mkdir()
        binary = staged / ('monty.exe' if os.name == 'nt' else 'monty')
        shutil.copy2(runtime['binary'], binary)
        if digest(binary) != digest(runtime['binary']):
            raise ValueError('Source binary changed while caching; retry after the build finishes')
        metadata = {'source': str(runtime['binary']), 'version': runtime['version'], 'sha256': digest(binary),
                    'created': datetime.now(timezone.utc).isoformat()}
        (staged / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
        if destination.exists():
            # Preserve the previous snapshot until the replacement is fully prepared.
            backup = Path(temporary) / 'previous'
            destination.rename(backup)
            try:
                staged.rename(destination)
            except OSError:
                backup.rename(destination)
                raise
        else:
            staged.rename(destination)
    return cached_binary(name)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Save and reuse named Monty binary snapshots')
    parser.add_argument('name', nargs='?')
    parser.add_argument('binary', nargs='?')
    parser.add_argument('--replace', action='store_true', help='Replace an existing snapshot')
    parser.add_argument('--list', action='store_true', help='List cached snapshots')
    args = parser.parse_args(argv)
    try:
        if args.list:
            if args.name or args.binary or args.replace:
                parser.error('--list cannot be combined with other arguments')
            for folder in sorted(cache_root().glob('*')):
                if (folder / 'metadata.json').is_file():
                    metadata = json.loads((folder / 'metadata.json').read_text())
                    print(f'{folder.name}: {metadata["version"]} ({metadata["created"]})')
            return 0
        if not args.name or not args.binary:
            parser.error('Provide a cache name and a Monty executable, or --list')
        binary = save(args.name, args.binary, args.replace)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.error(str(error))
    print(f'{args.name}: {binary}\nUse -r {args.name}=@{args.name}')
    return 0
