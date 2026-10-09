# Flying Circus

Compare real application workloads across Monty, CPython and PyPy binaries.

```sh
uv tool install --editable .
flying-circus -r monty=/path/to/monty -r python3.14 -r pypy3
flying-circus --diff -r baseline=/path/to/old/monty -r optimized=/path/to/new/monty
```

The installed command works from any directory. No Justfile is required.
Repeat `-r` / `--runtime` for each executable, with an optional `label=executable` tag.
Executable names resolve through PATH; labels default to the executable basename and must be unique.
Runtime type is detected independently of its label, so multiple versions of any supported interpreter can be compared.
Python 3.11 or later is required for the harness; worker interpreters need Python 3.10 or later.

Every run measures all workloads in both scenarios: a first request in a fresh ready worker, and repeated requests
in reused workers with fresh application sessions. Compilation, execution and output delivery are timed;
process startup and fixture preparation are excluded. Repeated measurements have three untimed warmups by default.
An empty `-c ''` command measures process startup separately, including launch through exit with normal interpreter defaults.
Peak RSS measures whole processes, including startup, in separate one-shot runs on Linux and macOS.
Unsupported workloads display `n/a`; unexpected failures remain visible.

Results include raw samples, interpreter hashes, host details and `report.html` in a new directory under the user's
application-data directory. Use `--output /path/to/new-directory` to choose another location.
Existing result directories are never overwritten.

Choose report formats with `--format`; HTML is the default. Repeat the flag to write several formats from one run:

```sh
flying-circus -r python3.14 -r pypy3 --format markdown
flying-circus --diff -r before=/path/to/baseline -r after=/path/to/candidate --format json
flying-circus -r python3.14 -r pypy3 --format html --format markdown --format json
```

Reports are written as `report.html`, `report.md`, and `report.json` in the result directory.
Markdown includes startup, timing and RSS tables with runtime names and versions.
Lowest measurements per scenario are bold, including ties at the displayed precision.
Values display as `0.xx`, `x.xx`, `xx.x`, or three significant digits for larger values;
very small measurements retain additional precision to avoid rounding to zero.
JSON contains a versioned report envelope with run metadata, raw results for both scenarios, startup samples,
and all diff classifications when `--diff` is enabled. Unavailable numeric measurements are `null` with a status.
Diff HTML and Markdown show significant changes, compatibility changes and failures;
unchanged, unavailable and inconclusive classifications remain in the JSON data.
Raw measurement files and `diff.json` are retained regardless of the chosen report format.

```sh
flying-circus -r python3.14 -r pypy3 --samples 30 --memory-samples 5 --startup-samples 50
flying-circus --diff -r before=/path/to/baseline -r after=/path/to/candidate --threshold 5
```

For a quick full-suite comparison, use `--quick`:

```sh
flying-circus --quick -r monty=/path/to/monty -r python3.14 -r pypy3
flying-circus --quick --samples 10 -r before=/path/to/old -r after=/path/to/new --diff
```

| Setting | Default | Quick |
| --- | --- | --- |
| Timing samples per workload, runtime and scenario | 20 | 3 |
| Startup samples per runtime | 50 | 5 |
| Repeated warmups per workload | 3 | 1 |
| Separate RSS samples per workload | 3 (10 with `--diff`) | 1 |
| Per-request timeout | 30 seconds | 30 seconds |

Explicit sample and warmup flags override the preset, regardless of argument order.
Quick mode still runs every workload in both one-shot and repeated scenarios, with output validation and compatibility checks.
It provides a rough comparison; PyPy's repeated results are especially sensitive to the reduced warmup count.
Reports mark quick runs, and raw metadata records the actual settings.
With fewer than ten timing samples, `--diff` records meaningful timing changes as inconclusive rather than significant.
RSS collection defaults to zero on platforms other than Linux and macOS.

