#!/usr/bin/env bash
# Verify command: counts failures across backend + frontend.
# Outputs a single integer (total failure count) on stdout.
# Lower is better.
#
# Failure sources (each weighted 1):
#   - backend pytest failures
#   - backend pytest errors (collection / runtime)
#   - frontend vitest failures
#   - frontend tsc errors
#
# Build (next build) is reserved for the guard, not the metric.

set +e
cd "$(dirname "$0")/.."

backend_fail=0
backend_err=0
front_fail=0
tsc_err=0

# --- Backend pytest ---
pushd backend > /dev/null
out=$(python -m pytest --tb=no -q 2>&1)
# Pull the final summary line e.g. "1 failed, 92 passed, 3 skipped"
backend_fail=$(printf '%s\n' "$out" | grep -oE '[0-9]+ failed' | head -1 | grep -oE '[0-9]+' || true)
backend_err=$(printf '%s\n' "$out" | grep -oE '[0-9]+ errors?' | head -1 | grep -oE '[0-9]+' || true)
backend_fail=${backend_fail:-0}
backend_err=${backend_err:-0}
popd > /dev/null

# --- Frontend vitest ---
pushd frontend > /dev/null
out=$(npx --no-install vitest run --reporter=basic 2>&1)
# vitest summary line: "Tests  N failed | M passed"
front_fail=$(printf '%s\n' "$out" | grep -oE '[0-9]+ failed' | head -1 | grep -oE '[0-9]+' || true)
front_fail=${front_fail:-0}

# --- Frontend typecheck ---
tsc_out=$(npx --no-install tsc --noEmit 2>&1)
# Each error line looks like "src/x.ts(12,3): error TS1234: ..."
tsc_err=$(printf '%s\n' "$tsc_out" | grep -cE ': error TS[0-9]+' || true)
tsc_err=${tsc_err:-0}
popd > /dev/null

total=$((backend_fail + backend_err + front_fail + tsc_err))
echo "$total"
