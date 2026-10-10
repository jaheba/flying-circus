import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description='Vendor additional pinned pyperformance workloads')
parser.add_argument('--upstream', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1] / 'src/flying_circus'
revision = 'ccc0aeb7ad46d65b6dcd4160e0fdda4d885852dd'
if subprocess.check_output(['git', '-C', str(args.upstream), 'rev-parse', 'HEAD'], text=True).strip() != revision:
    parser.error('Upstream checkout must match the pinned revision')
manifest = json.loads((root / 'workloads/manifest.json').read_text())
provenance = json.loads((root / 'vendor/pyperformance/provenance.json').read_text())
adapters = {
    'barnes_hut': "print(f'{bench_quadtree_nbody(1, DEFAULT_PARTICLES, DEFAULT_ITERATIONS, DEFAULT_THETA):.6e}')\n",
    'float': "result = benchmark(POINTS)\nprint(f'{result.x:.9f} {result.y:.9f} {result.z:.9f}')\n",
    'unpack_sequence': "print(bench_tuple_unpacking(1000))\nprint(bench_list_unpacking(1000))\n",
    'json_dumps': """data = [(EMPTY[0], range(EMPTY[1])), (SIMPLE[0], range(SIMPLE[1])),
        (NESTED[0], range(NESTED[1])), (HUGE[0], range(HUGE[1]))]
bench_json_dumps(data)
for obj, _ in data:
    encoded = json.dumps(obj)
    assert json.loads(encoded) == obj
    print(len(encoded))
""",
    'json_loads': """objs = (json.dumps(DICT), json.dumps(TUPLE), json.dumps(DICT_GROUP))
bench_json_loads(objs)
for encoded, expected in zip(objs, (DICT, list(TUPLE), DICT_GROUP)):
    decoded = json.loads(encoded)
    assert decoded == expected
    print(len(decoded))
""",
}
for name, adapter in adapters.items():
    upstream_path = f'pyperformance/data-files/benchmarks/bm_{name}/run_benchmark.py'
    original = (args.upstream / upstream_path).read_bytes()
    (root / 'vendor/pyperformance' / f'{name}.py').write_bytes(original)
    source = original.decode()
    lines = source.splitlines(keepends=True)
    remove = set()
    for node in ast.parse(source).body:
        if ((isinstance(node, ast.Import) and any(a.name in ('pyperf', 'sys', 'random') for a in node.names))
            or (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name) and node.test.left.id == '__name__')
            or (isinstance(node, ast.FunctionDef) and node.name in ('main', 'add_cmdline_args', 'mutate_dict'))):
            remove.update(range(node.lineno - 1, node.end_lineno))
        if name == 'json_loads' and isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in ('random_source', 'DICT_GROUP') for t in node.targets):
            remove.update(range(node.lineno - 1, node.end_lineno))
    adapted = ''.join(line for i, line in enumerate(lines) if i not in remove)
    adapted = ''.join(line for line in adapted.splitlines(keepends=True) if line.strip() != 't0 = pyperf.perf_counter()')
    if name == 'float':
        adapted = adapted.replace('class Point(object):', 'class Point:')
    if name == 'barnes_hut':
        adapted = adapted.replace('return pyperf.perf_counter() - t0', 'return final_energy')
    elif name == 'unpack_sequence':
        adapted = adapted.replace('return pyperf.perf_counter() - t0', 'return (a, b, c, d, e, f, g, h, i, j)')
    elif name == 'json_loads':
        # Freeze the upstream seeded input so all interpreters parse identical JSON.
        namespace = {}
        exec(source.replace('import pyperf', ''), namespace)
        adapted += '\nDICT_GROUP = ' + repr(namespace['DICT_GROUP']) + '\n'
    path = root / 'workloads' / f'perf_{name}.py'
    path.write_text('# Adapted from pyperformance; see ../vendor/pyperformance/ for source and license.\n' + adapted.rstrip() + '\n\n' + adapter)
    result = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, timeout=60, check=True)
    details = {'revision': revision, 'path': upstream_path, 'sha256': hashlib.sha256(original).hexdigest()}
    manifest[f'perf_{name}'] = {'file': path.name, 'stdout': result.stdout, 'suite': 'pyperformance',
                              'compatibility_probe': True, 'upstream': details}
    provenance['benchmarks'][name] = {'path': upstream_path, 'sha256': details['sha256']}
    print(name, result.stdout.strip())
(root / 'workloads/manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
(root / 'vendor/pyperformance/provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