`--diff` compares every later runtime against the first. Its report shows improvements, regressions, compatibility
changes and failures, and writes all classifications (including inconclusive changes) to `diff.json`.
A timing change must exceed both the percentage threshold (default 5%) and the absolute threshold
(`--absolute-threshold-ms`, default 0.01 ms). RSS uses the percentage threshold.
Bootstrap bounds for median ratios use a Bonferroni correction across measured comparisons at an approximate 95% family level.
At least ten samples per runtime are needed to classify a meaningful change; smaller samples produce inconclusive results.
Bounds estimate sampling uncertainty and do not account for systematic host interference.
Default sample counts are 20 for application timing, 50 for startup and 3 for RSS (10 with `--diff`).
`--warmups` and `--timeout` control repeated warmups and the per-request timeout.
The exit status is nonzero for measurement failures; detected regressions alone do not change it.

For development, run `uv sync` and `uv run python -m unittest discover -s tests`.
The optional Justfile and legacy subcommands remain available for existing workflows.

## Workloads

| Name | Application |
| --- | --- |
| `expense_report` | Aggregate team expenses and produce a sorted report |
| `order_cleanup` | Normalize spreadsheet-export rows, reject missing quantities and calculate regional sales |
| `api_report` | Parse a ticket API response, filter, prioritize and produce an action report |
| `capacity_planning` | Optimize 80 indivisible projects within a 2,400-day budget using dynamic programming |
| `portfolio_risk` | Bootstrap 2,048 portfolio scenarios over 126 trading days using fixed-point returns |
| `ticket_search` | Build a TF-IDF index over 1,600 support tickets and rank five incident queries |

The suite includes small tasks and computational workloads with deterministic synthetic data.
Each workload performs one application task; it does not repeat a tiny operation to fill time.
Capacity planning checks the selected projects against the budget and reported benefit.
Portfolio risk uses a fixed pseudorandom sequence and integer cents for exact cross-engine results.
Ticket search reports ranked IDs and quantized scores, covering tokenization, indexing and ranking.
Input generation, computation and reporting are all included in application latency.
Callback-driven workflows and fixtures from real applications remain to be added.
Expected output is checked in independently in `workloads/manifest.json` and checked after every timed execution.
To check shared Python semantics, the same programs can be run through CPython using `--monty /path/to/python3`.
Label that revision explicitly as CPython; the option name refers to the normal benchmark target.

## One-shot and repeated scenarios

The primary scenarios run each workload exactly once per process:

| Scenario | Process lifecycle | Timed interval |
| --- | --- | --- |
| `cold_process_one_shot` | Fresh CLI process per sample | Launch through exit and captured result |
| `warm_worker_one_shot` | Fresh worker per sample; readiness handshake first | First application request through result |
| `repeated_requests` | Reuse a worker across samples | Each application request through result |

`run` defaults to `warm_worker_one_shot`. `warm` remains an alias of `run`.
Both one-shot scenarios enforce zero workload warmups.
Each measured request uses a separate process, so earlier application requests cannot train its JIT or caches.
OS file caches are not flushed; one-shot describes the process lifecycle, not cold storage.
In `warm_worker_one_shot`, process readiness and session configuration are outside the application timer.
Readiness and session setup timings are stored per sample; the first application feed includes lazy interpreter setup.
The readiness handshake executes no application code.
The Python helper imports its own protocol dependencies before readiness, which can initialize their import caches.
Process startup is measured separately with an empty `-c ""` command.

```sh
uv run flying-circus run --scenario warm_worker_one_shot \
  --monty /absolute/path/to/monty --cpython /absolute/path/to/python3 --pypy /absolute/path/to/pypy3 \
  --monty-revision COMMIT --cpython-revision cpython-VERSION --pypy-revision pypy-VERSION \
  --output results/one-shot-worker
uv run flying-circus run --scenario cold_process_one_shot \
  --monty /absolute/path/to/monty --cpython /absolute/path/to/python3 --pypy /absolute/path/to/pypy3 \
  --monty-revision COMMIT --cpython-revision cpython-VERSION --pypy-revision pypy-VERSION \
  --output results/one-shot-process
```

For an older Monty CLI, add `--legacy-cli-summary` to the cold-process command.
Use `compare --monty-results DIR/monty.json --cpython-results DIR/cpython.json --pypy-results DIR/pypy.json`
with `--output DIR/comparison.html` to generate a report for either scenario.
Scenario compatibility checks prevent comparing cold, first-request and repeated-request results.
`repeated_requests` retains the earlier warm-process benchmark behavior, including optional workload warmups.
Existing result files labeled `warm_worker_new_session` describe that earlier repeated-request behavior.
The `bench` command also remains available for standalone-process timing and peak RSS collection.

