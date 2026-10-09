import html
import json
from pathlib import Path

from .differences import difference
from .formatting import measurement, runtime_description, runtime_label, winners
from .theme import page

MODES = ('one-shot', 'repeated')


def load(directory):
    directory = Path(directory)
    index = json.loads((directory / 'run.json').read_text())
    runs = {mode: {key: json.loads((directory / mode / f'{key}.json').read_text())
                   for key in index['runtimes']} for mode in MODES}
    first = next(iter(runs['one-shot'].values()))
    for mode in MODES:
        for key, run in runs[mode].items():
            reference = runs['one-shot'][key]
            for field in ('binary_sha256', 'machine', 'platform', 'architecture', 'harness_sha256', 'memory_helper_sha256'):
                if run[field] != reference[field]:
                    raise ValueError(f'{key}: scenarios differ in {field}')
            for field in ('machine', 'platform', 'architecture', 'harness_sha256', 'memory_helper_sha256'):
                if run[field] != first[field]:
                    raise ValueError(f'Runs differ in {field}')
            if run['benchmarks'].keys() != first['benchmarks'].keys():
                raise ValueError('Runs differ in workloads')
            for name, bench in run['benchmarks'].items():
                for field in ('workload_sha256', 'expected_sha256'):
                    if bench[field] != first['benchmarks'][name][field]:
                        raise ValueError(f'{name}: runs differ in {field}')
    startup = json.loads((directory / 'startup.json').read_text())
    for key, entry in startup.get('engines', {}).items():
        if entry['binary_sha256'] != runs['one-shot'][key]['binary_sha256']:
            raise ValueError('Startup binary differs')
    return index, runs, startup


def entries(index, runs, startup):
    keys = list(index['runtimes'])
    for name in next(iter(runs['one-shot'].values()))['benchmarks']:
        for mode in MODES:
            records = {key: runs[mode][key]['benchmarks'][name] for key in keys}
            yield name, mode, 'ms', records, 'wall_seconds', 1000
        records = {key: runs['one-shot'][key]['benchmarks'][name] for key in keys}
        yield name, 'one-shot', 'rss_mib', records, 'peak_rss_bytes', 1 / 1048576
    records = {key: dict(entry, status='failed' if entry.get('errors') else 'ok')
               for key, entry in startup.get('engines', {}).items()}
    if records:
        yield 'Process startup', 'empty command', 'ms', records, 'wall_seconds', 1000


def diff_results(index, runs, startup, threshold, absolute_ms):
    keys = list(index['runtimes'])
    baseline = keys[0]
    measured = list(entries(index, runs, startup))
    comparisons = sum(
        bool(records[baseline].get(field)) and bool(records[key].get(field))
        for _, _, _, records, field, _ in measured for key in keys[1:])
    results = []
    for name, mode, metric, records, field, scale in measured:
        before = records[baseline]
        for key in keys[1:]:
            after = records[key]
            row = {'workload': name, 'scenario': mode, 'metric': metric,
                   'baseline_label': index['runtimes'][baseline]['label'], 'candidate_label': index['runtimes'][key]['label']}
            if before['status'] == 'failed' or after['status'] == 'failed':
                outcome = {'status': 'failure', 'reason': str(after.get('errors') or before.get('errors'))}
            elif before['status'] != after['status']:
                outcome = {'status': 'compatibility change', 'reason': before['status'] + ' → ' + after['status']}
            elif before['status'] != 'ok':
                outcome = {'status': 'unchanged'}
            else:
                outcome = difference([v * scale for v in before[field]], [v * scale for v in after[field]],
                                     threshold=threshold, absolute=absolute_ms if metric == 'ms' else 0,
                                     trials=max(4000, comparisons * 100), comparisons=max(1, comparisons))
            row.update(outcome)
            results.append(row)
    return results


