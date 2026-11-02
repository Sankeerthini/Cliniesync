# 1 · Data sources: what to use, and how

## Recommendation: synthetic data, built in, generated locally

**Use the bundled synthetic generator for development and demos.** Keep the datasets in the idea deck only as *optional design references*, and use them locally, never in the demo. Three reasons:

| Concern | Detail |
|---|---|
| **Hackathon rule** | "Teams build on fake or fully anonymised data only – no patient data on the platform, with mentors, or in demos." |
| **Licences** | MIMIC-IV and eICU-CRD (PhysioNet) require credentialing (CITI training) and a data-use agreement. The DUA restricts sharing data with third parties, including hosted LLM APIs. EHRSHOT (Stanford) also needs a research DUA. Check the licence of the Obstetrics Notes Collection before use. |
| **Fit** | MIMIC-IV and eICU are US ICU/ED data. ClinieSync's workflow is Indian **outpatient ANC → delivery → PNC → immunization**, recorded in MCP cards, RCH registers and PHC/CHC exports. Those datasets contain very few ANC visit schedules, Indian registers or multilingual patients. |

The generator (`data_generator/`) produces a realistic Indian MCH cohort: 600 mothers, 3 facilities, about 18 months of activity. It writes the data in the **messy formats clinics actually hold**, so the ETL is exercised for real:

| Facility | Source system | Files written to `data/raw/` |
|---|---|---|
| F1 PHC Hebbal | EHR/HMIS export | `ehr_F1/*.csv` + `notes.jsonl` (ISO dates, BP as "110/70") |
| F2 District Hospital Tumakuru | EHR/HMIS export | `ehr_F2/*.csv` + `notes.jsonl` (mixed date formats, split BP, also receives referrals for delivery) |
| F3 CHC Anekal | **No EHR** | `register_F3/ANC_Register_CHC_Anekal.xlsx` (wide register, ANC1–ANC5 columns) + `lab_reports/*.pdf` |

```bash
python -m data_generator.run --mothers 600 --seed 42 --reference-date 2026-10-19
```

### What is simulated (and why it matters to the KPIs)

| Domain | Parameters | Basis |
|---|---|---|
| Registration | LMP, EDD (LMP + 280 d), gravida/parity, registration GA (60% in the first trimester) | GoI ANC guidance: register in T1 |
| ANC contacts | ANC1 at registration; target windows ~20, 26, 32, 36 (+38) weeks; per-woman attendance probability; no-shows; late re-attendance; drop-out | 4+ ANC contacts (GoI / PMSMA) |
| Recorded values | weight, BP, Hb (from CBC), fundal height and FHR from 20 w, urine albumin | MCP-card fields |
| Investigations | CBC, blood group & Rh, HIV, VDRL, HBsAg, urine; dating USG (≤13 w), anomaly scan (18–22 w), OGTT 75 g (24–28 w), TSH, growth scan; turnaround times; ~8–15% never resulted | GoI ANC schedule |
| Delivery | GA at delivery, mode (NVD / LSCS / assisted), birth weight, ~35% referred to the district hospital (cross-facility linkage) | – |
| PNC | day 3, day 7, day 42 contacts | GoI PNC schedule |
| Child | UIP sessions: birth, 6 w, 10 w, 14 w, 9 m, with drop-out | Universal Immunization Programme |
| Coordination | appointments booked at each visit; free-text notes with instructions ("Review after 2 weeks with investigation reports") | What follow-ups look like in practice |
| People | fake names, fake RCH-style IDs, `+9190000xxxxx` numbers, `example.com` e-mails; languages kn/hi/bn/en by area; caregiver and consent flags | – |
| Noise | 4 date formats, `g%` vs `g/dL`, grams vs kg, combined vs split BP, ~1.5% duplicates, ~0.4% typos (e.g. weight 520), 10% missing RCH IDs | Real exports look like this |

Parameters are **illustrative, not epidemiological estimates**. No intervention effect is simulated, so the KPI page will honestly show baseline ≈ pilot.

### Parameters to focus on (they drive every feature)

* **Identity and linkage**: RCH ID, name, phone. These feed the master patient index across facilities.
* **Time anchors**: LMP/EDD, visit dates, due dates, so the system can compute gestational age, timelines and follow-up status.
* **Follow-ups**: booked appointments, register "next due" dates, and note instructions. These drive the primary KPI.
* **Status fields**: completed vs no-show visits, resulted vs pending investigations.
* **Language, caregiver and consent**: these drive multilingual, consent-gated communication.
* **Recorded values** (Hb, BP, weight…): shown **exactly as documented**, never interpreted.

## How "reports and documents" are generated

* **Lab/imaging reports (PDF)**: `data_generator/writers.py::_lab_pdf` uses ReportLab to write one PDF per ANC visit, with patient name, RCH ID, sample date and lines in the form `Test | Result | Reported on`. Pending tests read "Result awaited".
* **Clinical notes**: `data_generator/notes.py` contains templates for ANC, delivery/discharge, PNC and immunization notes. They use Indian OPD conventions (G2P1, POG 18w3d, O/E, MCP card) plus documented follow-up sentences.
* **Register remarks**: free text in the Excel register ("Referred to DH for delivery", "Called – not reachable").
* **Patient reports** (the outgoing Share Report): built by the app from verified answers (see `docs/06_user_interface.md`).

## Optional: other synthetic or real sources

* **Synthea** (open-source synthetic patient generator, includes a pregnancy module):
  `java -jar synthea-with-dependencies.jar -p 500 --exporter.csv.export true`.
  Map `patients.csv`, `encounters.csv` and `observations.csv` into `etl/extract.py` the same way as the EHR exports. It's useful for scale testing, but it is US-centric.
* **Your own clinic (pilot phase)**: drop the clinic's real exports into `data/raw/` using the same folder conventions, inside the clinic's environment, with ethics approval. Nothing else changes.
* **ONC / MIMIC notes**: only as a private style reference for note templates or for evaluating the note-instruction extractor, locally and under their licences. Never in the app or the demo.
