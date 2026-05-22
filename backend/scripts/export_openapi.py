"""Dump FastAPI's OpenAPI schema as YAML to contracts/openapi.yaml."""
from __future__ import annotations

from pathlib import Path

import yaml

from app.main import app

OUT = Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"


def main() -> None:
    schema = app.openapi()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(yaml.safe_dump(schema, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
