import argparse
import html
import json
from collections import defaultdict
from pathlib import Path

from .theme import page
from .formatting import milliseconds


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build an offline benchmark history page')
    parser.add_argument('results', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    groups = defaultdict(list)
    for path in args.results:
        run = json.loads(path.read_text())
        if run['schema_version'] != 1:
            parser.error(f'unsupported schema: {path}')
        for name, benchmark in run['benchmarks'].items():
            key = (name, run['machine'], run['platform'], run['architecture'],
                   benchmark['workload_sha256'], benchmark['expected_sha256'],
                   run['harness_sha256'], run['memory_helper_sha256'], run['harness_python'],
                   run['configuration']['legacy_cli_summary'], run['memory_method'], run.get('engine', run['binary_sha256']), benchmark['scenario'])
            groups[key].append((run, benchmark))
    sections = []
    escape = lambda value: html.escape(str(value))
    for key, entries in sorted(groups.items()):
        entries.sort(key=lambda item: item[0]['timestamp'])
        rows = []
        baseline = None
        for run, bench in entries:
            value = bench['median_wall_seconds']
            valid = bench['status'] == 'ok' and value is not None
            if baseline is None and valid:
                baseline = value
            relative = f'{value / baseline:.3f}×' if valid and baseline else '—'
            latency = milliseconds(value * 1000 if value is not None else None)
            memory = bench['median_peak_rss_bytes']
            memory = f'{memory / 1048576:.2f}' if memory is not None else '—'
            fields = [run['timestamp'], run['revision'], bench['status'], len(bench['wall_seconds']),
                      latency, relative, memory, run['build_info'], bench.get('compatibility', {}).get('reason', '')]
            rows.append('<tr>' + ''.join('<td>' + escape(field) + '</td>' for field in fields) + '</tr>')
        sections.append(f'<h2>{escape(key[0])} · {escape(key[-1])} · {escape(key[-2])}</h2><p>{escape(key[1])} · {escape(key[2])}<br>'
                        f'Workload: <code>{escape(key[4][:12])}</code></p>'
                        '<div class="table-wrap"><table><thead><tr><th>UTC</th><th>Revision</th><th>Status</th><th>Samples</th>'
                        '<th>Median ms</th><th>Time / baseline</th><th>Peak RSS MiB</th><th>Build</th><th>Compatibility reason</th>'
                        '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>')
    document = '''<h1>Application benchmark history</h1>
<p>Application benchmark history; scenario names distinguish fresh-process and warm-worker runs. Lower latency and memory are better.
Ratios use the first successful run in each comparable series; they are descriptive, not significance tests.
Series separate machines, OS versions, workloads, harnesses and measurement methods.
Failed runs are shown but never used as baselines. Memory comes from separate process runs.</p>
''' + ''.join(sections)
    document = page('Application benchmark history', document)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as destination:
        destination.write(document)


if __name__ == '__main__':
    main()