## Latency

Each sample starts a fresh process and waits for completion.
The measurement includes host process launch and pipe handling, but excludes result validation.
It measures completion latency, not time to the first output byte or worker readiness.
Fresh processes do not imply cold OS caches; there is no cache flushing or discarded warmup.
The default is 20 samples per workload, interleaved in a reproducible shuffled order.
Use `--workload NAME` repeatedly to select workloads, `--samples N` and `--timeout SECONDS` to control collection.

Result files contain ordered raw samples, medians, standard deviations, errors, binary/workload/harness hashes,
revision, build notes and machine metadata.
A failed or timed-out run is recorded and makes the command exit nonzero.
Existing result and report files are never overwritten.

Run comparisons on an otherwise idle, stable machine with fixed power settings and comparable build settings.
The report separates series by machine, platform, workload, harness, Python version and measurement method.
It shows changes relative to the first successful run in each series.
Ratios describe the collected samples; they do not establish statistical significance.
Pass all desired JSON result files to `flying-circus report` to generate an offline history page.

## Memory

Linux and macOS support peak resident memory collection without interpreter instrumentation.
The default is three separate memory runs per workload, after latency sampling.
A fresh Python collector launches exactly one target process and reads `RUSAGE_CHILDREN.ru_maxrss` after it exits.
The collector's own memory is excluded. macOS bytes and Linux KiB are normalized to bytes.
Use `--memory-samples 0` to disable collection, including on unsupported platforms.

RSS includes interpreter code, allocator overhead, stacks and resident data.
The measurement applies to the direct CLI process; it does not claim a simultaneous process-tree peak.
Peak accounting conventions differ between operating systems; compare on the same OS and machine.
Internal live-byte accounting, allocation counts and object attribution would require optional telemetry or profiling.
Those diagnostics are separate from the primary application measurements.

## Next scenarios

Persistent-worker and callback benchmarks should drive `monty subprocess` using its versioned protobuf protocol.
Measure session creation, first execution, follow-up feeds, callback round trips and snapshot restoration separately.
That adapter should depend on the protocol schema, independently of interpreter internals.
CLI measurements do not include Python binding or pool overhead.
Warm-worker measurements are implemented below. Stateful follow-up feeds, callbacks, snapshots and automated publishing remain to be added.

## CPython comparison

Run the identical checked workloads through a CPython executable, then compare result files:

```sh
uv run flying-circus bench --binary /absolute/path/to/python3 --engine cpython --revision cpython-3.14.2 \
  --output results/cpython.json
uv run flying-circus compare --monty-results results/monty.json \
  --cpython-results results/cpython.json --output results/comparison.html
```

Collect both engines on the same idle machine with the same harness version.
The comparison checks workload/output hashes, machine, OS, architecture, harness and memory measurement compatibility.
Different CLI output adapters are allowed, so an older Monty timing summary can be stripped while CPython stays strict.
The programs use each engine's standard library implementations; compilation, imports and output delivery are included.
The report shows median completion latency, Monty/CPython latency ratios and each engine's peak RSS.
This measures fresh-process application cost; it does not isolate interpreter execution speed.

## Repeated-request comparison

Reuse one process per engine and measure each application in a fresh session:

```sh
uv run flying-circus run --scenario repeated_requests --monty /absolute/path/to/monty \
  --cpython /absolute/path/to/python3 \
  --monty-revision COMMIT --cpython-revision cpython-3.14.2 \
  --output results/warm
uv run flying-circus compare --monty-results results/warm/monty.json \
  --cpython-results results/warm/cpython.json --output results/warm/comparison.html
```

The Monty adapter drives `monty subprocess` through the versioned protobuf schema.
It reuses one worker, configuring and resetting a session per sample, as a warm pool checkout does.
The CPython adapter keeps one helper process alive and creates a fresh globals dictionary per sample.
Each engine gets one validated, untimed warmup per workload by default (`--warmups N`).
Samples are shuffled across both engines and workloads, with only one application request active at a time.

