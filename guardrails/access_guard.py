"""ACCESS GUARD - role-based access control + minimum-necessary data scopes."""
from __future__ import annotations

from dataclasses import dataclass

from guardrails.policy import ROLE_INTENTS, ROLE_SCOPES


@dataclass
class AccessDecision:
    allowed: bool
    scopes: set[str]
    detail: str


def check(role: str, intent: str, patient_level: bool) -> AccessDecision:
    scopes = ROLE_SCOPES.get(role, set())
    if intent not in ROLE_INTENTS.get(role, set()):
        return AccessDecision(False, scopes, f"role '{role}' may not run '{intent}'")
    if patient_level and "identifiers" not in scopes:
        return AccessDecision(False, scopes, f"role '{role}' sees de-identified aggregates only")
    return AccessDecision(True, scopes, f"role '{role}' allowed; scopes: {', '.join(sorted(scopes)) or 'aggregate-only'}")


def has(scopes: set[str], scope: str) -> bool:
    return scope in scopes
