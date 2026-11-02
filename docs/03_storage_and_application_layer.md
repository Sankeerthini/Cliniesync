# 3 · Data storage and the application layer

## Structured vs unstructured storage

| | Structured | Unstructured |
|---|---|---|
| What | patients, pregnancies, visits, observations, investigations, follow-ups, immunizations, plus app data (reviews, audit, outbox, reports, KPIs) | clinical notes, discharge summaries, lab-report text, register remarks |
| Store | **SQLite** (default, zero setup) or **PostgreSQL** (`DATABASE_URL=postgresql+psycopg://…`). Same SQLAlchemy models; portable SQL. | **ChromaDB** (embedded, persistent in `data/vectorstore/`), with automatic **TF-IDF fallback** |
| Access | SQLAlchemy ORM + **de-identified analytics views** (`v_visits`, `v_pregnancies`, `v_investigations`, `v_followups`, `v_immunizations`): the only relations text-to-SQL may touch | similarity search filtered by `patient_id`, each hit re-checked against the SQL `documents` table |
| Code | `database/models.py`, `database/views.py`, `database/session.py` | `ai/rag/vector_store.py`, `ai/rag/indexer.py` |

The documents table stores the full text, so the vector index is a **rebuildable cache**: `python -m etl.pipeline` regenerates it. For production on one server, **PostgreSQL + pgvector** can hold both stores in a single database.

## Application layer: FastAPI (`backend/app/`)

```
backend/app/
  main.py              app factory, CORS, startup (tables, views, demo users, NeMo), serves frontend/dist
  security.py          PBKDF2 passwords, HMAC-signed tokens, role dependencies (swap for OIDC/Keycloak in production)
  schemas/requests.py  Pydantic request models
  api/                 thin HTTP routers
    auth  system  query  patients  followups  analytics  reviews  reports  kpi  trust  data
  services/            business logic
    patient_service    registry, profile (role-scoped), timeline, measurements, documents
    followup_service   queue, ageing, multilingual drafts, approve → send, contact log, override
    report_service     doctor-only Share Report (en/hi/bn/kn), consent checks, delivery
    kpi_service        primary/secondary KPIs, baseline vs pilot, AI-quality and safety metrics
    audit              one-line audit helper used by every write
    notify/providers   sandbox / Twilio SMS / WhatsApp Cloud / SMTP, with allow-list
```

**Query orchestration** lives in `ai/orchestrator.py` (see docs/04): input guard → slots → access guard → SQL / RAG / hybrid → output guard → persist for review → audit.

### Business rules enforced in the backend (not just the UI)

* Every AI answer is stored as `pending_review`. Only `verified` or `edited` patient answers can be shared, and only by a doctor.
* Reminders follow **draft → human approve → send**. Sending without approval returns `409`.
* Consent is checked per channel. The doctor must also re-confirm consent before sharing.
* Status overrides require a reason, which is written to the audit trail.
* Human edits are screened for diagnostic or treatment language before they can be stored or shared.
* Administrators get aggregates only: `403` on patient endpoints, and access-guard blocks in Ask.
* Database writes commit **before** the HTTP response (`Depends(get_session, scope="function")`), so the UI's immediate re-fetch always sees them.

### API overview (interactive docs at `http://localhost:8000/docs`)

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/login`, `GET /api/auth/me` |
| Ask | `POST /api/query`, `GET /api/query/examples`, `POST /api/voice/transcribe` |
| Patients | `GET /api/patients`, `/{id}`, `/{id}/timeline`, `/{id}/measurements`, `/{id}/documents`, `/{id}/fhir` |
| Coordination | `GET /api/followups`, `/summary`, `POST /drafts`, `/{id}/contact`, `/{id}/override`, `GET /api/outbox`, `POST /api/outbox/{id}`, `/approve-and-send` |
| Analytics | `GET /api/analytics/dashboard`, `/{metric}` |
| Review & reports | `GET/POST /api/reviews/{id}`, `POST /api/reports/preview`, `/share` |
| KPIs & trust | `GET /api/kpi`, `POST /api/kpi/timing`, `GET /api/trust/audit`, `/stats`, `POST /playground`, `/feedback` |
| Data | `GET /api/data/quality`, `POST /api/data/register/preview`, `/etl/run` |
