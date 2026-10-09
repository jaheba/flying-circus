import json

from . import matrix_report
from .formatting import measurement, runtime_description, runtime_label

EXTENSIONS = {'html': 'html', 'markdown': 'md', 'json': 'json'}


def report_data(directory, diff=False, threshold=5, absolute_ms=0.01):
    index, runs, startup = matrix_report.load(directory)
    changes = matrix_report.diff_results(index, runs, startup, threshold, absolute_ms) if diff else None
    return {'schema_version': 1, 'mode': 'diff' if diff else 'comparison',
            'run': index, 'results': runs, 'startup': startup,
            'diff': {'threshold_percent': threshold, 'absolute_threshold_ms': absolute_ms, 'comparisons': changes}
            if diff else None}


def escape(value):
    return str(value).replace('\\', '\\\\').replace('|', '\\|').replace('\r', ' ').replace('\n', ' ').replace('`', '\\`').replace('*', '\\*').replace('_', '\\_').replace('<', '&lt;').replace('>', '&gt;')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |']
                     + ['| ' + ' | '.join(row) + ' |' for row in rows]) + '\n'


def markdown(data):
    index, runs, startup = data['run'], data['results'], data['startup']
    keys = list(index['runtimes'])
    first = runs['one-shot'][keys[0]]
    diff = data['mode'] == 'diff'
    headers = [escape(runtime_label(index['runtimes'][key])) for key in keys]
    lines = ['# Performance changes' if diff else '# Application benchmarks', '',
             f'- CPU: {escape(first.get("cpu", "Not recorded"))}', f'- OS: {escape(first["platform"])}',
             f'- Samples: {first["configuration"]["samples"]}',
             f'- Repeated warmups: {runs["repeated"][keys[0]]["configuration"]["warmups"]}',
             '- Timing: median ms, one-shot / repeated; startup excluded',
             '- RSS: median MiB, separate one-shot processes including startup',
             '- Startup: empty -c command, launch through exit, normal defaults', '']
    lines += [' · '.join(escape(runtime_description(index['runtimes'][key], runs['one-shot'][key])) for key in keys), '']
    if diff:
        changes = data['diff']['comparisons']
        visible = [row for row in changes if row['status'] in ('failure', 'compatibility change', 'regression', 'improvement')]
        order = {'failure': 0, 'compatibility change': 1, 'regression': 2, 'improvement': 3}
        visible.sort(key=lambda row: (order[row['status']], -abs(row.get('change_percent', 0))))
        lines += [f'- Reference: {escape(index["runtimes"][keys[0]]["label"])}',
                  f'- Threshold: {data["diff"]["threshold_percent"]:g}% and {data["diff"]["absolute_threshold_ms"]:g} ms for timings',
                  '- Evidence: bootstrap median-ratio bounds, approximate 95% family level, Bonferroni correction', '',
                  f'{len(changes)} comparisons; {len(visible)} changes or failures; '
                  f'{sum(row["status"] == "inconclusive" for row in changes)} inconclusive (see diff.json).', '']
        if not visible:
            lines += ['No significant changes detected.', '']
        else:
            rows = []
            for row in visible:
                bounds = row.get('interval_percent')
                detail = f'{bounds[0]:+.1f}% to {bounds[1]:+.1f}%' if bounds else row.get('reason', '')
                rows.append([escape(value) for value in (row['workload'], row['scenario'], row['metric'], row['candidate_label'],
                             row['status'], measurement(row.get('baseline'), row['metric']),
                             measurement(row.get('candidate'), row['metric']),
                             f'{row["change_percent"]:+.1f}%' if 'change_percent' in row else 'n/a', detail)])
            lines += [table(['Workload', 'Scenario', 'Metric', 'Candidate', 'Result', 'Baseline', 'Candidate value', 'Change', 'Bounds / reason'], rows), '']
        lines += ['Inconclusive results are excluded from the table. Bootstrap bounds are estimates; repeat borderline runs.', '']
    else:
        if startup.get('engines'):
            values = {key: 'failed' if entry.get('errors') else measurement(entry['median_wall_seconds'] * 1000, 'ms')
                      for key, entry in startup['engines'].items()}
            cells = [values[key] for key in keys]
            lines += ['## Process startup · ms', '', table(headers, [cells]), '']
        for metric, heading in (('ms', 'Runtime · ms · one-shot / repeated'), ('rss_mib', 'Peak RSS · MiB · one-shot')):
            rows = []
            modes = matrix_report.MODES if metric == 'ms' else ('one-shot',)
            for name in first['benchmarks']:
                values = {}
                for mode in modes:
                    field, scale = ('median_wall_seconds', 1000) if metric == 'ms' else ('median_peak_rss_bytes', 1 / 1048576)
                    for key in keys:
                        record = runs[mode][key]['benchmarks'][name]
                        value = record[field]
                        values[mode, key] = ('failed' if record['status'] == 'failed' else
                                            measurement(value * scale if record['status'] == 'ok' and value is not None else None, metric))
                rows.append([escape(name)] + [' / '.join(values[mode, key] for mode in modes) for key in keys])
            lines += [f'## {heading}', '', table(['Workload'] + headers, rows), '']
        failures = []
        for mode, results in runs.items():
            for key, run in results.items():
                for name, record in run['benchmarks'].items():
                    if record['status'] == 'failed':
                        failures.append(f'- {escape(index["runtimes"][key]["label"])} / {escape(name)} / {mode}: {escape(record["errors"])}')
        for key, entry in startup.get('engines', {}).items():
            if entry.get('errors'):
                failures.append(f'- {escape(index["runtimes"][key]["label"])} / startup: {escape(entry["errors"])}')
        if failures:
            lines += ['## Failures', '', *failures, '']
    lines += ['## Runtimes and build details', '']
    for key in keys:
        run = runs['one-shot'][key]
        lines += [f'- **{escape(index["runtimes"][key]["label"])}**: {escape(run["engine"])}; {escape(run["revision"])}',
                  f'  - Binary: {escape(run["configuration"]["binary"])}',
                  f'  - Build: {escape(run["build_info"])}', f'  - SHA256: {run["binary_sha256"]}', '']
    return '\n'.join(lines)


def write_reports(directory, formats, diff=False, threshold=5, absolute_ms=0.01):
    from pathlib import Path

    directory = Path(directory)
    data = report_data(directory, diff, threshold, absolute_ms)
    paths = []
    for format in dict.fromkeys(formats):
        if format == 'html':
            text, _ = matrix_report.render(directory, diff, threshold, absolute_ms)
        elif format == 'markdown':
            text = markdown(data)
        else:
            text = json.dumps(data, indent=2, allow_nan=False) + '\n'
        path = directory / ('report.' + EXTENSIONS[format])
        path.write_text(text, encoding='utf-8')
        paths.append(path)
    changes = data['diff']['comparisons'] if diff else None
    if changes is not None:
        (directory / 'diff.json').write_text(json.dumps(changes, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return paths, changes
