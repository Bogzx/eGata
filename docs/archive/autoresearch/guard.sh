#!/usr/bin/env bash
# Guard command: frontend build + backend collect must succeed.
# Exits 0 on success, non-zero on failure.
set -e
cd "$(dirname "$0")/../../.."  # repo root (moved to docs/archive/autoresearch)

# Backend: tests must at least *collect* (no syntax/import errors).
pushd backend > /dev/null
python -m pytest --collect-only -q > /dev/null
popd > /dev/null

# Frontend: typecheck must pass (build is expensive — typecheck is the cheap proxy).
pushd frontend > /dev/null
npx --no-install tsc --noEmit > /dev/null
popd > /dev/null

echo "guard: ok"
