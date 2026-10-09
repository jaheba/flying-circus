import argparse
import html
import json
from pathlib import Path

from .theme import page
from .formatting import measurement


def compare_runs(monty, cpython, pypy=None):
    for field in ('schema_version', 'machine', 'platform', 'architecture', 'harness_sha256',
                  'memory_helper_sha256', 'harness_python', 'memory_method'):
        if monty[field] != cpython[field]:
            raise ValueError(f'Runs differ in {field}')
    for field in ('warmups', 'timeout'):
        if monty.get('configuration', {}).get(field) != cpython.get('configuration', {}).get(field):
            raise ValueError(f'Runs differ in {field}')
    if monty['schema_version'] != 1:
        raise ValueError('Unsupported result schema')
    if monty['benchmarks'].keys() != cpython['benchmarks'].keys():
        raise ValueError('Runs must contain the same workloads')
    rows = []
    for name, left in monty['benchmarks'].items():
        right = cpython['benchmarks'][name]
        for field in ('scenario', 'workload_sha256', 'expected_sha256'):
            if left[field] != right[field]:
                raise ValueError(f'{name}: runs differ in {field}')
        if left['status'] not in ('ok', 'unsupported') or right['status'] not in ('ok', 'unsupported'):
            raise ValueError(f'{name}: cannot compare failed runs')
        m_time, c_time = left['median_wall_seconds'], right['median_wall_seconds']
        for result, value in ((left, m_time), (right, c_time)):
            if result['status'] == 'ok' and (value is None or value <= 0):
                raise ValueError(f'{name}: positive latency measurements required')
        rows.append({
            'workload': name, 'monty_ms': m_time * 1000 if left['status'] == 'ok' else None,
            'cpython_ms': c_time * 1000 if right['status'] == 'ok' else None,
            'latency_ratio': m_time / c_time if left['status'] == right['status'] == 'ok' else None,
            'monty_status': left['status'], 'cpython_status': right['status'],
            'monty_reason': left.get('compatibility', {}).get('reason', ''),
            'cpython_reason': right.get('compatibility', {}).get('reason', ''),
            'monty_rss_mib': left['median_peak_rss_bytes'] / 1048576 if left['median_peak_rss_bytes'] is not None else None,
            'cpython_rss_mib': right['median_peak_rss_bytes'] / 1048576 if right['median_peak_rss_bytes'] is not None else None,
        })
    if pypy is not None:
        pypy_rows = compare_runs(monty, pypy)
        for row, pypy_row in zip(rows, pypy_rows):
            row['pypy_status'] = pypy_row['cpython_status']
            row['pypy_reason'] = pypy_row['cpython_reason']
            row['pypy_ms'] = pypy_row['cpython_ms']
            row['pypy_rss_mib'] = pypy_row['cpython_rss_mib']
            row['monty_pypy_ratio'] = pypy_row['latency_ratio']
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description='Compare Monty, CPython and optional PyPy results')
    parser.add_argument('--monty-results', type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--cpython-results', type=Path)
    group.add_argument('--candidate-results', type=Path, help='Results from a second Monty binary')
    parser.add_argument('--pypy-results', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    monty = json.loads(args.monty_results.read_text())
    cpython = json.loads((args.candidate_results or args.cpython_results).read_text())
    if args.candidate_results and any(run.get('engine') != 'monty' for run in (monty, cpython)):
        parser.error('Version comparisons require two Monty runs')
    if args.candidate_results and args.pypy_results:
        parser.error('--candidate-results cannot be combined with --pypy-results')
    pypy = json.loads(args.pypy_results.read_text()) if args.pypy_results else None
    try:
        rows = compare_runs(monty, cpython, pypy)
    except ValueError as error:
        parser.error(str(error))
    escape = lambda value: html.escape(str(value))
    engines = [('Monty', 'monty', monty), ('CPython', 'cpython', cpython)]
    if args.candidate_results:
        engines = [('Baseline Monty', 'monty', monty), ('Candidate Monty', 'cpython', cpython)]
    if pypy is not None:
        engines.append(('PyPy', 'pypy', pypy))
    tables = []
    for metric, heading in (('ms', 'Runtime · ms'), ('rss_mib', 'Peak RSS · MiB')):
        headers = ['Workload'] + [label for label, _, _ in engines]
        if args.candidate_results and metric == 'ms':
            headers.append('Time change %')
        body = []
        for row in rows:
            if row['workload'] == 'startup':
                continue
            measured = [float(measurement(row[key + '_' + metric], metric)) for _, key, _ in engines
                        if row[key + '_' + metric] is not None]
            best = min(measured) if measured else None
            cells = [f'<td>{escape(row["workload"])}</td>']
            for _, key, _ in engines:
                value = row[key + '_' + metric]
                display = measurement(value, metric)
                reason = row[key + '_reason'] if value is None else ''
                title_attr = f' title="{escape(reason)}"' if reason else ''
                if value is not None and float(display) == best:
                    display = f'<strong>{display}</strong>'
                cells.append(f'<td{title_attr}>{display}</td>')
            if args.candidate_results and metric == 'ms':
                before, after = row['monty_ms'], row['cpython_ms']
                change = f'{(after / before - 1) * 100:+.2f}%' if before and after else 'n/a'
                cells.append(f'<td>{change}</td>')
            body.append('<tr>' + ''.join(cells) + '</tr>')
        tables.append(f'<h2>{heading}</h2><div class="table-wrap"><table><thead><tr>'
                      + ''.join('<th scope="col">' + escape(header) + '</th>' for header in headers)
                      + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table></div>')
    scenarios = ', '.join(sorted({b['scenario'] for b in monty['benchmarks'].values()}))
    title = ' vs '.join(label for label, _, _ in engines)
    facts = [('CPU', monty.get('cpu', 'Not recorded')), ('OS', monty['platform']),
             ('Machine', monty['machine']), ('Architecture', monty['architecture']),
             ('Scenario', scenarios), ('Samples', monty['configuration'].get('samples', 'n/a')),
             ('Warmups', monty['configuration'].get('warmups', 0)),
             ('Timing', 'Median ms'), ('RSS', 'Median MiB · whole interpreter process · separate runs'),
             ('Sort', 'Click column headers'), ('Winners', 'Lowest value · ties at displayed precision')]
    if args.candidate_results:
        facts.append(('Time change', 'Candidate vs baseline · negative means faster'))
    document = f'<h1>{escape(title)}</h1><dl class="facts">'
    document += ''.join(f'<div><dt>{escape(key)}</dt><dd>{escape(value)}</dd></div>' for key, value in facts)
    document += '</dl><details><summary>Versions and build details</summary>'
    document += ''.join(
        f'<p>{escape(label)} · {escape(run["revision"])} · {escape(run["timestamp"])}<br>'
        f'{escape(run["build_info"])}</p>' for label, _, run in engines)
    document += '</details>'
    document += ''.join(tables)
    document = page(title, document)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as destination:
        destination.write(document)


if __name__ == '__main__':
    main()
