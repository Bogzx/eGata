"""Apply SQL migrations in order against SUPABASE_DB_URL."""
from __future__ import annotations

import sys
from pathlib import Path

import psycopg

from app.config import get_settings

MIG_DIR = Path(__file__).resolve().parents[1] / "migrations"


def main() -> int:
    settings = get_settings()
    files = sorted(MIG_DIR.glob("*.sql"))
    if not files:
        print("No migrations found.", file=sys.stderr)
        return 1
    with psycopg.connect(settings.supabase_db_url, autocommit=True) as conn, conn.cursor() as cur:
        for path in files:
            print(f"Applying {path.name}...")
            sql = path.read_text(encoding="utf-8")
            cur.execute(sql)  # type: ignore[arg-type]
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
