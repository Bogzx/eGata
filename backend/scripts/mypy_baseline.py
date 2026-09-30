"""mypy with a ratchet: known findings are tolerated, new ones fail.

`app/` is clean under the strict config in mypy.ini and must stay clean; the
hackathon tests and one-off scripts still carry findings, recorded in
`mypy-baseline.txt`. CI runs this instead of bare mypy:

    python -m scripts.mypy_baseline            # fail on anything not in the baseline
    python -m scripts.mypy_baseline --update   # after fixing findings: shrink it

Findings are compared as "path: [code] message" with line numbers stripped, so
unrelated edits that shift lines do not churn the baseline; duplicates are
counted, so a second copy of a known finding in the same file is still new.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
BASELINE = BACKEND / "mypy-baseline.txt"
TARGETS = ["app", "scripts", "tests"]
_LINE = re.compile(r"^(?P<path>[^:\s]+\.py):\d+(?::\d+)?: error: (?P<msg>.*?)\s+\[(?P<code>[\w-]+)\]$")


def run_mypy() -> Counter[str]:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "mypy", "--explicit-package-bases", "--no-error-summary", *TARGETS],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
    )
    found: Counter[str] = Counter()
    for line in proc.stdout.splitlines():
        m = _LINE.match(line.strip())
        if m:
            msg = re.sub(r"on line \d+", "on line N", m["msg"])
            found[f"{m['path']}: [{m['code']}] {msg}"] += 1
    if proc.returncode not in (0, 1) or (proc.returncode == 1 and not found):
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit("mypy did not run cleanly (see output above)")
    return found


def load_baseline() -> Counter[str]:
    if not BASELINE.exists():
        return Counter()
    lines = [ln for ln in BASELINE.read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("#")]
    return Counter(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="mypy with a baseline")
    ap.add_argument("--update", action="store_true", help="rewrite mypy-baseline.txt from the current findings")
    args = ap.parse_args(argv)

    current = run_mypy()
    if args.update:
        header = "# Known mypy findings (scripts/mypy_baseline.py). Shrink it; never grow it.\n"
        BASELINE.write_text(header + "".join(f"{f}\n" for f in sorted(current.elements())), encoding="utf-8")
        print(f"baseline: {sum(current.values())} findings written to {BASELINE.name}")
        return 0

    baseline = load_baseline()
    new = current - baseline
    fixed = baseline - current
    if new:
        print(f"mypy: {sum(new.values())} finding(s) not in the baseline:")
        for f in sorted(new.elements()):
            print(f"  {f}")
        print("Fix them (preferred) — the baseline is for old code, not new code.")
        return 1
    print(f"mypy: no new findings ({sum(current.values())} known, app/ clean).")
    if fixed:
        print(f"{sum(fixed.values())} baseline finding(s) are fixed; run with --update to shrink it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
