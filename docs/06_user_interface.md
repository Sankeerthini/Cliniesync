# 6 · User interface and features

**Stack:** React 18 + TypeScript + Vite · Recharts (standard charts) · custom SVG (timeline) · lucide-react icons · plain CSS design system (no UI framework).
Code: `frontend/src/` → `ui/` (design system: tokens, 3D card, table, modal…), `charts/`, `app/` (shell, header, login), `features/<page>/`.

## Design principles

* **Not information-heavy.** Each page has one job, and detail sits behind toggles (Table, SQL, Safety checks, Sources).
* **Sign-in page: a scroll story, "from population to person, through time".** A rotating 3D globe of 600 dots (one per mother in the synthetic registry, coloured by stage; it follows the pointer) → scrolling zooms into one mother → her dot becomes a pregnancy clock that advances with scroll (week 0 → 40 → birth → PNC → 14-week vaccines). Milestones light up and show which feature helps then (Ask / Journey / Monitor / Communicate). A fixed "Sign in" button, chapter dots and a progress bar mean nobody has to scroll through it. Built with Canvas 2D + SVG (no WebGL dependency); `prefers-reduced-motion` stops the auto-motion. No map is used, because inaccurate depictions of India's borders are legally sensitive.
* **A calm home page.** One headline, an original flat illustration (an Indian mother in a kurta and saree pallu cradling her newborn; pure SVG, so no external image or licence), two floating glass cards, and four cards (Ask, Journey, Monitor, Communicate) that open the right tab for the role. Detail lives in the feature tabs. The research evidence is on KPIs & Pilot ("Why it matters") and the policy matrix is in the Trust Center.
* **3D, used purposefully.** Tilt-on-hover cards with a moving sheen, layered depth shadows, and flip cards that turn each problem into its solution. 3D is applied only while tilting, so text stays crisp. `prefers-reduced-motion` disables motion.
* **Colour and contrast.** Brand teal from the deck for chrome; text tokens pass WCAG AA. Charts use a **CVD-validated categorical palette** and an ordinal blue ramp for ordered stages, and never encode meaning by colour alone: shapes, icons and labels always accompany it. Every chart has a legend (≥ 2 series), selective direct labels, value-first tooltips and a **table view**.
* **Scientific validity of visuals.** Recorded values are shown **as documented**, with no reference ranges, red/green flags or "abnormal" colouring. Interpretation stays with the clinician. Metric definitions and caveats sit next to each chart.

## Header tabs per role

| Doctor | Care coordinator | Hospital administration |
|---|---|---|
| Home · Ask · **Patient Journey** · Follow-ups · Reviews · KPIs & Pilot · Trust Center | Home · Ask · **Follow-ups** · Patient Journey (operational view) · Reviews · KPIs · Trust Center | Home · Ask · **Analytics** · Reviews · KPIs & Pilot · **Data Hub** · Trust Center |

A compact system pill shows whether the LLM is running or the system is in offline-safe deterministic mode, NeMo status, the vector store, sandbox messaging and the synthetic-data reference date.

## Feature → visualisation map

