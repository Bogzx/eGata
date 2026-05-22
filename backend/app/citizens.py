"""Citizen profile endpoints."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_pg_connection
from app.models import CitizenResponse
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


@router.get("/me", response_model=CitizenResponse)
def me(citizen_id: UUID = Depends(current_citizen_id)) -> CitizenResponse:
    data = fetch_citizen_by_id(citizen_id)
    return CitizenResponse(**data)
