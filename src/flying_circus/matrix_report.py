import html
import json
from pathlib import Path

from .charts import advantage_order, chart_reference, inline_chart, relative_values
from .differences import difference
from .formatting import duration, measurement, runtime_description, runtime_label, winners, paired_measurements
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
            if run['configuration'].get('arguments', []) != reference['configuration'].get('arguments', []):
                raise ValueError(f'{key}: scenarios differ in runtime arguments')
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
             ('Samples', first['configuration']['samples']), ('Parallel jobs', index.get('options', {}).get('x', 1)), ('Run duration', duration(index.get('elapsed_seconds'))), ('Repeated warmups', runs['repeated'][keys[0]]['configuration']['warmups']),
             ('Timing', 'Median ms · one-shot / repeated · startup excluded'),
             ('RSS', 'Median MiB · separate one-shot processes including startup'),
             ('Startup', 'Empty -c command · launch through exit · normal defaults'),
             ('Sort', 'Percentage advantage vs chart reference · largest improvement first; click headers to reorder')]
    if diff:
        facts += [('Reference', index['runtimes'][keys[0]]['label']),
                  ('Threshold', f'{threshold:g}% and {absolute_ms:g} ms for timings'),
                  ('Evidence', 'Bootstrap median-ratio bounds · 95% family level · Bonferroni correction')]
    document = f'<h1>{title}</h1>'
    if index.get('options', {}).get('quick'):
        document += '<p>Quick run · reduced sampling for a rough comparison. Repeat with default settings to confirm changes.</p>'
    document += '<dl class="facts">'
    document += ''.join(f'<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in facts[:5]) + '</dl>'
    document += '<details><summary>Measurement details</summary><dl class="facts">'
    document += ''.join(f'<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in facts[5:]) + '</dl></details>'
    def header(key):
        return f'<th>{esc(runtime_label(index["runtimes"][key]))}</th>'
    document += '<p class="runtime-info">' + ' · '.join(esc(runtime_description(index['runtimes'][key], runs['one-shot'][key])) for key in keys) + '</p>'
    document += '<details><summary>Runtimes and build details</summary>'
    for key in keys:
        runtime = index['runtimes'][key]
        run = runs['one-shot'][key]
        document += f'<p><strong>{esc(runtime["label"])}</strong> · {esc(run["engine"])} · {esc(run["revision"])}<br>'
        document += f'{esc(run["configuration"]["binary"])} {esc(" ".join(run["configuration"].get("arguments", [])))}<br>{esc(run["build_info"])}<br><code>{run["binary_sha256"]}</code></p>'
    document += '</details>'
    changes = diff_results(index, runs, startup, threshold, absolute_ms) if diff else None
    visible = [row for row in changes or [] if row['status'] in ('failure', 'compatibility change', 'regression', 'improvement')]
    if diff:
        index = dict(index, options=dict(index.get('options', {}), chart_baseline=index['runtimes'][keys[0]]['label']))
        if not visible:
            document += '<p>No significant changes detected.</p>'
        inconclusive = sum(row['status'] == 'inconclusive' for row in changes)
        document += f'<p>Reference: {esc(index["runtimes"][keys[0]]["label"])} · {len(visible)} changes or failures · {inconclusive} inconclusive</p>'
        document += '<div class="diff-filter"><label><input type="checkbox" id="significant-only"> Significant changes only</label><span id="benchmark-count" role="status" aria-live="polite"></span></div>'
        document += '<details><summary>Comparison evidence</summary><p>The checkbox filters to meaningful changes, failures or compatibility changes. Paired values include both modes for context. All classifications and confidence bounds are retained in diff.json.</p></details>'
    chart_baseline = chart_reference(index)
    chart_label = index['runtimes'][chart_baseline]['label']
    if startup.get('engines'):
        document += '<section data-diff-section><h2>Process startup · ms</h2><div class="table-wrap"><table class="startup"><thead><tr>'
        document += ''.join(header(key) for key in keys) + '</tr></thead><tbody><tr' + (f' data-significant="{str(any(row["workload"] == "Process startup" for row in visible)).lower()}"' if diff else '') + '>'
        startup_runs = {'startup': {key: {'benchmarks': {'startup': dict(entry, status='failed' if entry.get('errors') else 'ok')}}
                                    for key, entry in startup['engines'].items()}}
        startup_ratios, startup_extent = relative_values(index, startup_runs)
        values = {key: measurement(entry.get('median_wall_seconds') * 1000, 'ms') if not entry.get('errors') and entry.get('median_wall_seconds') is not None else 'n/a'
                  for key, entry in startup['engines'].items()}
        best = winners(values)
        for key in keys:
            text = f'<strong>{values[key]}</strong>' if key in best else values[key]
            chart = inline_chart(startup_ratios.get(('startup', key, 'startup')), startup_extent, 'startup', reference=chart_label) if key != chart_baseline else ''
            document += f'<td><span class="inline-measurement">{text}{chart}</span></td>'
        document += '</tr></tbody></table></div></section>'
    workload_names = list(first['benchmarks'])
    for metric, heading in (('ms', 'Runtime · ms · one-shot / repeated'), ('rss_mib', 'Peak RSS · MiB · one-shot')):
        paired = metric == 'ms'
        ratios, chart_extent = relative_values(index, runs if paired else {'one-shot': runs['one-shot']},
                                               'median_wall_seconds' if paired else 'median_peak_rss_bytes')
        selected_names = workload_names
        if not selected_names:
            continue
        document += f'<section data-diff-section><h2>{heading}</h2>'
        if ratios:
            comparison = 'faster, red below = slower' if paired else 'less memory, red below = more memory'
            document += f'<p class="chart-legend">Bars: {esc(chart_label)} = midpoint · blue above = {comparison} · shared asinh scale (5% transition)</p>'
        document += '<div class="table-wrap"><table' + (' data-paired="true"' if paired else '') + '><thead><tr><th>Workload</th>'
        document += ''.join(header(key) for key in keys) + '</tr></thead><tbody>'
        for name in advantage_order(selected_names, ratios, chart_baseline):
            source = first['benchmarks'][name].get('source_url', '')
            label = f'<a href="{esc(source)}">{esc(name)}</a>' if source.startswith('https://github.com/') else esc(name)
            significant = any(row['workload'] == name and row['metric'] == metric for row in visible)
            filter_attrs = f' data-benchmark="{esc(name)}" data-significant="{str(significant).lower()}"' if diff else ''
            document += f'<tr{filter_attrs}><td>{label}</td>'
            for key in keys:
                plain, parts, reasons, charts = [], [], [], []
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
                    charts.append(inline_chart(ratios.get((mode, key, name)), chart_extent, mode, 'runtime' if paired else 'RSS', reference=chart_label) if key != chart_baseline else '')
                    if diff:
                        for change in changes:
                            if change['workload'] == name and change['metric'] == metric and change['scenario'] == mode and change['candidate_label'] == index['runtimes'][key]['label']:
                                detail = f"{change['change_percent']:+.2f}%" if 'change_percent' in change else change.get('reason', '')
                                reasons.append(f"{mode}: {change['status']} {detail}")
                    if record['status'] != 'ok':
                        reasons.append(mode + ': ' + str(record.get('errors') or record.get('compatibility', {}).get('reason', '')))
                attrs = f' title="{esc("; ".join(reasons))}"' if reasons else ''
                if paired:
                    one = ratios.get(('one-shot', key, name))
                    repeated = ratios.get(('repeated', key, name))
                    attrs += f' data-one-shot="{plain[0]}" data-repeated="{plain[1]}"'
                    if ratios:
                        attrs += f' data-relative-one-shot="{one if one is not None else str()}" data-relative-repeated="{repeated if repeated is not None else str()}"'
                elif ratios:
                    ratio = ratios.get(('one-shot', key, name))
                    attrs += f' data-relative="{ratio if ratio is not None else str()}"'
                display = paired_measurements(parts)
                if any(charts):
                    display = ' / '.join(f'<span class="inline-measurement">{text}{chart}</span>' for text, chart in zip(parts, charts))
                if display == 'n/a':
                    attrs += ' class="unavailable"'
                document += f'<td{attrs}>' + display + '</td>'
            document += '</tr>'
        document += '</tbody></table></div></section>'
    return page(title, document), changes
