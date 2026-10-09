def number(value):
    if value is None:
        return 'n/a'
    magnitude = abs(value)
    if 0 < magnitude < 0.005:
        return f'{value:.3g}'
    if round(magnitude, 2) < 10:
        return f'{value:.2f}'
    if round(magnitude, 1) < 100:
        return f'{value:.1f}'
    return f'{float(f"{value:.3g}"):.0f}'


def milliseconds(value):
    return number(value)


def measurement(value, metric):
    return number(value)


def winners(values):
    available = {key: float(value) for key, value in values.items() if value not in ('n/a', 'failed')}
    best = min(available.values(), default=None)
    return {key for key, value in available.items() if value == best}


def runtime_label(runtime):
    import re

    label = runtime['label']
    if re.fullmatch(r'python(?:3(?:\.\d+)*)?', label) or label == 'cpython':
        return 'CPython'
    if re.fullmatch(r'pypy(?:3(?:\.\d+)*)?', label):
        return 'PyPy'
    if label == 'monty':
        return 'Monty'
    if label.startswith('monty-'):
        return 'Monty ' + label[6:]
    return label


def runtime_version(engine, output):
    import re

    number = r'(\d+\.\d+(?:\.\d+)?(?:[a-zA-Z][\w.-]*|[-+][\w.-]+)?)'
    prefix = {'monty': r'monty(?:-runtime)?', 'cpython': r'Python', 'pypy': r'PyPy'}.get(engine)
    match = re.search(prefix + r'\s+v?' + number, output, re.IGNORECASE) if prefix else None
    return match.group(1) if match else 'unknown'


def runtime_description(runtime, run):
    engine = runtime.get('engine') or run.get('engine', 'unknown')
    name = {'monty': 'Monty', 'cpython': 'CPython', 'pypy': 'PyPy'}.get(engine, engine)
    output = runtime.get('version') or run.get('runtime_version') or runtime.get('revision', '')
    version = runtime_version(engine, output)
    label = runtime_label(runtime)
    return f'{label}: {name} {version}' if label != name else f'{name} {version}'


def paired_measurements(values):
    values = list(values)
    return 'n/a' if values and all(value == 'n/a' for value in values) else ' / '.join(values)


def duration(seconds):
    if seconds is None:
        return 'Not recorded'
    seconds = round(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f'{hours}h {minutes}m {seconds}s'
    if minutes:
        return f'{minutes}m {seconds}s'
    return f'{seconds}s'
