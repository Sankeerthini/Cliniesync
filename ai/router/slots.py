"""Slot extraction: patient references, time windows, facility, counts, categories."""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m} | \
         {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
            "ten": 10, "twelve": 12}


@dataclass
class Slots:
    patient_ids: list[str] = field(default_factory=list)
    patient_name_candidates: list[tuple[str, str]] = field(default_factory=list)   # (patient_id, name)
    n_last: int | None = None
    start: date | None = None
    end: date | None = None
    period_label: str | None = None
    facility_id: str | None = None
    category: str | None = None          # ANC / PNC / Delivery / Child
    followup_type: str | None = None
    status: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in self.__dict__.items()}


def _month_bounds(y: int, m: int) -> tuple[date, date]:
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def time_window(text: str, ref: date) -> tuple[date | None, date | None, str | None]:
    t = text.lower()
    if "today" in t:
        return ref, ref, "today"
    if "this week" in t:
        return ref, ref + timedelta(days=7), "next 7 days" if "due" in t else "this week"
    if "next week" in t:
        return ref + timedelta(days=7), ref + timedelta(days=14), "next week"
    if "last week" in t:
        return ref - timedelta(days=7), ref, "last 7 days"
    if "this month" in t:
        return ref.replace(day=1), ref, ref.strftime("%B %Y")
    if "last month" in t or "previous month" in t:
        y, m = (ref.year, ref.month - 1) if ref.month > 1 else (ref.year - 1, 12)
        s, e = _month_bounds(y, m)
        return s, e, s.strftime("%B %Y")
    if "this year" in t:
        return date(ref.year, 1, 1), ref, str(ref.year)
    if "last year" in t:
        return date(ref.year - 1, 1, 1), date(ref.year - 1, 12, 31), str(ref.year - 1)
    if "last quarter" in t:
        return ref - timedelta(days=91), ref, "last 3 months"
    m = re.search(r"last (\d+|" + "|".join(WORD_NUM) + r") (day|week|month|year)s?", t)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else WORD_NUM[m.group(1)]
        days = {"day": 1, "week": 7, "month": 30, "year": 365}[m.group(2)] * n
        return ref - timedelta(days=days), ref, f"last {n} {m.group(2)}{'s' if n > 1 else ''}"
    m = re.search(r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\b\s*(\d{4})?", t)
    if m and (m.group(1) != "may" or m.group(2)):   # "may" alone is usually the verb
        mi = MONTHS[m.group(1)]
        y = int(m.group(2)) if m.group(2) else (ref.year if mi <= ref.month else ref.year - 1)
        s, e = _month_bounds(y, mi)
        return s, min(e, ref), s.strftime("%B %Y")
    return None, None, None


def extract(text: str, ref: date, patients: list[tuple[str, str]] | None = None,
            facilities: list[tuple[str, str]] | None = None) -> Slots:
    s = Slots()
    s.patient_ids = re.findall(r"\bCS-\d{6}\b", text, re.I)
    s.patient_ids = [p.upper() for p in s.patient_ids]
    low = text.lower()
    if not s.patient_ids and patients:
        for pid, name in patients:
            if name and name.lower() in low:
                s.patient_name_candidates.append((pid, name))
    m = re.search(r"\b(?:last|latest|recent|past)\s+(\d+|" + "|".join(WORD_NUM) + r")\b"
                  r"(?!\s+(?:days?|weeks?|months?|years?)\b)", low)   # "last 3 months" is a time window, not N items
    if m:
        s.n_last = int(m.group(1)) if m.group(1).isdigit() else WORD_NUM[m.group(1)]
    elif re.search(r"\b(last|latest|most recent) (visit|report|test|note)\b", low):
        s.n_last = 1
    s.start, s.end, s.period_label = time_window(text, ref)
    for fid, fname in facilities or []:
        short = fname.lower().replace("district hospital", "dh")
        if fname.lower() in low or short in low or re.search(rf"\b{fname.split()[-1].lower()}\b", low):
            s.facility_id = fid
            break
    if re.search(r"\b(anc|antenatal|prenatal)\b", low):
        s.category = "ANC"
    elif re.search(r"\b(pnc|postnatal|postpartum)\b", low):
        s.category = "PNC"
    elif re.search(r"\b(deliver\w*|births?|lscs|caesarean|cesarean|c-section)\b", low):
        s.category = "Delivery"
    elif re.search(r"\b(immuni[sz]\w*|vaccin\w*|bab(y|ies)|child\w*|infants?)\b", low):
        s.category = "Child"
    if re.search(r"\b(report|lab|investigation|result)s?\b", low) and re.search(r"follow|review|pending|due", low):
        s.followup_type = "Investigation review"
    elif s.category == "ANC":
        s.followup_type = "ANC visit"
    elif s.category == "PNC":
        s.followup_type = "PNC visit"
    elif s.category == "Child":
        s.followup_type = "Immunization"
    for st in ("overdue", "missed", "upcoming", "completed"):
        if st in low:
            s.status.append(st)
    if re.search(r"\bdue (today|this week|next week|soon)\b|\bdue\b(?! date)", low) and "overdue" not in low:
        s.status.append("due")
    if "pending" in low and not s.status:
        s.status += ["due", "overdue"]
    return s
