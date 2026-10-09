def milliseconds(value):
    if value is None:
        return 'n/a'
    return f'{value:.0f}' if value >= 1 else f'{value:.2g}'


def measurement(value, metric):
    if metric == 'ms':
        return milliseconds(value)
    return 'n/a' if value is None else f'{value:.2f}'
