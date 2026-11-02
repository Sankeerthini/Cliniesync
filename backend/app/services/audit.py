"""Audit trail helper - every operational action is recorded (who, what, when, decision)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ai.orchestrator import UserCtx
from database.models import AuditLog


def audit(s: Session, user: UserCtx, action: str, target: str | None = None, decision: str | None = None,
          **detail) -> None:
    s.add(AuditLog(at=datetime.now(), username=user.username, role=user.role, action=action, target=target,
                   decision=decision, detail=detail or None))
