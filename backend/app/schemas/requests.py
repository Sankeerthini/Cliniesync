"""Request bodies (Pydantic v2)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str
    password: str


class QueryIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    patient_id: str | None = None
    input_mode: Literal["text", "voice"] = "text"


class ReviewIn(BaseModel):
    action: Literal["verify", "edit", "reject"]
    edited_text: str | None = None
    note: str | None = None


class DraftIn(BaseModel):
    followup_ids: list[str]
    recipient: Literal["patient", "caregiver"] = "patient"
    channel: Literal["sms", "whatsapp", "email"] = "sms"
    language: Literal["auto", "en", "hi", "bn", "kn"] = "auto"


class MessageActionIn(BaseModel):
    action: Literal["approve", "reject", "send", "edit"]
    body: str | None = None


class BatchIn(BaseModel):
    message_ids: list[str]


class ContactIn(BaseModel):
    channel: Literal["phone", "sms", "whatsapp", "home_visit", "in_person"] = "phone"
    outcome: Literal["reached", "unreachable", "scheduled", "declined"]
    note: str = ""


class OverrideIn(BaseModel):
    status: Literal["completed", "cancelled", "missed", "overdue", "due"]
    reason: str = Field(min_length=3, max_length=240)


class ReportIn(BaseModel):
    response_id: str
    language: Literal["en", "hi", "bn", "kn"] = "en"
    recipient: Literal["patient", "caregiver", "other"] = "patient"


class ShareIn(ReportIn):
    channels: list[Literal["sms", "whatsapp", "email"]]
    consent_confirmed: bool = False
    # recipient == "other": the contact the doctor typed in
    to_name: str | None = Field(default=None, max_length=80)
    to_phone: str | None = Field(default=None, max_length=24)
    to_email: str | None = Field(default=None, max_length=120)
    base_url: str | None = Field(default=None, max_length=200)    # portal address seen by the doctor's browser


class TimingIn(BaseModel):
    task: str = Field(min_length=2, max_length=60)
    method: Literal["manual", "cliniesync"]
    seconds: float = Field(gt=0, lt=7200)


class FeedbackIn(BaseModel):
    response_id: str | None = None
    kind: Literal["helpful", "unhelpful", "wrong_block", "unsafe"]
    note: str | None = None


class PlaygroundIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