def render(directory, diff=False, threshold=5, absolute_ms=0.01):
    index, runs, startup = load(directory)
    keys = list(index['runtimes'])
    first = runs['one-shot'][keys[0]]
    esc = lambda value: html.escape(str(value))
    title = 'Performance changes' if diff else 'Application benchmarks'
    facts = [('CPU', first.get('cpu', 'Not recorded')), ('OS', first['platform']),
             ('Samples', first['configuration']['samples']), ('Repeated warmups', runs['repeated'][keys[0]]['configuration']['warmups']),
             ('Timing', 'Median ms · one-shot / repeated · startup excluded'),
             ('RSS', 'Median MiB · separate one-shot processes including startup'),
             ('Startup', 'Empty -c command · launch through exit · normal defaults'),
             ('Sort', 'Click column headers')]
    if diff:
        facts += [('Reference', index['runtimes'][keys[0]]['label']),
                  ('Threshold', f'{threshold:g}% and {absolute_ms:g} ms for timings'),
                  ('Evidence', 'Bootstrap median-ratio bounds · 95% family level · Bonferroni correction')]
    document = f'<h1>{title}</h1><dl class="facts">'
    document += ''.join(f'<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in facts[:3]) + '</dl>'
    document += '<details><summary>Measurement details</summary><dl class="facts">'
    document += ''.join(f'<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in facts[3:]) + '</dl></details>'
    def header(key):
        return f'<th>{esc(runtime_label(index["runtimes"][key]))}</th>'
    document += '<p class="runtime-info">' + ' · '.join(esc(runtime_description(index['runtimes'][key], runs['one-shot'][key])) for key in keys) + '</p>'
    document += '<details><summary>Runtimes and build details</summary>'
    for key in keys:
        runtime = index['runtimes'][key]
        run = runs['one-shot'][key]
        document += f'<p><strong>{esc(runtime["label"])}</strong> · {esc(run["engine"])} · {esc(run["revision"])}<br>'
        document += f'{esc(run["configuration"]["binary"])}<br>{esc(run["build_info"])}<br><code>{run["binary_sha256"]}</code></p>'
    document += '</details>'
    if diff:
        changes = diff_results(index, runs, startup, threshold, absolute_ms)
        visible = [row for row in changes if row['status'] not in ('unchanged', 'unavailable', 'inconclusive')]
        order = {'failure': 0, 'compatibility change': 1, 'regression': 2, 'improvement': 3, 'inconclusive': 4}
        visible.sort(key=lambda row: (order[row['status']], -abs(row.get('change_percent', 0))))
        if not visible:
            document += '<p>No significant changes detected.</p>'
        inconclusive = sum(row['status'] == 'inconclusive' for row in changes)
        document += f'<p>{len(changes)} comparisons · {len(visible)} changes or failures · {inconclusive} inconclusive (see diff.json)</p>'
        if visible:
            document += '<div class="table-wrap"><table><thead><tr>'
            headers = ('Workload', 'Scenario', 'Metric', 'Candidate', 'Result', 'Baseline', 'Candidate value', 'Change', 'Bounds / reason')
            document += ''.join(f'<th>{h}</th>' for h in headers) + '</tr></thead><tbody>'
            for row in visible:
                metric = row['metric']
                bounds = row.get('interval_percent')
                detail = f'{bounds[0]:+.1f}% to {bounds[1]:+.1f}%' if bounds else row.get('reason', '')
                fields = (row['workload'], row['scenario'], 'ms' if metric == 'ms' else 'RSS MiB', row['candidate_label'],
                          row['status'], measurement(row.get('baseline') if isinstance(row.get('baseline'), (int, float)) else None, metric),
                          measurement(row.get('candidate') if isinstance(row.get('candidate'), (int, float)) else None, metric),
                          f'{row["change_percent"]:+.1f}%' if 'change_percent' in row else 'n/a', detail)
                source = first['benchmarks'].get(row['workload'], {}).get('source_url', '')
                cells = [esc(v) for v in fields]
                if source.startswith('https://github.com/'):
                    cells[0] = f'<a href="{esc(source)}">{cells[0]}</a>'
                document += '<tr>' + ''.join(f'<td>{v}</td>' for v in cells) + '</tr>'
            document += '</tbody></table></div>'
        document += '<p>Inconclusive changes are recorded in diff.json and excluded from this table. Bootstrap bounds are estimates; repeat runs when results are borderline.</p>'
        return page(title, document), changes
    if startup.get('engines'):
        document += '<h2>Process startup · ms</h2><div class="table-wrap"><table><thead><tr>'
        document += ''.join(header(key) for key in keys) + '</tr></thead><tbody><tr>'
        values = {key: measurement(entry.get('median_wall_seconds') * 1000, 'ms') if not entry.get('errors') else 'n/a'
                  for key, entry in startup['engines'].items()}
        best = winners(values)
        for key in keys:
            text = f'<strong>{values[key]}</strong>' if key in best else values[key]
            document += f'<td>{text}</td>'
        document += '</tr></tbody></table></div>'
    workload_names = list(first['benchmarks'])
    for metric, heading in (('ms', 'Runtime · ms · one-shot / repeated'), ('rss_mib', 'Peak RSS · MiB · one-shot')):
        paired = metric == 'ms'
        document += f'<h2>{heading}</h2><div class="table-wrap"><table' + (' data-paired="true"' if paired else '') + '><thead><tr><th>Workload</th>'
        document += ''.join(header(key) for key in keys) + '</tr></thead><tbody>'
        for name in workload_names:
            source = first['benchmarks'][name].get('source_url', '')
            label = f'<a href="{esc(source)}">{esc(name)}</a>' if source.startswith('https://github.com/') else esc(name)
            document += f'<tr><td>{label}</td>'
            for key in keys:
                plain, parts, reasons = [], [], []
                for mode in MODES if paired else ('one-shot',):
                    record = runs[mode][key]['benchmarks'][name]
                    field = 'median_wall_seconds' if paired else 'median_peak_rss_bytes'
                    scale = 1000 if paired else 1 / 1048576
                    value = record[field] * scale if record['status'] == 'ok' and record[field] is not None else None
                    text = measurement(value, metric)
                    plain.append(text)
                    available = {other: measurement(runs[mode][other]['benchmarks'][name][field] * scale, metric)
                                 for other in keys if runs[mode][other]['benchmarks'][name]['status'] == 'ok'
                                 and runs[mode][other]['benchmarks'][name][field] is not None}
                    if key in winners(available):
                        text = f'<strong>{text}</strong>'
                    if record['status'] == 'failed':
                        text = 'failed'
                    parts.append(text)
                    if record['status'] != 'ok':
                        reasons.append(mode + ': ' + str(record.get('errors') or record.get('compatibility', {}).get('reason', '')))
                attrs = f' title="{esc("; ".join(reasons))}"' if reasons else ''
                if paired:
                    attrs += f' data-one-shot="{plain[0]}" data-repeated="{plain[1]}"'
                document += f'<td{attrs}>' + ' / '.join(parts) + '</td>'
            document += '</tr>'
        document += '</tbody></table></div>'
    return page(title, document), None