| Feature (deck slide 6) | Where | Visualisation and why |
|---|---|---|
| **Patient history / longitudinal timeline** | Patient Journey → Timeline | Swimlane: lanes for antenatal care, investigations, delivery and postnatal, child immunization, follow-ups. **Trimester bands**, LMP/EDD/Delivery/Today markers, turnaround bars from order to result, status by **shape + colour** (filled = done, ring = no-show/awaiting, diamond = due/overdue, square = missed). Mother and baby share one axis. |
| Recorded values | Patient Journey → Recorded values (doctors) | **Small multiples**, one panel per measure with its own scale (Hb, weight, systolic/diastolic BP, fundal height, FHR, infant weight). No thresholds. |
| EHR queries | Ask | Cited answer, data table, citation drawer with verbatim source text |
| Clinical summaries | Ask / Journey → "Summarize journey" | Bulleted summary, every line cited `[S#]`; verify, edit or reject; **Share report** |
| Follow-up queues | Follow-ups | Stat tiles (due ≤ 7 d / overdue / missed / drafts) · ageing histogram by days past due · open items by type · queue ordered by days past due (operational, *not* clinical priority) |
| Patient tracking | Follow-ups + Journey | Coordination state (draft ready → reminder sent → reached/scheduled/unreachable), attempts, contact log, override with reason |
| Care-team communication | Follow-ups → Reminder outbox | Multilingual drafts in native script → edit → **approve** → send (sandbox/live) |
| Population analytics | Analytics | Headline tiles + governed metric cards |
| Visit volume | Analytics | **Stacked columns** per month by category (ANC / delivery / PNC / child) |
| Drop-off / visit frequency | Analytics | **ANC continuation funnel** (ordinal ramp) + drop-off line by EDD cohort; histogram of ANC contacts per pregnancy |
| Investigation utilization | Analytics | Stacked bars (resulted vs awaiting) by test + median turnaround bars |
| Operational trends | Analytics / KPIs | No-show trend, recall-completion trend with go-live marker, early registration, PNC and immunization coverage, facility comparison |

## Interaction features you asked for

1. **Text or voice queries (English).** Mic button uses the browser Web Speech API (en-IN); otherwise audio goes to `/api/voice/transcribe` (faster-whisper, offline). Voice queries are tagged in the answer and the audit log.
2. **Safety pipeline before retrieval.** A live pipeline strip (Text/voice → Guardrails + access → Router → SQL·RAG → Grounded answer → Human review), and an expandable **guard trace** on every answer listing each layer's verdict and reason.
3. **Human validation per role.** Every answer shows *Human review required*: **Verify / Edit / Reject**. The Reviews tab is the queue. Edits are re-screened. Verification time feeds the time-to-information KPI.
4. **Doctor-only Share Report.** After verification: language (English / हिन्दी / বাংলা / ಕನ್ನಡ), recipient (patient, caregiver or **someone else**), channels (SMS / WhatsApp / e-mail), mandatory consent confirmation, and a live preview of the printable report, WhatsApp text and SMS.
   * *Patient / caregiver*: the contact on record is used, and channels without consent on record are disabled.
   * *Someone else*: the doctor types an **e-mail address** and/or a mobile number (10-digit Indian numbers get +91). The doctor confirms the patient agreed to share with this person. The audit trail keeps only a masked contact.
   * **E-mail is delivered directly by the server** (SMTP). The formatted report is the mail body and is attached as an HTML file. It is free with a Gmail app password: run `.venv/bin/python scripts/setup_email.py` once, which writes `.env` and sends a test mail, then restart.
   * **WhatsApp is free**: a click-to-chat link (`wa.me`) opens WhatsApp on the doctor's device with the message and report link filled in, and the doctor presses send. **SMS** opens the device's SMS app. No paid gateway is needed. Twilio or the WhatsApp Cloud API are used only if their credentials are configured.
   * Every message carries an **expiring report link** (`/r/<token>`, 7 days, `REPORT_LINK_DAYS`) that opens the full report on a phone without a login. It works when the portal is reachable from outside, for example through the Cloudflare tunnel URL (or set `PUBLIC_BASE_URL`).
   * `DELIVERY_MODE=sandbox` keeps everything on the machine (`data/outbox/`). Contacts on record (fake in synthetic data) are messaged only if they are in `DELIVERY_ALLOWLIST`.
5. **Multilingual support.** Reviewed templates in four languages for reports and reminders; each patient's preferred language is the default; Noto fonts for Indic scripts.

## Running the UI

* Production: `cd frontend && npm install && npm run build`. FastAPI then serves `frontend/dist` at `http://localhost:8000`.
* Development: `npm run dev` (Vite on :5173 proxies `/api` to :8000).
* Demo logins: the role cards on the sign-in page (password `demo123`).
