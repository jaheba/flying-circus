import html
import math

from .formatting import runtime_label


def runtime_chart(index, runs):
    runtimes = index['runtimes']
    baseline = next((key for key, runtime in runtimes.items() if runtime['engine'] == 'cpython'), None)
    if baseline is None or len(runtimes) < 2:
        return ''
    esc = lambda value: html.escape(str(value), quote=True)
    reference = runtime_label(runtimes[baseline])
    document = f'<h2>Runtime relative to {esc(reference)}</h2>'
    document += '<p>CPython = 1× · lower is faster · median runtime, startup excluded.</p>'
    colors = ('#38a9dc', '#e16370', '#a48ae0', '#43b5a2', '#dfaa45')
    for mode in ('one-shot', 'repeated'):
        rows = []
        for name, base in runs[mode][baseline]['benchmarks'].items():
            denominator = base.get('median_wall_seconds')
            if base['status'] != 'ok' or not denominator or not math.isfinite(denominator):
                continue
            values = []
            for key in runtimes:
                if key == baseline:
                    continue
                record = runs[mode][key]['benchmarks'][name]
                value = record.get('median_wall_seconds')
                ratio = value / denominator if record['status'] == 'ok' and value is not None else None
                values.append((key, ratio if ratio is not None and math.isfinite(ratio) and ratio >= 0 else None))
            rows.append((name, values))
        maximum = max([1] + [ratio for _, values in rows for _, ratio in values if ratio is not None])
        document += f'<details class="runtime-chart"{ " open" if mode == "one-shot" else ""}><summary>{mode.capitalize()}</summary>'
        document += f'<p class="chart-scale">Shared scale: 0–{maximum:.3g}× · vertical line = 1×</p>'
        for name, values in rows:
            document += f'<div class="chart-group"><div class="chart-name">{esc(name)}</div>'
            for number, (key, ratio) in enumerate(values):
                label = runtime_label(runtimes[key])
                text = f'{ratio:.3g}×' if ratio is not None else 'n/a'
                document += f'<div class="chart-row" aria-label="{esc(name)}: {esc(label)} {text}"><span>{esc(label)}</span>'
                document += f'<span class="chart-track"><i class="chart-reference" style="left:{100 / maximum:.6f}%"></i>'
                if ratio is not None:
                    document += f'<i class="chart-bar" style="width:{100 * ratio / maximum:.6f}%;background:{colors[number % len(colors)]}"></i>'
                document += f'</span><span>{text}</span></div>'
            document += '</div>'
        document += '</details>'
    return document
