"""Cleaning primitives: dates, phones, names, numbers, de-duplication, quarantine."""
from __future__ import annotations

import math
import re
from datetime import date, datetime

import pandas as pd

_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d-%b-%Y", "%d-%b-%y", "%d-%m-%Y", "%d/%m/%y",
                 "%Y-%m-%d %H:%M:%S"]


def parse_date(v) -> date | None:
    """Parse the date formats found in Indian clinic records (day-first)."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.date()
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s or s.lower() in {"nan", "nat", "none", "-"}:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def normalize_phone(v) -> str | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    digits = re.sub(r"\D", "", str(v).split(".")[0])
    if len(digits) < 10:
        return None
    return "+91" + digits[-10:]


def normalize_name(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip().title()  # "  KAVYA  prasad" -> "Kavya Prasad"


def name_key(v) -> str:
    return re.sub(r"[^a-z]", "", str(v or "").lower())


def to_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return None if (isinstance(v, float) and math.isnan(v)) else float(v)
    m = re.search(r"-?\d+(?:\.\d+)?", str(v))
    return float(m.group()) if m else None


def blank(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() in {"", "nan", "NaN", "None"}


def dedupe(df: pd.DataFrame, subset: list[str] | None = None) -> tuple[pd.DataFrame, int]:
    before = len(df)
    out = df.drop_duplicates(subset=subset).reset_index(drop=True)
    return out, before - len(out)


class Quarantine:
    """Collects rows that failed validation, with a reason - nothing is silently dropped."""

    def __init__(self):
        self.rows: list[dict] = []

    def add(self, source: str, table: str, reason: str, record: dict) -> None:
        self.rows.append({"source": source, "table": table, "reason": reason,
                          "record": {k: (str(v) if not isinstance(v, (int, float, str, type(None))) else v)
                                     for k, v in record.items()}})

    def summary(self) -> dict:
        out: dict[str, int] = {}
        for r in self.rows:
            out[f"{r['table']}: {r['reason']}"] = out.get(f"{r['table']}: {r['reason']}", 0) + 1
        return out
