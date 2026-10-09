# Pyperformance Benchmark Game sources

Source: https://github.com/python/pyperformance/tree/ccc0aeb7ad46d65b6dcd4160e0fdda4d885852dd

The six original `run_benchmark.py` files are preserved here, together with `COPYING` and source hashes in `provenance.json`.
Contributor credits remain in their original docstrings.

The `workloads/game_*.py` adapters remove the pyperf import, command-line runner and timing wrappers.
They execute each algorithm once at its upstream default input size and print a checked result.
Spectral norm returns the calculated norm instead of pyperf's elapsed-time value.
N-body prints initial and final energy rounded to nine decimals.
Pi digits prints the full 2,000-digit result.
Meteor retains upstream's complete expected-solution assertion before printing a summary.
Regex DNA includes FASTA input generation in the application request.
The computational algorithms and unsupported Python features are retained.

These are adapted one-shot workloads, not official pyperformance/pyperf measurements.
Source compilation, imports, input initialization and result reporting follow the selected Flying Circus scenario.

Regenerate from a checkout at the pinned revision:

```sh
uv run python scripts/vendor_pyperformance.py --upstream /path/to/pyperformance
```

Additional workloads use the same pinned revision and retain their original sources here.
Regenerate them with:

```sh
uv run python scripts/vendor_pyperformance_extra.py --upstream /path/to/pyperformance
```

The `pyperformance` suite contains these adapters:

- Barnes–Hut: 200 particles, 100 steps, theta 0.5; prints final system energy.
- Float: 100,000 points; prints the normalized coordinate maxima.
  The redundant `object` base is omitted so Monty can construct the class.
- Sequence unpacking: tuple and list inputs, 1,000 batches of upstream's 400 unpackings each.
  Each function returns its final unpacked values instead of elapsed time.
- JSON dumps: all four upstream cases and their original repetition counts; checks round trips and prints encoded lengths.
- JSON loads: all three upstream objects, 20 loads each; checks decoded values.
  The upstream seeded random dictionary group is frozen into the adapter using the generator's CPython.
  Every engine receives identical fixture values, without depending on random-module support or native integer size.
- GC traversal: the original 1,000-level shared-container graph and two explicit collections.
  It retains the zero-collected assertion, checks graph size, and prints the outer length.
  A missing `gc` module remains unsupported; the adapter does not emulate garbage collection.

Fannkuch uses direct `perm1.insert(...)` and `perm1.pop(...)` calls instead of cached bound methods.
This keeps its permutation algorithm intact.
Monty binaries without slice assignment still report `n/a` for this workload.

All adapters include initialization, imports, compilation and result checking according to the selected request scenario.
They do not reproduce pyperf's calibrated timing boundaries.
