# 7 · Scope, KPIs and pilot plan (mapped to "Important Notes for Healthathon 2026")

| Judging note | How ClinieSync answers it | Where to show it |
|---|---|---|
| 1. Assistive, not diagnostic; human override; audit trail; fake data only | 6 input layers + access + 5 output checks; NeMo Guardrails; verify/edit/reject; override with reason; every action audited; synthetic data only | Trust Center (playground + audit), Ask "Blocked by design" |
| 2. High-frequency pain, easy, low-cost channels, light integration | Daily follow-up queue; SMS/WhatsApp reminders; reads existing CSV/Excel/PDF exports; no EHR rewrite | Follow-ups, Data Hub |
| 3. **Measurable KPI** with baseline and change | **Primary: follow-up (recall) completion rate**, baseline vs pilot window, monthly trend with go-live marker; secondary: no-show, handoff lag, time-to-information | KPIs & Pilot |
| 4. Minimal integration; meet the clinic where it is | Excel register melted, PDFs parsed, notes mined for documented instructions, cross-facility MPI | Data Hub |
| 5. Multilingual, caregiver-friendly | en/hi/bn/kn templates; preferred language by default; caregiver as a first-class recipient | Follow-ups outbox, Share Report |
| 6. Pilot evidence in 60–90 days | 4-phase plan, KPI definitions frozen up front, same SQL for baseline and pilot | KPIs & Pilot |

## The KPI, precisely

**Follow-up (recall) completion rate** = documented follow-ups completed **≤ 7 days** after their due date ÷ follow-ups due in the window (cancelled excluded; items inside the grace period excluded).
* *Baseline*: the 90 days before go-live, computed from historical records (no new data collection needed).
* *Pilot*: go-live → today − 7 days. Same query. Target **+10 percentage points** within 90 days.
* Secondary: ANC no-show rate (↓), handoff lag = median days from due date to first coordinator contact (↓), time-to-information (manual chart review vs ClinieSync including verification, measured with the built-in time-motion stopwatch) (↓ ≥ 50%).
* Safety KPIs: zero clinical-advice outputs in the audit; wrong-block rate; edit and reject rates of AI answers.

On synthetic data **no effect is simulated**, so baseline ≈ pilot, and the page says so. Do not present synthetic numbers as results.

## What makes ClinieSync distinctive (talking points)

1. **Safety you can see.** Every answer carries its guard trace, sources and review state. Blocked requests explain why and offer safe alternatives.
2. **Documented follow-ups, not AI-decided ones.** Instructions are extracted from notes with the verbatim sentence and source, and statuses come from what actually happened.
3. **Works with what clinics already have.** CSV + Excel + PDF + notes become one linked record (600 women recovered from 669 source records across 3 facilities).
4. **Offline-safe.** Every AI step has a deterministic fallback, so it runs on a laptop without internet or GPU, and gets better when an open-source LLM is present.
5. **Scientifically careful analytics.** EDD-cohort drop-off, explicit denominators, caveats, SQL shown, de-identified views for administrators.
6. **Consent-gated, multilingual, caregiver-aware communication** through low-cost channels, human-approved.

## Scope boundaries (state these up front)

* No diagnosis, interpretation, treatment, triage or risk prediction, including operational "who will miss" prediction.
* No sending without a human click. Live messaging only to allow-listed numbers until the pilot is approved.
* Production use requires ethics approval, a security/privacy review (DPDP Act 2023), the hospital's identity provider, and native-speaker review of templates.

## Possible extensions (after phase 1)

* OCR for scanned registers/MCP cards (Tesseract / docTR), with human confirmation of extracted fields.
* Package as an **OHC CARE plugin** (see `integrations/care_ohc/README.md`).
* WhatsApp two-way "reply 1 to confirm" scheduling (still no clinical content).
* ABHA/ABDM linkage for patient identity, where available.
