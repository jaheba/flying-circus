import math
import random
import statistics


def difference(before, after, *, threshold=5, absolute=0, trials=4000, comparisons=1):
    if not before or not after:
        return {'status': 'unavailable'}
    if any(not math.isfinite(value) or value <= 0 for value in before + after):
        raise ValueError('Samples must be finite and positive')
    baseline, candidate = statistics.median(before), statistics.median(after)
    change = (candidate / baseline - 1) * 100
    result = {'change_percent': change, 'baseline': baseline, 'candidate': candidate}
    if abs(change) < threshold or abs(candidate - baseline) < absolute:
        return dict(result, status='unchanged')
    if len(before) < 10 or len(after) < 10:
        return dict(result, status='inconclusive', reason='At least 10 samples per runtime required')
    rng = random.Random(0)
    changes = []
    for _ in range(trials):
        b = statistics.median(rng.choices(before, k=len(before)))
        c = statistics.median(rng.choices(after, k=len(after)))
        changes.append((c / b - 1) * 100)
    changes.sort()
    # Bonferroni correction across the measured timing comparisons.
    tail = 0.025 / comparisons
    low = changes[min(int(trials * tail), trials - 1)]
    high = changes[min(math.ceil(trials * (1 - tail)) - 1, trials - 1)]
    if comparisons > trials * 0.025:
        return dict(result, status='inconclusive', reason='Too many comparisons for bootstrap resolution')
    result.update(interval_percent=[low, high], confidence_family=0.95)
    meaningful = abs(change) >= threshold and abs(candidate - baseline) >= absolute
    if meaningful and low > 0:
        status = 'regression'
    elif meaningful and high < 0:
        status = 'improvement'
    elif meaningful:
        status = 'inconclusive'
    else:
        status = 'unchanged'
    return dict(result, status=status)
