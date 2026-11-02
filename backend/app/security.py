"""Authentication (signed bearer tokens) and role-based authorisation.

Standard-library only: PBKDF2 password hashes + HMAC-SHA256 signed tokens.
For production, swap for the hospital's identity provider (OIDC/Keycloak) -
the `current_user` dependency is the only integration point.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Callable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ai.orchestrator import UserCtx
from common.settings import get_settings
from database.models import User
from database.session import get_session

DEMO_USERS = [
    # username, display name, role, facility (None = all facilities)
    ("dr.ananya", "Dr. Ananya Rao", "doctor", None),
    ("rekha.coord", "Rekha S. (Care Coordinator)", "coordinator", None),
    ("admin.ops", "Hospital Administrator", "admin", None),
]
DEMO_PASSWORD = "demo123"


def hash_password(pw: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    salt_hex, dk_hex = stored.split("$")
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), 200_000)
    return hmac.compare_digest(dk.hex(), dk_hex)


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(user: User) -> str:
    s = get_settings()
    body = _b64(json.dumps({"sub": user.username, "role": user.role, "exp": int(time.time()) + s.token_ttl_minutes * 60})
                .encode())
    sig = _b64(hmac.new(s.secret_key.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def read_token(token: str) -> dict:
    s = get_settings()
    try:
        body, sig = token.split(".")
        good = _b64(hmac.new(s.secret_key.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            raise ValueError("bad signature")
        data = json.loads(_unb64(body))
        if data["exp"] < time.time():
            raise ValueError("expired")
        return data
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}") from exc


def seed_users(session: Session) -> None:
    for username, name, role, fac in DEMO_USERS:
        if not session.get(User, username):
            session.add(User(username=username, display_name=name, role=role, facility_id=fac,
                             password_hash=hash_password(DEMO_PASSWORD)))


def current_user(authorization: str = Header(default=""), session: Session = Depends(get_session, scope="function")) -> UserCtx:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    data = read_token(authorization.split(" ", 1)[1])
    u = session.get(User, data["sub"])
    if not u:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown user")
    return UserCtx(username=u.username, role=u.role, display_name=u.display_name, facility_id=u.facility_id)


def require_roles(*roles: str) -> Callable:
    def dep(user: UserCtx = Depends(current_user)) -> UserCtx:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"role '{user.role}' is not allowed here")
        return user

    return dep