The application timer includes request serialization, IPC, source compilation, execution and output collection.
It excludes process startup, readiness, session configuration/reset and correctness validation.
Worker readiness and session setup/reset durations are stored separately in the result files.
CPython's process-wide import cache survives namespace resets; this is normal warm-process behavior.
Monty session resets discard the session's compiled code and globals.
Process startup is shown separately and is not subtracted from application timings.

This models sequential use of a warm worker, including transport overhead.
It does not measure pool scheduling, concurrent throughput, Python binding overhead or precompiled execution alone.
One-shot scenarios collect peak RSS in three separate process runs per workload by default on Linux/macOS.
This measures the whole interpreter process, including startup; it does not attribute memory to individual application allocations.
Repeated-request memory is not collected because a process-lifetime peak cannot be attributed to one request.
Use `--memory-samples 0` to disable collection.
The generated protocol adapter adds a protobuf runtime dependency.

To run only the computational workloads:

```sh
uv run flying-circus run --scenario repeated_requests --monty /absolute/path/to/monty \
  --cpython /absolute/path/to/python3 \
  --monty-revision COMMIT --cpython-revision cpython-3.14.2 \
  --workload capacity_planning --workload portfolio_risk --workload ticket_search \
  --output results/computational
```

## PyPy

Add an optional PyPy executable to the same interleaved warm-worker run:

```sh
uv run flying-circus run --scenario repeated_requests --monty /absolute/path/to/monty \
  --cpython /absolute/path/to/python3 --pypy /absolute/path/to/pypy3 \
  --monty-revision COMMIT --cpython-revision cpython-3.14.2 \
  --pypy-revision pypy-VERSION --warmups 3 --samples 20 --output results/three-engines
uv run flying-circus compare --monty-results results/three-engines/monty.json \
  --cpython-results results/three-engines/cpython.json \
  --pypy-results results/three-engines/pypy.json --output results/three-engines/comparison.html
```

PyPy uses the same persistent Python helper as CPython; it does not need the harness installed in its environment.
The helper supports Python 3.10 and later; the harness still requires Python 3.11 or later.
Record both the PyPy version and its supported Python version in the revision/build notes.
The comparison may therefore include different Python language versions, which the report should identify.
The history report keeps each engine in a separate series.

