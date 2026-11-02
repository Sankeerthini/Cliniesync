# Integrating with OHC CARE (Open Healthcare Network)

The organisers offered CARE, OHC's open-source EMR, as a platform with a plugin architecture: frontend plugins (React), backend plugins (Django), or both. ClinieSync is designed to sit **next to** an EMR, so there are two complementary paths.

## Path A: data exchange via FHIR (implemented here)

`fhir_export.py` turns ClinieSync's unified layer into **FHIR R4** resources: Patient, EpisodeOfCare, Encounter, Observation (LOINC), ServiceRequest/DiagnosticReport, Appointment, DocumentReference.

```bash
python -m integrations.care_ohc.fhir_export CS-000010 > bundle.json     # CLI
GET /api/patients/CS-000010/fhir                                        # API (doctor role)
```
The reverse direction (reading CARE data into ClinieSync) is a new `extract_*` function in `etl/extract.py` that consumes CARE's API or FHIR output into the same staging tables.

## Path B: ClinieSync as a CARE plugin (next step, not yet built)

Start from the resources in the OHC mail: *Build on Care*, the plugin documentation, the **Care plugin scaffold** and the **OHC AI coding skills**. The two example plugins are good references:

* **Frontend plugin** (pattern: *Care AI Vision*): embed ClinieSync's panels inside CARE's patient page and dashboards. Candidates are the Ask box with patient context, the longitudinal timeline, and the follow-up queue. They would call the ClinieSync API.
* **Backend plugin** (pattern: *Care Filly*, a Django plugin that authenticates CARE users, checks facility permissions and issues short-lived tokens): let CARE users open ClinieSync with **CARE's own login and facility permissions**. The plugin would issue a short-lived token that `backend/app/security.py::current_user` validates, replacing the demo tokens.

Before building Path B, confirm the exact plugin interfaces and data models in the CARE plugin documentation. This repository does not assume them.
