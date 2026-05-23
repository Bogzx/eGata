"""Institutions catalog — loads JSON files from backend/institutions/."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.models import Institutie

INSTITUTIONS_DIR = Path(__file__).resolve().parent.parent / "institutions"


@lru_cache(maxsize=1)
def get_institutions_registry() -> dict[str, Institutie]:
    out: dict[str, Institutie] = {}
    for path in sorted(INSTITUTIONS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        inst = Institutie.model_validate(data)
        if inst.id != path.stem:
            raise ValueError(f"Institution id {inst.id!r} does not match filename {path.stem!r}")
        out[inst.id] = inst
    if not out:
        raise RuntimeError(f"No institutions found in {INSTITUTIONS_DIR}")
    return out


def get_institution(institutie_id: str) -> Institutie | None:
    return get_institutions_registry().get(institutie_id)
