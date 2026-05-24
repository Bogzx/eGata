"""Citizen profile endpoints."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_pg_connection
from app.models import CitizenResponse, PatchAttributesRequest
from app.security import current_citizen_id

router = APIRouter(prefix="/citizens", tags=["citizens"])


# Demo hack: seed data stores address as a single string in `current_address`,
# but procedures like placuta-numar-postal expect a separate `apartament`.
# Inject per-persona placeholders so the LLM auto-fills instead of asking.
_DEMO_APARTAMENT_BY_CITIZEN: dict[str, str] = {
    "11111111-1111-1111-1111-111111111111": "3",   # Maria — bloc
    "22222222-2222-2222-2222-222222222222": "12",  # Andrei — bloc
    "33333333-3333-3333-3333-333333333333": "7B",  # Elena — bloc
}


def fetch_citizen_by_id(citizen_id: UUID) -> dict[str, Any]:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id, cnp, nume, prenume, data_nasterii, email, phone, attributes "
            "from citizens where id = %s;",
            (str(citizen_id),),
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Citizen not found")
    data = dict(row)
    attrs = data.get("attributes") or {}
    fallback = _DEMO_APARTAMENT_BY_CITIZEN.get(str(citizen_id))
    # Override on falsy values (None / empty string) too — seed data may
    # contain `apartament: ""` which would defeat setdefault.
    if fallback is not None and not attrs.get("apartament"):
        attrs["apartament"] = fallback
    # The LLM only sees `attributes` in the system prompt (see
    # session_engine.build_system_instruction). Flatten core profile fields
    # into attrs so it can auto-fill nume_complet/telefon/email/cnp without
    # having to ask.
    nume = data.get("nume")
    prenume = data.get("prenume")
    if nume and prenume:
        attrs.setdefault("nume_complet", f"{prenume} {nume}")
    if data.get("email"):
        attrs.setdefault("email", data["email"])
    if data.get("phone"):
        attrs.setdefault("telefon", data["phone"])
    if data.get("cnp"):
        attrs.setdefault("cnp", data["cnp"])
    # Field-name aliases — many procedure schemas use `ap_domiciliu` /
    # `nr_domiciliu` / `strada_domiciliu` while the profile stores them under
    # the shorter `apartament` / `numar` / `strada`. Mirror them so the LLM
    # can call set_field("ap_domiciliu", ...) without any semantic mapping.
    for src, dst in (
        ("apartament", "ap_domiciliu"),
        ("strada", "strada_domiciliu"),
        ("numar", "nr_domiciliu"),
        ("current_address", "adresa_curenta"),
    ):
        if attrs.get(src) and not attrs.get(dst):
            attrs[dst] = attrs[src]
    data["attributes"] = attrs
    return data


def patch_citizen_attributes(citizen_id: UUID, patch: dict[str, Any]) -> dict[str, Any]:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "update citizens set attributes = attributes || %s::jsonb where id = %s "
            "returning id, cnp, nume, prenume, data_nasterii, email, phone, attributes;",
            (json.dumps(patch, ensure_ascii=False), str(citizen_id)),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Citizen not found")
        conn.commit()
    return dict(row)


@router.get("/me", response_model=CitizenResponse)
def me(citizen_id: UUID = Depends(current_citizen_id)) -> CitizenResponse:
    data = fetch_citizen_by_id(citizen_id)
    return CitizenResponse(**data)


@router.patch("/me/attributes", response_model=CitizenResponse)
def patch_attributes(
    req: PatchAttributesRequest,
    citizen_id: UUID = Depends(current_citizen_id),
) -> CitizenResponse:
    data = patch_citizen_attributes(citizen_id, req.attributes)
    return CitizenResponse(**data)
