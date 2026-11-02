# 4 · AI and intelligence layer: SQL analytics + RAG + open-source LLM

```
query ─► INPUT GUARD ─► slots (patient, dates, facility, N) ─► ACCESS GUARD ─► ROUTER
                                                                          ├─ population_analytics ─► semantic metric (SQL) │ LLM text-to-SQL (validated)
                                                                          ├─ care_coordination    ─► follow-up registry (SQL) + documented instructions
                                                                          ├─ patient_retrieval    ─► SQL facts │ RAG over notes
                                                                          └─ patient_summary      ─► evidence pack [S1..Sn] ─► LLM (grounded) │ template
                                                            ─► OUTPUT GUARD ─► stored "pending_review" ─► human verify / edit / reject
```
Code: `ai/orchestrator.py`, `ai/router/`, `ai/sql/`, `ai/rag/`, `ai/llm/`, `ai/translate/`, `ai/voice/`.

## Choosing the LLM (open-source)

| Role | Default | Why | Alternatives |
|---|---|---|---|
| Summaries, Q&A over notes, NeMo self-check rails, translation fallback | **Qwen2.5-7B-Instruct** (`qwen2.5:7b-instruct`, Apache-2.0) via **Ollama** | Strong instruction-following and JSON, good multilingual coverage, ~4.7 GB at Q4, so it runs on an 8–12 GB GPU (your RTX 5070 runs it comfortably) | Llama-3.1-8B-Instruct, Gemma-3-12B, Qwen3-8B (disable "thinking") |
| Text-to-SQL fallback | same model, or **Qwen2.5-Coder-7B** (`LLM_SQL_MODEL`) | Specialised for SQL | SQLCoder |
| Embeddings | **all-MiniLM-L6-v2** (ONNX, built into ChromaDB; no torch, no GPU) | Fast and small; notes are short | `BAAI/bge-small-en-v1.5` (`EMBEDDING_MODEL=`) |
| Translation of free text | **AI4Bharat IndicTrans2** (en→hi/bn/kn, open-source) | Best open model for Indic languages | the chat LLM (labelled machine translation) |
| Speech-to-text | Browser Web Speech API (en-IN); **faster-whisper** offline | Audio never leaves the clinic in Whisper mode | – |

Avoid medical "diagnostic" LLMs here: ClinieSync needs a model that **restates** documents, not one tuned to give clinical opinions.

`ai/llm/client.py` talks to any **OpenAI-compatible** endpoint (Ollama, vLLM, llama.cpp, LM Studio). Switching models is a config change:
```
LLM_BASE_URL=http://localhost:11434/v1   LLM_MODEL=qwen2.5:7b-instruct
```
**Every AI feature has a deterministic fallback.** If the model is down, answers are built from records by templates, so a demo cannot fail on stage, and the UI says so ("Offline-safe").

## SQL analytics (population analytics)

1. **Semantic layer** (`ai/sql/semantic_layer.py`): 14 governed, reviewed metrics with explicit numerators, denominators and cohorts:
   visit count/volume, ANC continuation funnel and drop-off, no-show trend, follow-up (recall) completion, investigation utilization and turnaround, visit frequency, early registration, PNC coverage, immunization coverage, deliveries, pregnancy status, follow-up backlog, facility comparison.
   *Scientific choices:* drop-off uses **EDD cohorts** (only pregnancies whose antenatal window is complete, so recent registrants aren't counted as drop-outs). No-show excludes register-only facilities, which don't record no-shows. Recall completion excludes items still inside the grace period. Each result carries its SQL, definition and caveats, all shown in the UI.
2. **LLM text-to-SQL fallback** (`ai/sql/text_to_sql.py`), used only when no metric matches. The model sees the documented **de-identified views**. Its output passes `ai/sql/validator.py` (sqlglot: one SELECT, whitelisted views, no dangerous functions, LIMIT ≤ 500, aggregate-only for admins) and runs on a **read-only** connection.

## RAG (patient retrieval and summarisation)

* **Evidence pack** (`ai/rag/retriever.py`): structured facts (profile, pregnancy, visits with recorded values, investigations, follow-ups, child, immunizations) plus the top-k note chunks from the vector store (filtered by patient, then ownership re-checked in SQL). Every item gets an ID `[S1]…[Sn]`, and the user's **role scopes** decide what goes in. Coordinators get no clinical values or notes.
* **Summaries** (`ai/rag/summarizer.py`):
  * *Deterministic*: built directly from records; cites every line; never interprets.
  * *LLM*: a strict prompt (restate only, cite `[S#]` on every bullet, no normal/abnormal words, no advice), then the output guard. If any check fails, ClinieSync **falls back to the deterministic summary** rather than showing unchecked text.
* **Vector DB**: ChromaDB (persistent, embedded). For production, pgvector inside PostgreSQL. A TF-IDF fallback is built in.

## Multilingual layer

Patient-facing messages and reports use **reviewed templates** in English, Hindi, Bengali and Kannada (`ai/translate/templates.py`), filled with names, dates and facility. The doctor's free-text note is translated **only by a dedicated MT model** (IndicTrans2, `USE_INDICTRANS=true`). The translation is labelled as machine translation, with the verified English beneath it.

> **Tested finding:** with `qwen2.5:7b-instruct` as translator, the Hindi note rendered "Pregnancy" as *विवाह* ("marriage") and "Delivery" as *निष्कासन* ("expulsion"). General chat LLMs are therefore **disabled for patient-facing translation** (`ALLOW_LLM_TRANSLATION=false`). Without IndicTrans2, the note stays in verified English with a label in the patient's language.
