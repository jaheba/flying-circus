import argparse
import ast
import shutil
import hashlib
import json
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description='Regenerate pinned pyperformance Benchmark Game adapters')
parser.add_argument('--upstream', type=Path, required=True)
args = parser.parse_args()
upstream = args.upstream / 'pyperformance/data-files/benchmarks'
root = Path(__file__).resolve().parents[1] / 'src/flying_circus'
manifest = json.loads((root / 'workloads/manifest.json').read_text())
revision = 'ccc0aeb7ad46d65b6dcd4160e0fdda4d885852dd'
actual_revision = subprocess.check_output(['git', '-C', str(args.upstream), 'rev-parse', 'HEAD'], text=True).strip()
if actual_revision != revision:
    parser.error(f'Expected upstream revision {revision}, got {actual_revision}')
shutil.copyfile(args.upstream / 'COPYING', root / 'vendor/pyperformance/COPYING')
adapters = {
    'fannkuch': 'print(fannkuch(DEFAULT_ARG))\n',
    'nbody': "offset_momentum(BODIES[DEFAULT_REFERENCE])\nprint(f'{report_energy():.9f}')\nadvance(0.01, DEFAULT_ITERATIONS)\nprint(f'{report_energy():.9f}')\n",
    'pidigits': "print(''.join(str(digit) for digit in calc_ndigits(DEFAULT_DIGITS)))\n",
    'spectral_norm': "print(f'{bench_spectral_norm(1):.9f}')\n",
    'regex_dna': 'print(run_benchmarks(init_benchmarks(DEFAULT_INIT_LEN, DEFAULT_RNG_SEED)))\n',
    'meteor_contest': '''board, cti, pieces = get_puzzle(WIDTH, HEIGHT)
fps = get_footprints(board, cti, pieces)
se_nh = get_senh(board, cti)
solutions = []
solve(SOLVE_ARG, 0, frozenset(range(len(board))), [-1] * len(board),
      list(range(len(pieces))), solutions, fps, se_nh)
assert solutions == SOLUTIONS
print(len(solutions))
print(solutions[0])
print(solutions[-1])
''',
}
provenance = json.loads((root / 'vendor/pyperformance/provenance.json').read_text())
provenance.update(repository='https://github.com/python/pyperformance', revision=revision)
for name, adapter in adapters.items():
    original = (upstream / f'bm_{name}/run_benchmark.py').read_bytes()
    (root / 'vendor/pyperformance' / f'{name}.py').write_bytes(original)
    source = original.decode()
    lines = source.splitlines(keepends=True)
    remove = set()
    for node in ast.parse(source).body:
        if ((isinstance(node, ast.Import) and any(alias.name == 'pyperf' for alias in node.names))
            or (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name) and node.test.left.id == '__name__')
            or (isinstance(node, ast.FunctionDef) and node.name in
                {'add_cmdline_args', 'main', 'bench_nbody', 'bench_regex_dna', 'bench_meteor_contest'})):
            remove.update(range(node.lineno - 1, node.end_lineno))
    adapted = ''.join(line for i, line in enumerate(lines) if i not in remove)
    if name == 'fannkuch':
        adapted = adapted.replace('    perm1_ins = perm1.insert\n', '')
        adapted = adapted.replace('    perm1_pop = perm1.pop\n', '')
        adapted = adapted.replace('perm1_ins(r, perm1_pop(0))', 'perm1.insert(r, perm1.pop(0))')
    if name == 'spectral_norm':
        adapted = adapted.replace('    t0 = pyperf.perf_counter()\n', '')
        adapted = adapted.replace('    return pyperf.perf_counter() - t0', '    return (vBv / vv) ** 0.5')
    adapted = '# Adapted from pyperformance; provenance and license are in ../vendor/pyperformance/.\n' + adapted.rstrip() + '\n\n\n' + adapter
    path = root / 'workloads' / f'game_{name}.py'
    path.write_text(adapted)
    result = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, check=True, timeout=60)
    print(name, result.stdout[:140].strip())
    upstream_path = f'pyperformance/data-files/benchmarks/bm_{name}/run_benchmark.py'
    manifest[f'game_{name}'] = {'file': path.name, 'stdout': result.stdout, 'suite': 'benchmark_game',
                              'compatibility_probe': True,
                              'upstream': {'revision': revision, 'path': upstream_path,
                                           'sha256': hashlib.sha256(original).hexdigest()}}
    if name == 'fannkuch':
        manifest[f'game_{name}']['known_missing'] = [{'type': 'AttributeError',
            'message': "'list' object has no attribute 'insert'"},
            {'type': 'TypeError', 'message': 'list indices must be integers or slices, not slice'}]
    provenance['benchmarks'][name] = {'path': upstream_path, 'sha256': hashlib.sha256(original).hexdigest()}
(root / 'workloads/manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
(root / 'vendor/pyperformance/provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
