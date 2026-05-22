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
    return dict(row)


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
