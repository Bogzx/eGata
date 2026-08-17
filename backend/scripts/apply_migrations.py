"""Apply SQL migrations in order against SUPABASE_DB_URL.

Thin wrapper kept for the name RUNBOOK.md and older docs use. The
implementation lives in `scripts.bootstrap_local_db`, which additionally
tracks what has already been applied (so a re-run is safe) and installs an
`auth.uid()` stub when the target is not Supabase.
"""
from __future__ import annotations

import sys

from scripts.bootstrap_local_db import main

if __name__ == "__main__":
    sys.exit(main())
