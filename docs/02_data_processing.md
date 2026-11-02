# 2 · Data processing: ETL, cleaning, normalisation and the unified data layer

**Tech stack:** Python 3.12 · pandas · openpyxl (Excel) · pypdf (PDF) · rapidfuzz (record linkage) · SQLAlchemy 2 (load).
OCR for scanned PDFs is a drop-in addition in `extract.py` (`pytesseract`).

```
data/raw/*  ──► EXTRACT ──► CLEAN ──► NORMALISE ──► LINK (MPI) ──► DERIVE ──► LOAD (SQL) ──► INDEX (vector)
               extract.py  clean.py   vocab.py      transform.py   followups.py  load.py      ai/rag/indexer.py
                                         └────────── orchestrated by etl/pipeline.py ──────────┘
```

Run it with `python -m etl.pipeline`. A full run takes about 5 s, plus about 40–70 s the first time the index is built.

## Step by step

| Step | What happens | Code |
|---|---|---|
| **Extract** | Each source becomes harmonised *staging* tables (patients, pregnancies, encounters, observations, labs, appointments, children, immunizations, documents). The wide Excel register is **melted** (ANC1..ANC5 columns become one row per visit). PDF lab reports are parsed with regex (`RCH ID`, `Sample Date`, `Test \| Result \| Reported on`). Every row keeps its `source_system` for lineage. | `etl/extract.py` |
| **Clean** | Day-first date parsing (`2026-03-04`, `04/03/2026`, `04.03.2026`, `04-Mar-26`, Excel dates); phone numbers to `+91XXXXXXXXXX`; name casing; exact de-duplication; **quarantine** with a reason for anything implausible. Plausibility checks are data-entry checks (e.g. weight 520 kg), never clinical judgement. | `etl/clean.py` |
| **Normalise** | Local terms become canonical codes through a controlled vocabulary: `Hb/HB/Haemoglobin → hemoglobin (LOINC 718-7)`, `Wt → weight (29463-7)`, BP `110/70` split into `8480-6`/`8462-4`, `TIFFA scan → usg_anomaly`, `DNA → no_show`. Units: `g%` → g/dL, grams → kg. Unmapped terms are reported, not dropped. | `etl/vocab.py` |
| **Link (MPI)** | Master patient index: link by RCH ID, then by phone + fuzzy name (rapidfuzz ≥ 90). One canonical `CS-xxxxxx` ID per woman. Pregnancy episodes from different facilities are merged when LMPs fall within 21 days. Children are de-duplicated by mother + date of birth. The demo recovers **exactly 600 patients from 669 source records**, matching the ground truth. | `etl/transform.py::patients` |
| **Derive** | ANC sequence (ANC1..ANC5), PNC day (D3/D7/D42) from the delivery date, immunization session from the child's age, gestational age at each visit, and pregnancy status. **Documented follow-ups** are taken from appointments, register next-due dates and note instructions; 1,769 of 2,061 note instructions attach to an existing booking. Each follow-up's status (completed / due / overdue / missed / cancelled) is computed from what actually happened afterwards. | `etl/transform.py`, `etl/followups.py` |
| **Load** | Rebuild the clinical tables and keep app tables (users, reviews, audit). Coordinators' workflow states carry over across reloads. | `etl/load.py` |
| **Index** | Chunk the documents (notes, lab reports, discharge summaries, remarks) and embed them into the vector store with patient/visit metadata. | `ai/rag/indexer.py` |
| **Report** | Data-quality report: source counts, duplicates, quarantine reasons, linkage stats, follow-up extraction, timings. Saved to `data/processed/quality_report.json` and shown in **Data Hub**. | `etl/pipeline.py` |

## The unified data layer

The canonical, FHIR-shaped schema in `database/models.py` covers `patients`, `patient_identifiers` (MPI), `pregnancies` (EpisodeOfCare), `children`, `visits` (Encounter), `observations` (LOINC), `investigations` (ServiceRequest/DiagnosticReport), `immunizations`, `followups` (Appointment), and `documents` (DocumentReference). Because the shape follows FHIR, `integrations/care_ohc/fhir_export.py` can emit standard FHIR R4 bundles for OHC CARE or any FHIR server.

## Adding a real clinic source (pilot)

1. Put the export in `data/raw/<new folder>`.
2. Add an `extract_*` function that outputs the staging columns, and list it in `extract_all`.
3. Run the ETL. Read the **unmapped terms** and **quarantine** sections of the quality report, then extend `etl/vocab.py`.
4. Preview Excel registers before loading them in **Data Hub → Validate a new Excel ANC register**.
