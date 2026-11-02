"""Unified data layer: canonical ClinieSync schema (SQLAlchemy 2.0 ORM).

Two groups of tables:

* Clinical-operational tables (filled by the ETL pipeline from clinic sources):
  facilities, providers, patients, patient_identifiers, pregnancies, children,
  visits, observations, investigations, immunizations, followups, documents.
  The shape follows FHIR R4 resources (Patient, EpisodeOfCare, Encounter,
  Observation, ServiceRequest/DiagnosticReport, Immunization, Appointment,
  DocumentReference) so data can be exchanged with OHC CARE or any FHIR server.

* Application tables (written by the backend): users, ai_responses (human review),
  outbox_messages, contact_events, reports, feedback, baseline_timings,
  audit_log, etl_runs.

Columns are portable between SQLite (default) and PostgreSQL.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------- reference
class Facility(Base):
    __tablename__ = "facilities"
    facility_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    facility_type: Mapped[str] = mapped_column(String(40))          # PHC / CHC / District Hospital
    district: Mapped[str] = mapped_column(String(60))
    source_system: Mapped[str] = mapped_column(String(40))          # ehr_export / excel_register


class Provider(Base):
    __tablename__ = "providers"
    provider_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(40))                   # OBG, Paediatrician, ANM, Coordinator
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.facility_id"))


# --------------------------------------------------------------------------- people
class Patient(Base):
    __tablename__ = "patients"
    patient_id: Mapped[str] = mapped_column(String(16), primary_key=True)   # CS-000123
    rch_id: Mapped[str | None] = mapped_column(String(20), index=True)      # synthetic RCH-style ID
    full_name: Mapped[str] = mapped_column(String(120), index=True)
    age_years: Mapped[int | None] = mapped_column(Integer)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(120))
    preferred_language: Mapped[str] = mapped_column(String(5), default="en")  # en/hi/bn/kn
    village: Mapped[str | None] = mapped_column(String(80))
    district: Mapped[str | None] = mapped_column(String(60))
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.facility_id"), index=True)
    caregiver_name: Mapped[str | None] = mapped_column(String(120))
    caregiver_relation: Mapped[str | None] = mapped_column(String(40))
    caregiver_phone: Mapped[str | None] = mapped_column(String(20))
    consent_sms: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_whatsapp: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_email: Mapped[bool] = mapped_column(Boolean, default=False)
    registered_on: Mapped[date | None] = mapped_column(Date)
    source_system: Mapped[str] = mapped_column(String(40))


class PatientIdentifier(Base):
    """Master-patient-index rows: which source record maps to which canonical patient."""

    __tablename__ = "patient_identifiers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.patient_id"), index=True)
    source_system: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[str] = mapped_column(String(60))


class Pregnancy(Base):
    __tablename__ = "pregnancies"
    pregnancy_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.patient_id"), index=True)
    lmp: Mapped[date | None] = mapped_column(Date)
    edd: Mapped[date | None] = mapped_column(Date)
    gravida: Mapped[int | None] = mapped_column(Integer)
    parity: Mapped[int | None] = mapped_column(Integer)
    registration_date: Mapped[date | None] = mapped_column(Date)
    registration_ga_weeks: Mapped[float | None] = mapped_column(Float)
    registration_month: Mapped[str | None] = mapped_column(String(7))     # YYYY-MM (portable grouping)
    status: Mapped[str] = mapped_column(String(20))                       # antenatal / delivered / postnatal_closed / no_recent_contact
    delivery_date: Mapped[date | None] = mapped_column(Date)
    delivery_mode: Mapped[str | None] = mapped_column(String(40))         # as documented
    delivery_facility_id: Mapped[str | None] = mapped_column(String(16))
    anc_visits_completed: Mapped[int] = mapped_column(Integer, default=0)


class Child(Base):
    __tablename__ = "children"
    child_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    mother_patient_id: Mapped[str] = mapped_column(ForeignKey("patients.patient_id"), index=True)
    pregnancy_id: Mapped[str | None] = mapped_column(ForeignKey("pregnancies.pregnancy_id"))
    full_name: Mapped[str] = mapped_column(String(120))
    sex: Mapped[str | None] = mapped_column(String(10))
    dob: Mapped[date | None] = mapped_column(Date)
    birth_weight_g: Mapped[int | None] = mapped_column(Integer)
    facility_id: Mapped[str | None] = mapped_column(String(16))


# --------------------------------------------------------------------------- encounters
class Visit(Base):
    __tablename__ = "visits"
    visit_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.patient_id"), index=True)
    child_id: Mapped[str | None] = mapped_column(String(20), index=True)
    pregnancy_id: Mapped[str | None] = mapped_column(String(20), index=True)
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.facility_id"), index=True)
    provider_id: Mapped[str | None] = mapped_column(String(16))
    visit_date: Mapped[date] = mapped_column(Date, index=True)
    visit_month: Mapped[str] = mapped_column(String(7), index=True)       # YYYY-MM
    visit_category: Mapped[str] = mapped_column(String(20))               # ANC / Delivery / PNC / Child
    visit_type: Mapped[str] = mapped_column(String(30))                   # ANC1, ANC2, PNC-D7, Immunization-6w ...
    sequence: Mapped[int | None] = mapped_column(Integer)
    ga_weeks: Mapped[float | None] = mapped_column(Float)                 # gestational age at visit (arithmetic from LMP)
    status: Mapped[str] = mapped_column(String(20))                       # completed / no_show
    source_system: Mapped[str] = mapped_column(String(40))


class Observation(Base):
    __tablename__ = "observations"
    obs_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visit_id: Mapped[str] = mapped_column(ForeignKey("visits.visit_id"), index=True)
    patient_id: Mapped[str] = mapped_column(String(16), index=True)
    child_id: Mapped[str | None] = mapped_column(String(20))
    code: Mapped[str] = mapped_column(String(40))                         # canonical code e.g. hemoglobin
    display: Mapped[str] = mapped_column(String(80))
    loinc: Mapped[str | None] = mapped_column(String(12))
    value_num: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(String(80))
    unit: Mapped[str | None] = mapped_column(String(20))
    observed_on: Mapped[date] = mapped_column(Date)


class Investigation(Base):
    __tablename__ = "investigations"
    investigation_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    visit_id: Mapped[str | None] = mapped_column(String(24), index=True)
    patient_id: Mapped[str] = mapped_column(String(16), index=True)
    test_code: Mapped[str] = mapped_column(String(40))
    test_name: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(20))                     # lab / imaging
    ordered_on: Mapped[date] = mapped_column(Date)
    ordered_month: Mapped[str] = mapped_column(String(7))
    resulted_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))                       # resulted / pending
    turnaround_days: Mapped[int | None] = mapped_column(Integer)
    result_summary: Mapped[str | None] = mapped_column(String(200))       # verbatim documented result
    report_doc_id: Mapped[str | None] = mapped_column(String(32))
    source_system: Mapped[str] = mapped_column(String(40))


class Immunization(Base):
    __tablename__ = "immunizations"
    imm_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    child_id: Mapped[str] = mapped_column(ForeignKey("children.child_id"), index=True)
    vaccine: Mapped[str] = mapped_column(String(40))
    schedule_label: Mapped[str] = mapped_column(String(20))               # Birth / 6 weeks / ...
    due_on: Mapped[date] = mapped_column(Date)
    given_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))                       # given / due / overdue
    visit_id: Mapped[str | None] = mapped_column(String(24))


class FollowUp(Base):
    """A documented follow-up (next visit, investigation review, immunization due...).

    `status` is derived from the records (upcoming/due/overdue/completed/missed);
    `workflow_state` is the human coordination state managed in the app.
    """

    __tablename__ = "followups"
    followup_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.patient_id"), index=True)
    child_id: Mapped[str | None] = mapped_column(String(20))
    pregnancy_id: Mapped[str | None] = mapped_column(String(20))
    facility_id: Mapped[str] = mapped_column(String(16), index=True)
    source_visit_id: Mapped[str | None] = mapped_column(String(24))
    source_doc_id: Mapped[str | None] = mapped_column(String(32))
    followup_type: Mapped[str] = mapped_column(String(30))                # ANC visit / PNC visit / Immunization / Investigation review
    expected_visit_type: Mapped[str | None] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(String(240))                 # documented instruction (verbatim when available)
    due_on: Mapped[date] = mapped_column(Date, index=True)
    due_month: Mapped[str] = mapped_column(String(7))
    status: Mapped[str] = mapped_column(String(20), index=True)
    completed_visit_id: Mapped[str | None] = mapped_column(String(24))
    completed_on: Mapped[date | None] = mapped_column(Date)
    origin: Mapped[str] = mapped_column(String(30))                       # appointment / register / note_extraction / schedule
    workflow_state: Mapped[str] = mapped_column(String(30), default="none")
    contact_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_contact_on: Mapped[date | None] = mapped_column(Date)
    first_contact_on: Mapped[date | None] = mapped_column(Date)
    assigned_to: Mapped[str | None] = mapped_column(String(40))
    override_reason: Mapped[str | None] = mapped_column(String(240))


class Document(Base):
    __tablename__ = "documents"
    doc_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    patient_id: Mapped[str] = mapped_column(String(16), index=True)
    child_id: Mapped[str | None] = mapped_column(String(20))
    visit_id: Mapped[str | None] = mapped_column(String(24))
    doc_type: Mapped[str] = mapped_column(String(30))                     # clinical_note / lab_report / discharge_summary / register_remark
    title: Mapped[str] = mapped_column(String(160))
    doc_date: Mapped[date] = mapped_column(Date)
    author: Mapped[str | None] = mapped_column(String(120))
    text: Mapped[str] = mapped_column(Text)
    source_system: Mapped[str] = mapped_column(String(40))
    source_file: Mapped[str | None] = mapped_column(String(240))


# --------------------------------------------------------------------------- application
class User(Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(40), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))                         # doctor / coordinator / admin
    password_hash: Mapped[str] = mapped_column(String(200))
    facility_id: Mapped[str | None] = mapped_column(String(16))


class AIResponse(Base):
    """Every AI answer is stored and must be verified by a human before it is reused or shared."""

    __tablename__ = "ai_responses"
    response_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    username: Mapped[str] = mapped_column(String(40))
    role: Mapped[str] = mapped_column(String(20))
    query_text: Mapped[str] = mapped_column(Text)
    input_mode: Mapped[str] = mapped_column(String(10), default="text")   # text / voice
    intent: Mapped[str] = mapped_column(String(40))
    route: Mapped[str] = mapped_column(String(20))                        # sql / rag / sql+rag / blocked
    patient_id: Mapped[str | None] = mapped_column(String(16))
    answer_text: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON)                           # table/chart/citations/guard trace
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), index=True)           # pending_review / verified / edited / rejected / blocked
    reviewed_by: Mapped[str | None] = mapped_column(String(40))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_seconds: Mapped[int | None] = mapped_column(Integer)
    final_text: Mapped[str | None] = mapped_column(Text)
    review_note: Mapped[str | None] = mapped_column(String(400))


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"
    message_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    kind: Mapped[str] = mapped_column(String(20))                         # followup_reminder / report
    followup_id: Mapped[str | None] = mapped_column(String(32))
    report_id: Mapped[str | None] = mapped_column(String(32))
    patient_id: Mapped[str] = mapped_column(String(16), index=True)
    recipient_type: Mapped[str] = mapped_column(String(20))               # patient / caregiver
    recipient: Mapped[str] = mapped_column(String(120))
    channel: Mapped[str] = mapped_column(String(12))                      # sms / whatsapp / email
    language: Mapped[str] = mapped_column(String(5))
    subject: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))                       # draft / approved / sent / failed / rejected
    created_by: Mapped[str] = mapped_column(String(40))
    approved_by: Mapped[str | None] = mapped_column(String(40))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    delivery_detail: Mapped[str | None] = mapped_column(String(400))


class ContactEvent(Base):
    __tablename__ = "contact_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    followup_id: Mapped[str] = mapped_column(String(32), index=True)
    at: Mapped[datetime] = mapped_column(DateTime)
    by_user: Mapped[str] = mapped_column(String(40))
    channel: Mapped[str] = mapped_column(String(20))                      # phone / sms / whatsapp / home_visit
    outcome: Mapped[str] = mapped_column(String(20))                      # reached / unreachable / scheduled / declined
    note: Mapped[str | None] = mapped_column(String(400))


class Report(Base):
    __tablename__ = "reports"
    report_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    response_id: Mapped[str] = mapped_column(String(32))
    patient_id: Mapped[str] = mapped_column(String(16), index=True)
    language: Mapped[str] = mapped_column(String(5))
    html: Mapped[str] = mapped_column(Text)
    short_text: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(40))
    channels: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20))                       # shared / failed


class ReportLink(Base):
    """Expiring, unguessable link to a shared report, so a recipient can open it on their phone without logging in."""

    __tablename__ = "report_links"
    token: Mapped[str] = mapped_column(String(48), primary_key=True)
    report_id: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String(40))
    views: Mapped[int] = mapped_column(Integer, default=0)


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime)
    username: Mapped[str] = mapped_column(String(40))
    response_id: Mapped[str | None] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(20))                         # helpful / unhelpful / wrong_block / unsafe
    note: Mapped[str | None] = mapped_column(String(400))


class BaselineTiming(Base):
    """Time-motion log for the 'time-to-information' KPI (manual chart review vs ClinieSync)."""

    __tablename__ = "baseline_timings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime)
    username: Mapped[str] = mapped_column(String(40))
    task: Mapped[str] = mapped_column(String(60))
    method: Mapped[str] = mapped_column(String(20))                       # manual / cliniesync
    seconds: Mapped[float] = mapped_column(Float)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime, index=True)
    username: Mapped[str] = mapped_column(String(40))
    role: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(40), index=True)
    target: Mapped[str | None] = mapped_column(String(60))
    decision: Mapped[str | None] = mapped_column(String(20))              # allowed / blocked / approved / ...
    detail: Mapped[dict | None] = mapped_column(JSON)


class EtlRun(Base):
    __tablename__ = "etl_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime)
    report: Mapped[dict] = mapped_column(JSON)
