# Adapted from pyperformance; see ../vendor/pyperformance/ for source and license.
import json



EMPTY = ({}, 2000)
SIMPLE_DATA = {'key1': 0, 'key2': True, 'key3': 'value', 'key4': 'foo',
               'key5': 'string'}
SIMPLE = (SIMPLE_DATA, 1000)
NESTED_DATA = {'key1': 0, 'key2': SIMPLE[0], 'key3': 'value', 'key4': SIMPLE[0],
               'key5': SIMPLE[0], 'key': '\u0105\u0107\u017c'}
NESTED = (NESTED_DATA, 1000)
HUGE = ([NESTED[0]] * 1000, 1)

CASES = ['EMPTY', 'SIMPLE', 'NESTED', 'HUGE']


def bench_json_dumps(data):
    for obj, count_it in data:
        for _ in count_it:
            json.dumps(obj)

data = [(EMPTY[0], range(EMPTY[1])), (SIMPLE[0], range(SIMPLE[1])),
        (NESTED[0], range(NESTED[1])), (HUGE[0], range(HUGE[1]))]
bench_json_dumps(data)
for obj, _ in data:
    encoded = json.dumps(obj)
    assert json.loads(encoded) == obj
    print(len(encoded))
