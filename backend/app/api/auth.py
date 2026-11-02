from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ai.orchestrator import UserCtx
from backend.app.schemas.requests import LoginIn
from backend.app.security import DEMO_PASSWORD, DEMO_USERS, current_user, make_token, verify_password
from backend.app.services.audit import audit
from database.models import User
from database.session import get_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, s: Session = Depends(get_session, scope="function")):
    u = s.get(User, body.username.strip())
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "invalid username or password")
    audit(s, UserCtx(u.username, u.role), "login", decision="allowed")
    return {"token": make_token(u), "user": {"username": u.username, "display_name": u.display_name, "role": u.role}}


@router.get("/me")
def me(user: UserCtx = Depends(current_user)):
    return {"username": user.username, "display_name": user.display_name, "role": user.role}


@router.get("/demo-users")
def demo_users():
    """Demo accounts shown on the login screen (synthetic-data demo only)."""
    return {"password": DEMO_PASSWORD,
            "users": [{"username": u, "display_name": n, "role": r} for u, n, r, _ in DEMO_USERS]}
