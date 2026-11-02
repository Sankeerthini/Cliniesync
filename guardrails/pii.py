"""Personal-data detection and redaction (for logs and admin-facing outputs)."""
from __future__ import annotations

import re

PATTERNS = {
    "phone": re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)"),
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "id_number": re.compile(r"(?<!\d)\d{12}(?!\d)"),               # Aadhaar/RCH-like 12-digit numbers
    "patient_id": re.compile(r"\bCS-\d{6}\b"),
}


def detect(text: str) -> list[str]:
    return [k for k, rx in PATTERNS.items() if rx.search(text or "")]


def redact(text: str, kinds: tuple[str, ...] = ("phone", "email", "id_number")) -> str:
    out = text or ""
    for k in kinds:
        out = PATTERNS[k].sub(f"[{k.upper()}]", out)
    return out
