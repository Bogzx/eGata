"""Identity endpoints: ROeID mock, MRZ lookup, OTP."""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from twilio.rest import Client as TwilioClient

from app.config import get_settings
from app.db import get_pg_connection
from app.models import (
    ChallengeResponse,
    LoginMRZRequest,
    LoginROeIDRequest,
    OTPRequest,
    OTPResponse,
)
from app.security import mint_access_token

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("auth")

DEFAULT_DEMO_PERSONA = "maria-ionescu"
MOCK_OTP_CODE = "123456"
CHALLENGE_TTL_SECONDS = 300

PERSONA_TO_CNP: dict[str, str] = {
    "maria-ionescu": "2851014123456",
    "andrei-popa": "1900512123456",
    "elena-dumitru": "2620908123456",
}


def phone_hint(phone: str) -> str:
    last4 = phone[-4:] if len(phone) >= 4 else phone
    return f"***{last4}"


def fetch_citizen_by_persona_id(persona_id: str) -> dict[str, Any]:
    cnp = PERSONA_TO_CNP.get(persona_id)
    if cnp is None:
        raise HTTPException(status_code=404, detail=f"Unknown persona: {persona_id}")
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute("select id, phone, nume from citizens where cnp = %s;", (cnp,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Citizen not found")
    return dict(row)


def fetch_citizen_by_mrz(cnp: str, nume: str, prenume: str) -> dict[str, Any]:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id, phone, nume from citizens "
            "where cnp = %s and lower(nume) = lower(%s) and lower(prenume) = lower(%s);",
            (cnp, nume, prenume),
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="No citizen matches MRZ data")
    return dict(row)


def issue_otp(citizen_id: UUID | str, phone: str) -> str:
    settings = get_settings()
    challenge_id = f"ch_{secrets.token_urlsafe(12)}"
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=CHALLENGE_TTL_SECONDS)
    twilio_sid: str | None = None
    log.info(
        "issue_otp: citizen=%s phone_hint=%s mock=%s challenge=%s",
        citizen_id,
        phone_hint(phone),
        settings.mock_otp,
        challenge_id,
    )

    if not settings.mock_otp:
        try:
            client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
            verification = client.verify.v2.services(
                settings.twilio_verify_service_sid
            ).verifications.create(to=phone, channel="sms")
            twilio_sid = verification.sid
            log.info(
                "issue_otp: twilio sent challenge=%s sid=%s status=%s",
                challenge_id,
                twilio_sid,
                verification.status,
            )
        except Exception:
            log.exception(
                "issue_otp: twilio Verify call failed challenge=%s phone_hint=%s",
                challenge_id,
                phone_hint(phone),
            )
            raise

    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "insert into otp_challenges (id, citizen_id, phone, twilio_sid, expires_at) "
            "values (%s, %s, %s, %s, %s);",
            (challenge_id, str(citizen_id), phone, twilio_sid, expires_at),
        )
        conn.commit()

    return challenge_id


def verify_otp_and_consume(challenge_id: str, code: str) -> str:
    settings = get_settings()
    log.info(
        "verify_otp: in challenge=%s code_len=%d mock=%s",
        challenge_id,
        len(code or ""),
        settings.mock_otp,
    )
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select citizen_id, phone, twilio_sid, expires_at, consumed "
            "from otp_challenges where id = %s for update;",
            (challenge_id,),
        )
        row = cur.fetchone()
        if row is None:
            log.warning("verify_otp: unknown challenge=%s", challenge_id)
            raise ValueError("unknown challenge")
        if row["consumed"]:
            log.warning("verify_otp: replay attempt challenge=%s", challenge_id)
            raise ValueError("challenge already used")
        if row["expires_at"] < datetime.now(timezone.utc):
            log.warning(
                "verify_otp: expired challenge=%s expires_at=%s",
                challenge_id,
                row["expires_at"],
            )
            raise ValueError("challenge expired")

        if settings.mock_otp:
            if code != MOCK_OTP_CODE:
                log.warning(
                    "verify_otp: mock mode rejected wrong code challenge=%s",
                    challenge_id,
                )
                raise ValueError("invalid code")
            log.info("verify_otp: mock approved challenge=%s", challenge_id)
        else:
            try:
                client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
                check = client.verify.v2.services(
                    settings.twilio_verify_service_sid
                ).verification_checks.create(to=row["phone"], code=code)
            except Exception:
                log.exception(
                    "verify_otp: twilio verification_checks call failed challenge=%s",
                    challenge_id,
                )
                raise
            log.info(
                "verify_otp: twilio status=%s challenge=%s phone_hint=%s",
                check.status,
                challenge_id,
                phone_hint(row["phone"]),
            )
            if check.status != "approved":
                raise ValueError("invalid code")

        cur.execute("update otp_challenges set consumed = true where id = %s;", (challenge_id,))
        conn.commit()
        log.info(
            "verify_otp: ok challenge=%s citizen=%s",
            challenge_id,
            row["citizen_id"],
        )
        return str(row["citizen_id"])


@router.post("/login-roeid", response_model=ChallengeResponse)
def login_roeid(req: LoginROeIDRequest) -> ChallengeResponse:
    persona_id = req.persona_id or DEFAULT_DEMO_PERSONA
    log.info("login-roeid: persona=%s", persona_id)
    citizen = fetch_citizen_by_persona_id(persona_id)
    challenge_id = issue_otp(citizen["id"], citizen["phone"])
    return ChallengeResponse(challenge_id=challenge_id, phone_hint=phone_hint(citizen["phone"]))


@router.post("/login-mrz", response_model=ChallengeResponse)
def login_mrz(req: LoginMRZRequest) -> ChallengeResponse:
    log.info(
        "login-mrz: cnp_hint=***%s",
        req.cnp[-4:] if len(req.cnp) >= 4 else req.cnp,
    )
    citizen = fetch_citizen_by_mrz(req.cnp, req.nume, req.prenume)
    challenge_id = issue_otp(citizen["id"], citizen["phone"])
    return ChallengeResponse(challenge_id=challenge_id, phone_hint=phone_hint(citizen["phone"]))


@router.post("/otp", response_model=OTPResponse)
def otp(req: OTPRequest) -> OTPResponse:
    try:
        citizen_id = verify_otp_and_consume(req.challenge_id, req.code)
    except ValueError as exc:
        log.warning(
            "otp: 401 challenge=%s reason=%s",
            req.challenge_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    token = mint_access_token(citizen_id)
    log.info("otp: ok citizen=%s token_len=%d", citizen_id, len(token))
    return OTPResponse(access_token=token, citizen_id=UUID(citizen_id))
