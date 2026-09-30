"""Citizen profile endpoints."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.address import parse_ro_address
from app.db import get_pg_connection
from app.models import CitizenResponse, PatchAttributesRequest
from app.security import current_citizen_id

router = APIRouter(prefix="/citizens", tags=["citizens"])


# Parsed parts of `current_address`, stored with the string they came from:
# {"from": "<current_address>", "parts": {"strada": ..., "numar": ..., ...}}.
# Written at login and seed time; ignored (and re-parsed) once the address
# no longer matches, so an edited address never serves stale parts.
ADDRESS_PARTS_KEY = "current_address_parts"


def address_parts(attrs: dict[str, Any]) -> dict[str, str]:
    address = attrs.get("current_address")
    if not isinstance(address, str) or not address.strip():
        return {}
    cached = attrs.get(ADDRESS_PARTS_KEY)
    if isinstance(cached, dict) and cached.get("from") == address and isinstance(cached.get("parts"), dict):
        return {k: str(v) for k, v in cached["parts"].items()}
    return parse_ro_address(address)


def profile_attributes(row: dict[str, Any]) -> dict[str, Any]:
    """The citizen's attributes as the agent and autofill see them.

    The LLM only sees `attributes` in the system prompt (see
    session_engine.build_system_instruction), and autofill matches field
    names against them, so core profile columns are flattened in and the
    single-string address is split into the parts the forms ask for.
    Attributes set explicitly always win over derived ones.
    """
    attrs = dict(row.get("attributes") or {})
    nume, prenume = row.get("nume"), row.get("prenume")
    if nume and prenume:
        attrs.setdefault("nume_complet", f"{prenume} {nume}")
    if row.get("email"):
        attrs.setdefault("email", row["email"])
    if row.get("phone"):
        attrs.setdefault("telefon", row["phone"])
    if row.get("cnp"):
        attrs.setdefault("cnp", row["cnp"])
    for key, value in address_parts(attrs).items():
        attrs.setdefault(key, value)
    attrs.pop(ADDRESS_PARTS_KEY, None)
    # Field-name aliases — many procedure schemas use `ap_domiciliu` /
    # `nr_domiciliu` / `strada_domiciliu` while the profile stores them under
    # the shorter `apartament` / `numar` / `strada`. Mirror them so the LLM
    # can call set_field("ap_domiciliu", ...) without any semantic mapping.
    for src, dst in (
        ("apartament", "ap_domiciliu"),
        ("strada", "strada_domiciliu"),
        ("numar", "nr_domiciliu"),
        ("current_address", "adresa_curenta"),
        ("current_address", "adresa_domiciliu"),
    ):
        if attrs.get(src) and not attrs.get(dst):
            attrs[dst] = attrs[src]
    return attrs


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
    data["attributes"] = profile_attributes(data)
    return data


def store_address_parts(citizen_id: UUID | str) -> dict[str, str]:
    """Parse the profile address once and keep the parts (login / seed time).

    No-op when the stored parts already belong to the current address.
    Returns the parts now in effect.
    """
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute("select attributes from citizens where id = %s;", (str(citizen_id),))
        row = cur.fetchone()
        if row is None:
            return {}
        attrs = row["attributes"] or {}
        address = attrs.get("current_address")
        cached = attrs.get(ADDRESS_PARTS_KEY)
        if not isinstance(address, str) or not address.strip():
            return {}
        if isinstance(cached, dict) and cached.get("from") == address:
            return dict(cached.get("parts") or {})
        parts = parse_ro_address(address)
        cur.execute(
            "update citizens set attributes = attributes || jsonb_build_object(%s::text, %s::jsonb) "
            "where id = %s;",
            (ADDRESS_PARTS_KEY, json.dumps({"from": address, "parts": parts}, ensure_ascii=False),
             str(citizen_id)),
        )
        conn.commit()
    return parts


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
