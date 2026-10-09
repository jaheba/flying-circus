import argparse
import html
import json
import platform
from pathlib import Path

from .compare import compare_runs
from .machine import cpu_info
from .formatting import measurement, runtime_description, winners
from .theme import page


def render(directory):
    directory = Path(directory)
    modes = {}
    for mode in ('one-shot', 'repeated'):
        folder = directory / mode
        runs = {engine: json.loads((folder / f'{engine}.json').read_text())
                for engine in ('monty', 'cpython', 'pypy') if (folder / f'{engine}.json').exists()}
        if not {'monty', 'cpython'} <= runs.keys():
            raise ValueError(f'{mode}: Monty and CPython results are required')
        modes[mode] = (runs, compare_runs(runs['monty'], runs['cpython'], runs.get('pypy')))
    first = modes['one-shot'][0]
    second = modes['repeated'][0]
    if first.keys() != second.keys():
        raise ValueError('Scenarios must contain the same engines')
    for engine in first:
        for field in ('machine', 'platform', 'architecture', 'binary_sha256', 'harness_sha256',
                      'memory_helper_sha256', 'harness_python'):
            if first[engine][field] != second[engine][field]:
                raise ValueError(f'{engine}: scenarios differ in {field}')
        before, after = first[engine]['benchmarks'], second[engine]['benchmarks']
        if before.keys() != after.keys():
            raise ValueError('Scenarios must contain the same workloads')
        for name in before:
            if before[name]['scenario'] != 'warm_worker_one_shot' or after[name]['scenario'] != 'repeated_requests':
                raise ValueError('Expected ready-worker one-shot and repeated scenarios')
            for field in ('workload_sha256', 'expected_sha256'):
                if before[name][field] != after[name][field]:
                    raise ValueError(f'{name}: scenarios differ in {field}')
    escape = lambda value: html.escape(str(value))
    run = first['monty']
    cpu = run.get('cpu')
    if not cpu and (run['machine'], run['platform'], run['architecture']) == (
            platform.node(), platform.platform(), platform.machine()):
        cpu = cpu_info() + ' (report host; not recorded during run)'
    facts = [('CPU', cpu or 'Not recorded'), ('OS', run['platform']),
             ('Samples', run['configuration']['samples']), ('Architecture', run['architecture']), ('Machine', run['machine'])]
    for mode, (runs, _) in modes.items():
        config = runs['monty']['configuration']
        facts.append((mode.title(), f'{config["samples"]} samples · {config.get("warmups", 0)} warmups'))
    facts += [('Timing', 'Median ms · worker startup excluded · fresh session per request'),
              ('RSS', 'Median MiB · whole interpreter process including startup'),
              ('RSS samples', f'{run["configuration"].get("memory_samples", 0)} per workload · separate one-shot runs · repeated n/a'),
              ('Sort', 'Click column headers')]
    if any(bench.get('input_bytes') for bench in run['benchmarks'].values()):
        facts.append(('Text inputs', 'Small ≈10 KB · medium ≈1 MB · fixture setup excluded from request timing'))
    document = '<h1>Application benchmarks</h1><dl class="facts">'
    document += ''.join(f'<div><dt>{escape(key)}</dt><dd>{escape(value)}</dd></div>' for key, value in facts[:3])
    document += '</dl>'
    document += '<details><summary>Measurement details</summary><dl class="facts">'
    document += ''.join(f'<div><dt>{escape(key)}</dt><dd>{escape(value)}</dd></div>' for key, value in facts[3:]) + '</dl></details>'
    document += '<details><summary>Versions and build details</summary>'
    for engine, result in first.items():
        document += f'<p><strong>{escape(engine)}</strong> · {escape(result["revision"])}<br>{escape(result["build_info"])}<br>'
        document += f'<code>{escape(result["binary_sha256"])}</code></p>'
    for mode, (runs, _) in modes.items():
        document += f'<p>{escape(mode)} · {escape(runs["monty"]["timestamp"])}</p>'
    document += '</details>'
    labels = {'monty': 'Monty', 'cpython': 'CPython', 'pypy': 'PyPy'}
    def header(engine):
        return f'<th>{labels[engine]}</th>'
    document += '<p class="runtime-info">' + ' · '.join(escape(runtime_description({'label': engine, 'engine': engine}, result)) for engine, result in first.items()) + '</p>'
    startup_path = directory / 'startup.json'
    if startup_path.exists():
        startup = json.loads(startup_path.read_text())
        for field in ('machine', 'platform', 'architecture'):
            if startup[field] != run[field]:
                raise ValueError(f'Startup differs in {field}')
        if startup.get('scenario') != 'empty_command_process':
            raise ValueError('Expected empty-command startup measurements')
        if startup['engines'].keys() != first.keys():
            raise ValueError('Startup must contain the same engines')
        document += '<h2>Process startup · ms</h2><p>Empty <code>-c ""</code> command · launch through exit · normal interpreter defaults · '
        document += f'{startup["samples"]} samples · measured separately</p><div class="table-wrap"><table><thead><tr>'
        document += ''.join(header(engine) for engine in first)
        document += '</tr></thead><tbody><tr>'
        displays = {}
        for engine in first:
            entry = startup['engines'][engine]
            if entry['binary_sha256'] != first[engine]['binary_sha256']:
                raise ValueError(f'{engine}: startup binary differs')
            displays[engine] = measurement(entry['median_wall_seconds'] * 1000, 'ms')
        best = winners(displays)
        for engine in first:
            display = f'<strong>{displays[engine]}</strong>' if engine in best else displays[engine]
            document += f'<td>{display}</td>'
        document += '</tr></tbody></table></div>'
    for metric, title in (('ms', 'Runtime · ms'), ('rss_mib', 'Peak RSS · MiB')):
        selected = ['one-shot', 'repeated'] if metric == 'ms' else ['one-shot']
        paired = metric == 'ms'
        document += f'<h2>{title}' + (' · one-shot / repeated' if paired else ' · one-shot') + '</h2>'
        document += '<div class="table-wrap"><table' + (' data-paired="true"' if paired else '') + '><thead><tr><th>Workload</th>'
        document += ''.join(header(engine) for engine in first)
        document += '</tr></thead><tbody>'
        lookup = {mode: {row['workload']: row for row in rows} for mode, (_, rows) in modes.items()}
        for name in run['benchmarks']:
            if name == 'startup':
                continue
            source = run['benchmarks'][name].get('source_url', '')
            label = f'<a href="{escape(source)}">{escape(name)}</a>' if source.startswith('https://github.com/') else escape(name)
            document += f'<tr><td>{label}</td>'
            for engine in first:
                parts, plain, reasons = [], [], []
                for mode in selected:
                    row = lookup[mode][name]
                    value = row[engine + '_' + metric]
                    display = measurement(value, metric)
                    plain.append(display)
                    available = {e: measurement(row[e + '_' + metric], metric) for e in first}
                    if engine in winners(available):
                        display = f'<strong>{display}</strong>'
                    parts.append(display)
                    if value is None and row[engine + '_reason']:
                        reasons.append(mode + ': ' + row[engine + '_reason'])
                attributes = f' title="{escape("; ".join(reasons))}"' if reasons else ''
                if paired:
                    attributes += f' data-one-shot="{escape(plain[0])}" data-repeated="{escape(plain[1])}"'
                document += f'<td{attributes}>' + ' / '.join(parts) + '</td>'
            document += '</tr>'
        document += '</tbody></table></div>'
    return page('Application benchmarks', document)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Unified one-shot and repeated benchmark report')
    parser.add_argument('directory', type=Path, help='Contains one-shot/ and repeated/ result directories')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        document = render(args.directory)
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as destination:
        destination.write(document)