In repeated-request scenarios, the same number of warmup requests is used for every engine, and raw warmup timings are retained.
Repeated-request runs still compile fresh source per request and reset application globals.
They measure repeated independent application requests, including compilation and any JIT work incurred.
They do not establish steady-state JIT throughput: a fixed warmup count cannot guarantee that the JIT has settled.
For PyPy background, see its [performance guidance](https://pypy.org/performance.html).

Fresh-process PyPy latency and RSS can also be collected with `bench --binary /path/to/pypy3`.
Supply that result through `compare --pypy-results`, alongside matching Monty and CPython fresh-process runs.

## Pyperformance Benchmark Game suite

`--suite benchmark_game` selects the six Benchmark Game workloads documented by
[pyperformance](https://pyperformance.readthedocs.io/benchmarks.html):

| Workload | Upstream default input |
| --- | --- |
| `game_fannkuch` | Permutations of 9 elements |
| `game_nbody` | 20,000 simulation steps |
| `game_pidigits` | 2,000 pi digits |
| `game_spectral_norm` | Matrix dimension 130, 10 power iterations |
| `game_regex_dna` | FASTA length parameter 100,000; 1,000,000 bases |
| `game_meteor_contest` | First 60 puzzle solutions |

```sh
uv run flying-circus run --suite benchmark_game \
  --monty /absolute/path/to/monty --cpython /absolute/path/to/python3 --pypy /absolute/path/to/pypy3 \
  --monty-revision COMMIT --cpython-revision cpython-VERSION --pypy-revision pypy-VERSION \
  --output results/benchmark-game
uv run flying-circus compare --monty-results results/benchmark-game/monty.json \
  --cpython-results results/benchmark-game/cpython.json --pypy-results results/benchmark-game/pypy.json \
  --output results/benchmark-game/comparison.html
```

The default suite remains `applications`; `--suite all` includes both suites.
Explicit `--workload` selections override suite selection.
The standalone `bench` command also accepts `--suite`; use `--engine cpython` or `--engine pypy` for those binaries.

Before sampling a Benchmark Game workload, each engine runs a full compatibility probe in a disposable worker.
The probe checks the complete expected output and is outside all reported timings.
Every measured one-shot request still gets a separate, untrained process.
A supported workload is timed normally.
A missing module, explicitly unimplemented feature, or narrowly documented missing API produces `unsupported` with a reason.
For example, the fannkuch adapter recognizes the exact missing `list.insert` error; arbitrary attribute errors stay failures.
Crashes, timeouts, wrong output and unexpected exceptions remain `failed` and make the command exit nonzero.
Unsupported workloads do not stop other engines or workloads and are shown as `n/a` without timing ratios; reasons remain in tooltips and JSON.
No support decision is cached across runs, so a newer Monty binary is checked again automatically.

Original sources, license, pinned revision and adaptation notes are in `src/flying_circus/vendor/pyperformance/`.
The adapters preserve unsupported features rather than replacing them with Monty-specific algorithms.
They retain upstream default input sizes but use Flying Circus's one-shot lifecycle instead of pyperf's timing loop.
Consequently, their numbers should not be treated as official pyperformance results.

## Memory in comparison reports

One-shot `run` and `just` recipes collect peak resident memory in separate runs after latency sampling.
The default is three memory runs per supported workload on Linux/macOS.
The OS peak includes interpreter startup, code, stacks, allocator overhead and application data.
For worker scenarios, the collector waits for readiness and executes the first request, then obtains the exited child's peak RSS.
The collector's own Python process is excluded.
Memory profiling does not alter the latency samples.

To add memory to existing one-shot results without repeating latency collection:

```sh
just memory results/benchmark-game
```

This preserves original files and creates `results/benchmark-game/with-memory/`, including an updated report.
Binary and workload hashes, expected output, machine and OS must match the original run.
Unsupported timing cells and unavailable memory values display `n/a`; support reasons remain in tooltips and JSON.
`MEMORY_SAMPLES` controls memory runs in just recipes; repeated-request recipes leave memory disabled.

## Compare Monty versions

Keep a copy of the baseline binary before rebuilding with an optimization:

```bash
cp /path/to/monty /tmp/monty-baseline
# Build the candidate, then compare:
just versions /tmp/monty-baseline /path/to/monty
just versions /tmp/monty-baseline /path/to/monty results/my-optimization benchmark_game
just versions /tmp/monty-baseline /path/to/monty results/my-cold-run applications cold_process_one_shot
```

The default measures the first application request on a fresh, ready worker.
Both Monty versions use a shared shuffled sample schedule and identical workloads.
Peak RSS is measured in separate runs.
The output directory contains `monty.json` (baseline), `candidate.json`, and `comparison.html`.
Negative time change means the candidate is faster; small differences may be measurement noise.
Repeat runs on an otherwise idle machine before concluding that an optimization helps.
Unsupported workloads show `n/a` independently for each binary.

For revision labels, build details, or individual workloads, use the CLI:

```bash
flying-circus run --monty /tmp/monty-baseline --monty-revision main \
  --candidate /path/to/monty --candidate-revision my-optimization \
  --candidate-build-info 'release build' --workload capacity_planning --output results/optimization
flying-circus compare --monty-results results/optimization/monty.json \
  --candidate-results results/optimization/candidate.json --output results/optimization/comparison.html
```

The `pyperformance` suite adds Barnes–Hut, float, sequence unpacking, JSON dumps, JSON loads, and GC traversal:

```bash
just one-shot results/perf-one-shot pyperformance
just repeated results/perf-repeated pyperformance
just both results/perf-both pyperformance
```

Use `just both` without a suite argument to run all workloads in both modes.
Adapters, input sizes and compatibility changes are documented in `src/flying_circus/vendor/pyperformance/README.md`.

`just both` also writes a unified `comparison.html` at the root of its output directory.
Runtime columns show both scenarios side by side; RSS shows the separate one-shot measurements.
CPU, OS, sample counts and warmups appear above the tables.
Build details remain available in an expandable section.

Combine an existing pair without rerunning benchmarks:

```bash
just overview results/expanded-benchmarks
```

The directory must contain `one-shot/` and `repeated/` results from matching binaries and workloads.

## Text processing

```bash
just text
# Or choose the output directory:
just both results/text-processing text
```

The text suite contains seven tasks at two input sizes (roughly 10 KB and 1 MB):

| Task | Measured work |
| --- | --- |
| Line logs | Split lines, count services and errors, skip malformed records |
| Regex logs | Parse access logs, group status codes, total response bytes, calculate median/p95 latency |
| CSV aggregation | Parse quoted transaction records, reject missing customers and invalid amounts, total by month/customer |
| CSV cleanup | Handle quoted commas, escaped quotes, embedded newlines and missing names; serialize cleaned CSV |
| JSON parsing | Parse nested records and check record, amount and tag totals |
| JSON transformation | Parse, filter, sort, aggregate and serialize a summary |
| JSON Lines | Parse individual records, skip malformed JSON, deduplicate IDs and emit aggregate JSONL |

Inputs include Unicode and deterministic malformed records.
CSV parsing and writing use the same pure-Python state machine on all interpreters.
Quoted commas, escaped double quotes, embedded newlines and CRLF record separators are supported.
The standard `csv` module is used only by fixture generation and correctness tests.
The generator stores the actual UTF-8 byte count, fixture hash and checked reference output in the manifest.

Worker scenarios load fixture strings into a fresh session before request timing.
The timed request includes workload compilation, imports, parsing, processing, result generation and IPC.
Cold-process timing includes fixture initialization as part of the complete process.
Separate RSS measurements include fixture loading and the interpreter's entire process.

Regenerate fixtures and reference outputs with:

```bash
uv run python scripts/generate_text_suite.py
```

The applications suite contains six workloads; `all` selects 32 workloads.
The legacy readiness marker is excluded from normal suite selection.

## Process startup

Startup uses fresh direct processes with an empty command: `monty -c ""`, `python -c ""`, and `pypy3 -c ""`.
Timing covers process launch through exit, with normal interpreter defaults and no shell.
CPython site initialization is included.
The result is separate from first-request and repeated-request application timings.

`just both` records 50 shuffled startup samples per interpreter in `startup.json`.
The unified report places startup in its own section.
To add startup measurements to an existing pair of result directories:

```bash
just startup results/text-processing
flying-circus overview results/text-processing --output results/text-processing/with-startup.html
```

The startup command verifies that the host and binary hashes still match the application measurements.

## Published benchmarks

The `Benchmarks and Pages` workflow runs on pushes to `main`, daily at 05:17 UTC, and manually.
It installs the latest stable `pydantic-monty-runtime` wheel from PyPI with uv and compares its executable with
CPython 3.14 and PyPy 3.11 on one `ubuntu-24.04` runner.
Installation requires binary wheels; the workflow never builds Monty from source.
The resolved Monty package version and binary hash are recorded in each report.
Manual runs can select another CPython or PyPy version.
Each run measures startup first, followed by all workloads in one-shot and repeated scenarios, with separate RSS samples.

GitHub Pages serves the latest report, with Markdown and JSON downloads and an archive of the latest 90 runs.
The workflow records the Monty package versions, installation commands, executable versions, binary hashes and Actions run link.
Published wheel compiler flags and source revisions are marked unverified.
History is carried forward through a `benchmark-history` Actions artifact with a 90-day retention period.
If no successful run remains within artifact retention, history starts again.
GitHub-hosted runner hardware can vary; compare runtimes within a run and use a dedicated machine for precise historical trends.
Unexpected benchmark failures remain visible in published reports; missing reports stop deployment.

Pages must use GitHub Actions as its publishing source.
The workflow uses GitHub's standard Pages artifact deployment, with Pages write and OIDC permissions confined to the deploy job.

Published benchmark names link to their workload source at the exact harness commit used for that run.

Use `-v` or `--verbose` to see compatibility checks, the benchmark currently running,
warmups, individual timing and RSS samples, and median results:

```sh
flying-circus --quick -v -r monty -r python3 -r pypy3
```

Without verbose output, the CLI shows run phases and report paths. Failures are
always printed to stderr.
