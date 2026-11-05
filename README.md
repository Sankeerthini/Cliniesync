# ClinieSync: Maternal & Child Healthcare Operations Copilot

**Team ClinieSync · TANUH, IISc Bangalore · Health-a-thon 2026**

*Assistive, not diagnostic.* ClinieSync makes the EHR easier to **search, summarise and coordinate**: ask instead of search, summarise instead of reconstruct, coordinate instead of chase, prompt instead of depend on memory. AI only retrieves, organises, summarises and coordinates; a human verifies everything. **Synthetic data only.**

## Quick start

```bash
cd cliniesync
scripts/setup.sh        # venv + synthetic data + ETL + tests + UI build (needs Python 3.12, Node 18+)
scripts/run.sh          # http://localhost:8000  (API docs at /docs)
```
**Demo with a public link:** a Google Cloud server set up by `deploy/gcp/setup_server.sh`, or `scripts/start_demo.sh --fixed` on your own machine (Tailscale Funnel). Both are in [RUNBOOK.md](RUNBOOK.md).
Sign in with one of the demo role cards (password `demo123`): **Dr. Ananya Rao** (doctor), **Rekha S.** (care coordinator), **Hospital Administrator**.

Optional open-source LLM (summaries, text-to-SQL fallback, NeMo LLM self-check rails, translation):
```bash
scripts/setup_llm.sh    # Ollama + qwen2.5:7b-instruct;  ClinieSync auto-detects it
```
Without an LLM, everything still works in **offline-safe deterministic mode**.

## Architecture (idea-deck slide 5, implemented)

```
1 Data sources      data_generator/   EHR CSV exports · Excel ANC register · PDF lab reports · clinical notes (synthetic)
2 Data processing   etl/              extract → clean → normalise (vocab, LOINC, units) → link (MPI) → derive follow-ups
3 Data storage      database/         SQL (SQLite/PostgreSQL) + de-identified views   |  ai/rag/  ChromaDB vector store
4 User query        frontend/         text or voice (Web Speech en-IN / faster-whisper)
5 Safety & access   guardrails/       lexicon + semantic screen + NVIDIA NeMo Guardrails + RBAC + output guard
6 Query router      ai/router/        intent rules + exemplar classifier + slots
  SQL / RAG         ai/sql/, ai/rag/  governed metrics + validated text-to-SQL  |  cited evidence packs + summaries
7 Grounded answer   ai/orchestrator   output checks → stored "pending review" → verify / edit / reject
8 Multilingual      ai/translate/     en · hi · bn · kn templates (+ IndicTrans2/LLM for free text)
9 Application       backend/ + frontend/   FastAPI APIs & business logic · React clinical console
   Integration      integrations/care_ohc/  FHIR R4 export for OHC CARE / FHIR servers
```

## Folder map

| Folder | Contents |
|---|---|
| `common/` | settings (env-driven) |
| `data_generator/` | synthetic cohort simulator, note templates, writers for messy sources |
| `etl/` | extract, clean, vocab, transform/link, follow-ups, load, pipeline |
| `database/` | SQLAlchemy models (FHIR-shaped), analytics views, sessions |
| `ai/` | `llm/` client · `router/` intents and slots · `sql/` semantic layer, text-to-SQL, validator · `rag/` vector store, retriever, summariser · `translate/` · `voice/` · `orchestrator.py` |
| `guardrails/` | policy, lexicon, input/access/output guards, PII, NeMo adapter + `nemo_config/` |
| `backend/` | FastAPI `app/` (api, services, schemas, security) + `tests/` |
| `frontend/` | React app: `src/ui` design system, `src/charts`, `src/app` shell, `src/features/*` pages |
| `integrations/care_ohc/` | FHIR exporter + CARE plugin notes |
| `docs/` | step-by-step guides 01–07 |
| `scripts/` | setup, run, LLM setup |

## Guides

1. [Data sources](docs/01_data_sources.md): why synthetic, what is simulated, how reports are generated
2. [Data processing](docs/02_data_processing.md): ETL, cleaning, normalisation, MPI, unified layer
3. [Storage & application layer](docs/03_storage_and_application_layer.md): SQL + vector, FastAPI, business rules, API
4. [AI layer](docs/04_ai_layer.md): LLM choice, SQL analytics, RAG, vector DB, multilingual
5. [Safety & guardrails](docs/05_safety_guardrails.md): NeMo Guardrails and the layered policy
6. [User interface](docs/06_user_interface.md): design, feature → visualisation map, voice, review, Share Report
7. [Scope, KPI & pilot](docs/07_scope_kpi_and_pilot.md): judging notes mapped, KPI definition, 60–90 day plan

## Tests

`pytest -q` runs 109 tests: 99 safety regression cases for the guardrails (input and output) and 10 end-to-end API workflow tests (roles, verify-before-share, consent, approval-gated sending, overrides, analytics, KPIs, parameter retrieval per role, read-only SQL isolation).

## Suggested 5-minute demo

1. **Doctor** → Patient Journey: open a timeline (trimester bands, no-shows, pending results) → *Summarize journey* → open a citation → **Verify** → **Share report** in ಕನ್ನಡ.
2. Ask *"Does she have preeclampsia?"* → blocked, with the guard trace and safe alternatives.
3. **Coordinator** → Follow-ups: select overdue items → draft reminders (each patient's language) → approve & send (sandbox) → log a contact.
4. **Administrator** → Analytics (visit volume, ANC drop-off, investigations) → KPIs & Pilot → Data Hub (669 records → 600 patients).
