import html
import math


def relative_values(index, runs, field='median_wall_seconds'):
    baseline = next((key for key, runtime in index['runtimes'].items() if runtime['engine'] == 'cpython'), None)
    ratios = {}
    if baseline is not None and len(index['runtimes']) > 1:
        for mode, engines in runs.items():
            for name, reference in engines[baseline]['benchmarks'].items():
                denominator = reference.get(field)
                if reference['status'] != 'ok' or not denominator or not math.isfinite(denominator):
                    continue
                for key, engine in engines.items():
                    record = engine['benchmarks'][name]
                    value = record.get(field)
                    if record['status'] == 'ok' and value is not None:
                        ratio = value / denominator
                        if ratio > 0 and math.isfinite(ratio):
                            ratios[mode, key, name] = ratio
    extent = max(1, max([0] + [abs(math.asinh((value - 1) / 0.05)) for value in ratios.values()]))
    return ratios, extent


def inline_chart(ratio, extent, mode, metric='runtime'):
    if ratio is None:
        return ''
    offset = 50 * math.asinh((ratio - 1) / 0.05) / extent
    outcome = 'better' if ratio < 1 else 'worse' if ratio > 1 else 'equal'
    comparison = 'less memory' if metric == 'RSS' else 'faster'
    label = html.escape(f'{mode}: {(ratio - 1) * 100:+.2f}% vs CPython {metric} ({ratio:.3g}×); lower is {comparison}', quote=True)
    return (f'<span class="inline-chart {outcome}" role="img" aria-label="{label}" title="{label}">'
            '<i class="chart-reference"></i>'
            f'<i class="chart-bar" style="bottom:{50 + min(0, -offset):.6f}%;height:{abs(offset):.6f}%"></i></span>')


def advantage_order(names, ratios, baseline):
    if not ratios:
        return list(names)
    best = {}
    for (_, key, name), ratio in ratios.items():
        if key != baseline:
            best[name] = min(best.get(name, math.inf), ratio)
    return sorted(names, key=lambda name: best.get(name, math.inf))
