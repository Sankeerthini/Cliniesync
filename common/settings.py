"""Central configuration for every ClinieSync layer (data, ETL, AI, guardrails, backend).

All values can be overridden with environment variables or a `.env` file in the
project root. Defaults are chosen so the whole stack runs offline on a laptop.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

try:  # optional: load .env if python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:  # pragma: no cover
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # ---- paths -------------------------------------------------------------
    data_dir: Path = DATA_DIR
    raw_dir: Path = DATA_DIR / "raw"                    # synthetic "clinic" sources land here
    processed_dir: Path = DATA_DIR / "processed"        # ETL reports, quarantine files
    vector_dir: Path = DATA_DIR / "vectorstore"         # ChromaDB persistence
    outbox_dir: Path = DATA_DIR / "outbox"              # sandbox copies of sent messages

    # ---- database ----------------------------------------------------------
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'cliniesync.db'}")
    )

    # ---- time anchor (freeze for reproducible demos) -------------------------
    reference_date_str: str = field(default_factory=lambda: os.getenv("REFERENCE_DATE", ""))

    # ---- LLM (any OpenAI-compatible server: Ollama, vLLM, llama.cpp, LM Studio) --
    llm_enabled: bool = field(default_factory=lambda: _bool("LLM_ENABLED", True))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "qwen2.5:7b-instruct"))
    llm_sql_model: str = field(default_factory=lambda: os.getenv("LLM_SQL_MODEL", ""))  # defaults to llm_model
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", "ollama"))
    llm_timeout_s: float = field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT_S", "60")))

    # ---- retrieval ----------------------------------------------------------
    vector_backend: str = field(default_factory=lambda: os.getenv("VECTOR_BACKEND", "auto"))  # auto|chroma|tfidf
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "default"))

    # ---- guardrails ---------------------------------------------------------
    use_nemo_guardrails: bool = field(default_factory=lambda: _bool("USE_NEMO_GUARDRAILS", True))

    # ---- translation --------------------------------------------------------
    use_indictrans: bool = field(default_factory=lambda: _bool("USE_INDICTRANS", False))
    # A general chat LLM mistranslated clinical terms in testing (e.g. "Pregnancy" -> "marriage" in Hindi), so it is
    # NOT used for patient-facing translation unless explicitly enabled for experiments.
    allow_llm_translation: bool = field(default_factory=lambda: _bool("ALLOW_LLM_TRANSLATION", False))

    # ---- delivery (SMS / e-mail / WhatsApp) ---------------------------------
    # auto: e-mail sent by SMTP when configured; SMS/WhatsApp only via a configured gateway | sandbox: nothing sent
    delivery_mode: str = field(default_factory=lambda: os.getenv("DELIVERY_MODE", "auto"))
    delivery_allowlist: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            x.strip() for x in os.getenv("DELIVERY_ALLOWLIST", "").split(",") if x.strip()
        )
    )
    twilio_account_sid: str = field(default_factory=lambda: os.getenv("TWILIO_ACCOUNT_SID", ""))
    twilio_auth_token: str = field(default_factory=lambda: os.getenv("TWILIO_AUTH_TOKEN", ""))
    twilio_from_number: str = field(default_factory=lambda: os.getenv("TWILIO_FROM_NUMBER", ""))
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    smtp_from: str = field(default_factory=lambda: os.getenv("SMTP_FROM", ""))      # default: SMTP_USER
    smtp_from_name: str = field(default_factory=lambda: os.getenv("SMTP_FROM_NAME", "ClinieSync Clinic"))
    whatsapp_token: str = field(default_factory=lambda: os.getenv("WHATSAPP_TOKEN", ""))
    whatsapp_phone_number_id: str = field(default_factory=lambda: os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""))
    # public address of this portal (e.g. the Cloudflare tunnel URL) for report links in messages;
    # empty = the address the doctor is using in the browser
    public_base_url: str = field(default_factory=lambda: os.getenv("PUBLIC_BASE_URL", "").rstrip("/"))
    report_link_days: int = field(default_factory=lambda: int(os.getenv("REPORT_LINK_DAYS", "7")))
    # number printed in patient reminders ("call ... to reschedule"); 104 = state health helpline in Karnataka
    clinic_helpline: str = field(default_factory=lambda: os.getenv("CLINIC_HELPLINE", "104"))

    # ---- security -----------------------------------------------------------
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", "change-me-in-production"))
    token_ttl_minutes: int = field(default_factory=lambda: int(os.getenv("TOKEN_TTL_MINUTES", "720")))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        )
    )

    # ---- operational definitions (used by KPIs and follow-up status) --------
    followup_grace_days: int = 7       # completed within due+7d counts as "on time"
    followup_match_window_days: int = 28  # a visit within due±28d closes a follow-up
    missed_after_days: int = 28        # overdue beyond this => "missed"
    pilot_go_live_offset_days: int = 90  # demo: last 90 days are treated as the "pilot" window

    @property
    def reference_date(self) -> date:
        """'Today' for the app. Freeze with REFERENCE_DATE=YYYY-MM-DD for reproducible demos."""
        if self.reference_date_str:
            return date.fromisoformat(self.reference_date_str)
        return date.today()

    @property
    def sql_model(self) -> str:
        return self.llm_sql_model or self.llm_model

    def ensure_dirs(self) -> None:
        for p in (self.data_dir, self.raw_dir, self.processed_dir, self.vector_dir, self.outbox_dir):
            p.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
