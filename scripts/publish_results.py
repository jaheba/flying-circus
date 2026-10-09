import argparse
import html
import json
import os
import re
import shutil
from pathlib import Path

from flying_circus.export import write_reports
from flying_circus.bench import ROOT, digest
from urllib.parse import quote
from flying_circus.theme import page


def publish(results, site, run_id, monty_packages=None):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
        raise ValueError('Invalid run ID')
    results, site = Path(results), Path(site)
    destination = site / 'runs' / run_id
    if destination.exists():
        raise ValueError('Run already published')
    build = {'workflow_run': os.environ.get('WORKFLOW_RUN'), 'harness_commit': os.environ.get('HARNESS_COMMIT')}
    if monty_packages:
        metadata = {entry['label']: entry for path in Path(monty_packages).glob('*/package.json')
                    for entry in [json.loads(path.read_text())]}
        index = json.loads((results / 'run.json').read_text())
        build['monty_packages'] = []
        for key, runtime in index['runtimes'].items():
            if runtime['engine'] != 'monty':
                continue
            entry = metadata[runtime['label']]
            info = f'Prebuilt PyPI wheel: {entry["package"]}=={entry["package_version"]}; source revision and compiler flags unverified'
            runtime.update(revision=entry['package_version'], build_info=info, version=entry['version'])
            for mode in ('one-shot', 'repeated'):
                path = results / mode / f'{key}.json'
                run = json.loads(path.read_text())
                if run['binary_sha256'] != entry['binary_sha256']:
                    raise ValueError('Installed Monty package differs from measured binary')
                run.update(revision=entry['package_version'], build_info=info, runtime_version=entry['version'])
                path.write_text(json.dumps(run, indent=2) + '\n', encoding='utf-8')
            build['monty_packages'].append(entry)
        (results / 'run.json').write_text(json.dumps(index, indent=2) + '\n', encoding='utf-8')
    repository = os.environ.get('SOURCE_REPOSITORY', 'https://github.com/jaheba/flying-circus').rstrip('/')
    commit = build['harness_commit']
    if commit and re.fullmatch(r'[0-9a-f]{40,64}', commit) and repository.startswith('https://github.com/'):
        manifest = json.loads((ROOT / 'workloads/manifest.json').read_text())
        index = json.loads((results / 'run.json').read_text())
        for mode in ('one-shot', 'repeated'):
            for key in index['runtimes']:
                path = results / mode / f'{key}.json'
                run = json.loads(path.read_text())
                for name, record in run['benchmarks'].items():
                    source = manifest.get(name, {}).get('file')
                    if source:
                        if digest(ROOT / 'workloads' / source) != record['workload_sha256']:
                            raise ValueError(f'{name}: source differs from measured workload')
                        record['source_url'] = f'{repository}/blob/{commit}/src/flying_circus/workloads/{quote(source)}'
                path.write_text(json.dumps(run, indent=2) + '\n', encoding='utf-8')
    (results / 'build.json').write_text(json.dumps(build, indent=2) + '\n', encoding='utf-8')
    write_reports(results, ['html', 'markdown', 'json'])
    shutil.copytree(results, destination)
    manifest_path = site / 'history.json'
    history = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    index = json.loads((results / 'run.json').read_text())
    history.insert(0, {'id': run_id, 'timestamp': index['timestamp'], **build})
    for entry in history[90:]:
        old_id = entry['id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', old_id):
            raise ValueError('Invalid archived run ID')
        shutil.rmtree(site / 'runs' / old_id, ignore_errors=True)
    history = history[:90]
    manifest_path.write_text(json.dumps(history, indent=2) + '\n', encoding='utf-8')
    esc = html.escape
    navigation = (f'<p><a href="archive.html">Run history</a> · '
                  f'<a href="runs/{run_id}/report.md">Markdown</a> · '
                  f'<a href="runs/{run_id}/report.json">JSON</a></p>'
                  f'<details><summary>Published run</summary><p>Measured {esc(index["timestamp"])} · GitHub-hosted runner'
                  ' (hardware varies between runs; use within-run comparisons)</p>')
    for entry in build.get('monty_packages', []):
        package, version = entry['package'], entry['package_version']
        navigation += f'<p>{esc(entry["label"])}: <a href="https://pypi.org/project/{esc(package)}/{esc(version)}/">{esc(package)} {esc(version)}</a></p>'
    navigation += '</details>'
    document = (destination / 'report.html').read_text()
    (site / 'index.html').write_text(document.replace('<main>', '<main>' + navigation, 1), encoding='utf-8')
    archive = '<h1>Benchmark history</h1><p><a href="index.html">Latest comparison</a></p><ul>'
    for entry in history:
        archive += f'<li><a href="runs/{esc(entry["id"])}/report.html">{esc(entry["timestamp"])}</a>'
        archive += '</li>'
    (site / 'archive.html').write_text(page('Benchmark history', archive + '</ul>'), encoding='utf-8')
    (site / '.nojekyll').touch()


def main():
    parser = argparse.ArgumentParser(description='Build a Pages site from benchmark results, retaining the latest 90 runs')
    parser.add_argument('results', type=Path)
    parser.add_argument('site', type=Path)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--monty-packages', type=Path)
    args = parser.parse_args()
    publish(args.results, args.site, args.run_id, args.monty_packages)


if __name__ == '__main__':
    main()
