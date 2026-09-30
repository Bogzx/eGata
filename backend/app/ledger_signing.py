"""Ed25519 signatures over ledger chain heads.

The hash chain alone is unkeyed: anyone who can write to the database can
rebuild a chain whose hashes all check out. Each appended row is therefore
also signed, with a key that never touches the database:

    statement = canonical_json({
        "v": 1, "type": "egata-ledger-head", "key_id": ...,
        "citizen_id": ..., "document_id": ... | null,
        "row_id": ..., "row_hash": ...,
    })
    signature = Ed25519(private_key, statement.encode("utf-8"))

row_hash commits to every earlier row of the chain, so a signature on row N
attests the whole chain up to N. Rewriting history now also needs the
private key, and a citizen who kept a signed head (verify_ledger.py
--save-receipt) holds proof the operator cannot deny.

Key sources, in order: LEDGER_SIGNING_KEY (PEM, or base64 of the 32-byte
seed), then the PEM at LEDGER_SIGNING_KEY_FILE. If neither exists the key is
generated and written to that file with a loud warning — fine for a laptop,
not for production, where the key belongs in a secret store. Public keys are
published at GET /.well-known/egata-ledger-keys.json; retired keys stay
verifiable via LEDGER_RETIRED_PUBLIC_KEYS.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.config import get_settings

log = logging.getLogger(__name__)

STATEMENT_VERSION = 1
STATEMENT_TYPE = "egata-ledger-head"
DEFAULT_KEY_FILE = "./.data/ledger-signing-key.pem"


@dataclass(frozen=True)
class SigningKey:
    private: Ed25519PrivateKey
    key_id: str
    public_b64: str
    source: str  # "env" | "file" | "generated"


def _raw_public(pub: Ed25519PublicKey) -> bytes:
    return pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def key_id_for(public_raw: bytes) -> str:
    return "ed25519:" + hashlib.sha256(public_raw).hexdigest()[:16]


def _load_private(text: str) -> Ed25519PrivateKey:
    text = text.strip()
    if text.startswith("-----BEGIN"):
        key = serialization.load_pem_private_key(text.encode(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise RuntimeError("LEDGER_SIGNING_KEY is a PEM key but not Ed25519")
        return key
    seed = base64.b64decode(text)
    if len(seed) != 32:
        raise RuntimeError("LEDGER_SIGNING_KEY must be a PEM key or base64 of a 32-byte seed")
    return Ed25519PrivateKey.from_private_bytes(seed)


def _pem(key: Ed25519PrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


@lru_cache(maxsize=1)
def signing_key() -> SigningKey:
    settings = get_settings()
    path = Path(settings.ledger_signing_key_file or DEFAULT_KEY_FILE).expanduser()
    if settings.ledger_signing_key:
        private, source = _load_private(settings.ledger_signing_key), "env"
    elif path.is_file():
        private, source = _load_private(path.read_text(encoding="utf-8")), "file"
    else:
        private, source = Ed25519PrivateKey.generate(), "generated"
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(_pem(private))
        log.warning(
            "LEDGER SIGNING KEY GENERATED at %s. Every ledger row is signed with it; "
            "losing it makes new rows unverifiable against the published key, and "
            "anyone who reads it can forge ledger signatures. For anything but local "
            "development set LEDGER_SIGNING_KEY from a secret store.",
            path.resolve(),
        )
    raw = _raw_public(private.public_key())
    return SigningKey(private, key_id_for(raw), base64.b64encode(raw).decode(), source)


def statement(
    *, key_id: str, citizen_id: str, document_id: str | None, row_id: int, row_hash: str
) -> dict[str, Any]:
    return {
        "v": STATEMENT_VERSION,
        "type": STATEMENT_TYPE,
        "key_id": key_id,
        "citizen_id": citizen_id,
        "document_id": document_id,
        "row_id": row_id,
        "row_hash": row_hash,
    }


def sign_row(
    *, citizen_id: str, document_id: str | None, row_id: int, row_hash: str
) -> tuple[str, str]:
    """(key_id, base64 signature) for one ledger row."""
    from app.ledger import canonical_json  # local: ledger imports this module

    key = signing_key()
    stmt = statement(
        key_id=key.key_id,
        citizen_id=citizen_id,
        document_id=document_id,
        row_id=row_id,
        row_hash=row_hash,
    )
    sig = key.private.sign(canonical_json(stmt).encode("utf-8"))
    return key.key_id, base64.b64encode(sig).decode()


def published_keys() -> list[dict[str, str]]:
    """Current key plus any retired ones still needed to verify old rows."""
    current = signing_key()
    keys = [{"key_id": current.key_id, "algorithm": "Ed25519",
             "public_key": current.public_b64, "status": "current"}]
    for item in (get_settings().ledger_retired_public_keys or "").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            raw = base64.b64decode(item, validate=True)
        except ValueError:
            raw = b""
        if len(raw) != 32:
            log.warning("ignoring LEDGER_RETIRED_PUBLIC_KEYS entry that is not 32 bytes")
            continue
        keys.append({"key_id": key_id_for(raw), "algorithm": "Ed25519",
                     "public_key": item, "status": "retired"})
    return keys
