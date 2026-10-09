set dotenv-load
set positional-arguments

export MONTY_BIN := env("MONTY_BIN", "monty")
export CPYTHON_BIN := env("CPYTHON_BIN", "python3")
export PYPY_BIN := env("PYPY_BIN", "auto")
export MONTY_REVISION := env("MONTY_REVISION", "unverified-local")
export MONTY_BUILD_INFO := env("MONTY_BUILD_INFO", "Source revision and compiler flags unverified")
export SAMPLES := env("SAMPLES", "20")
export MEMORY_SAMPLES := env("MEMORY_SAMPLES", "3")
export TIMEOUT := env("TIMEOUT", "30")
export LEGACY_CLI_SUMMARY := env("LEGACY_CLI_SUMMARY", "0")
stamp := `date -u +%Y%m%dT%H%M%SZ`

# List common commands.
default:
    @just --list

# Install the package and locked dependencies.
install:
    uv sync --frozen

# Run the correctness and harness tests.
test:
    uv run --frozen python -m unittest discover -s tests

# First application request after worker readiness; a fresh worker per sample.
one-shot output=("results/" + stamp + "-one-shot-worker") suite="applications": (_run "warm_worker_one_shot" suite output "0")

# Fresh CLI process per sample, including process startup.
cold output=("results/" + stamp + "-one-shot-process") suite="applications": (_run "cold_process_one_shot" suite output "0")

# Repeated requests on reused workers, with explicit warmups.
repeated output=("results/" + stamp + "-repeated") suite="applications" warmups="3": (_run "repeated_requests" suite output warmups)

# One-shot computational application workloads.
compute output=("results/" + stamp + "-compute"): (_run "warm_worker_one_shot" "applications" output "0" "--workload" "capacity_planning" "--workload" "portfolio_risk" "--workload" "ticket_search")

# Pyperformance Benchmark Game suite, with dynamic compatibility checks.
game output=("results/" + stamp + "-benchmark-game") scenario="warm_worker_one_shot": (_run scenario "benchmark_game" output "auto")

# Both suites, measuring first requests on fresh workers.
all output=("results/" + stamp + "-all"): (_run "warm_worker_one_shot" "all" output "0")

# Generate a comparison from an existing run directory.
report directory output=(directory + "/comparison.html"):
    #!/usr/bin/env bash
    set -euo pipefail
    args=(--monty-results "$1/monty.json" --cpython-results "$1/cpython.json" --output "$2")
    if [[ -f "$1/pypy.json" ]]; then args+=(--pypy-results "$1/pypy.json"); fi
    uv run --frozen flying-circus compare "${args[@]}"

# Add peak RSS to existing one-shot results, preserving the original directory.
memory directory output=(directory + "/with-memory"):
    #!/usr/bin/env bash
    set -euo pipefail
    uv run --frozen flying-circus memory "$1" --output "$2" --samples "$MEMORY_SAMPLES" --timeout "$TIMEOUT"
    just report "$2"

[private]
_run scenario suite output warmups *extra:
    #!/usr/bin/env bash
    set -euo pipefail
    scenario="$1"; suite="$2"; output="$3"; warmups="$4"; shift 4
    monty="$(command -v "$MONTY_BIN")" || { echo "Monty not found: set MONTY_BIN in .env or your environment" >&2; exit 1; }
    cpython="$(command -v "$CPYTHON_BIN")" || { echo "CPython not found: set CPYTHON_BIN" >&2; exit 1; }
    cpython_version="$("$cpython" -c 'import platform; print("cpython-" + platform.python_version())')"
    args=(--scenario "$scenario" --suite "$suite" --output "$output" --samples "$SAMPLES" --timeout "$TIMEOUT"
          --monty "$monty" --monty-revision "$MONTY_REVISION" --monty-build-info "$MONTY_BUILD_INFO"
          --cpython "$cpython" --cpython-revision "$cpython_version")
    if [[ "$scenario" == repeated_requests ]]; then args+=(--memory-samples 0); else args+=(--memory-samples "$MEMORY_SAMPLES"); fi
    if [[ "$warmups" != auto ]]; then args+=(--warmups "$warmups"); fi
    if [[ "$LEGACY_CLI_SUMMARY" == 1 ]]; then args+=(--legacy-cli-summary); fi
    pypy=""
    if [[ "$PYPY_BIN" == auto ]]; then
        pypy="$(command -v pypy3 || true)"
    elif [[ -n "$PYPY_BIN" ]]; then
        pypy="$(command -v "$PYPY_BIN")" || { echo "PyPy not found: $PYPY_BIN" >&2; exit 1; }
    fi
    if [[ -n "$pypy" ]]; then
        pypy_version="$("$pypy" -c 'import platform, sys; v = sys.pypy_version_info; print("pypy-%s.%s.%s-python-%s" % (v.major, v.minor, v.micro, platform.python_version()))')"
        args+=(--pypy "$pypy" --pypy-revision "$pypy_version")
    fi
    uv run --frozen flying-circus run "${args[@]}" "$@"
    report=(--monty-results "$output/monty.json" --cpython-results "$output/cpython.json" --output "$output/comparison.html")
    if [[ -n "$pypy" ]]; then report+=(--pypy-results "$output/pypy.json"); fi
    uv run --frozen flying-circus compare "${report[@]}"

# Compare two Monty binaries using shuffled samples; negative time change means faster.
versions baseline candidate output=("results/" + stamp + "-monty-versions") suite="applications" scenario="warm_worker_one_shot":
    #!/usr/bin/env bash
    set -euo pipefail
    baseline="$(command -v "$1")"
    candidate="$(command -v "$2")"
    args=(--monty "$baseline" --candidate "$candidate" --monty-revision baseline --candidate-revision candidate
          --samples "$SAMPLES" --timeout "$TIMEOUT" --output "$3" --suite "$4" --scenario "$5")
    if [[ "$5" == repeated_requests ]]; then args+=(--memory-samples 0); else args+=(--memory-samples "$MEMORY_SAMPLES"); fi
    if [[ "$LEGACY_CLI_SUMMARY" == 1 ]]; then args+=(--legacy-cli-summary); fi
    uv run --frozen flying-circus run "${args[@]}"
    uv run --frozen flying-circus compare --monty-results "$3/monty.json" --candidate-results "$3/candidate.json" --output "$3/comparison.html"

# Run the same suite in both one-shot and repeated-request modes.
both output=("results/" + stamp + "-both") suite="all":
    #!/usr/bin/env bash
    set -euo pipefail
    just one-shot "$1/one-shot" "$2"
    just repeated "$1/repeated" "$2" 3
    uv run --frozen flying-circus startup "$1" --output "$1/startup.json" --timeout "$TIMEOUT"
    uv run --frozen flying-circus overview "$1" --output "$1/comparison.html"

# Combine existing one-shot and repeated results on one page.
overview directory output=(directory + "/comparison.html"):
    uv run --frozen flying-circus overview "{{directory}}" --output "{{output}}"

# Text-processing tasks at small and medium input sizes, in both scenarios.
text output=("results/" + stamp + "-text"): (both output "text")

# Measure fresh process startup using an empty -c command.
startup directory output=(directory + "/startup.json"):
    uv run --frozen flying-circus startup "{{directory}}" --output "{{output}}" --timeout "$TIMEOUT"
