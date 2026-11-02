"""ClinieSync responsible-AI policy: the intent routing matrix + role access matrix.

This file is the single source of truth shown in the UI (Trust Center) and
enforced by the guard layers. Changing policy = editing this file (reviewed,
version-controlled), never prompting the model differently.
"""
from __future__ import annotations

POLICY_VERSION = "2026.10-hackathon"

# ---- intent routing matrix (slide 8 of the idea deck) ----------------------
INTENT_MATRIX = [
    {"intent": "patient_retrieval", "label": "Patient Retrieval", "mechanism": "RAG + SQL", "action": "allowed"},
    {"intent": "patient_summary", "label": "Patient Summarization", "mechanism": "RAG", "action": "allowed"},
    {"intent": "population_analytics", "label": "Population Analytics", "mechanism": "SQL", "action": "allowed"},
    {"intent": "care_coordination", "label": "Care Coordination", "mechanism": "RAG / SQL", "action": "allowed"},
    {"intent": "diagnosis", "label": "Diagnosis / interpretation of results", "mechanism": "-", "action": "blocked"},
    {"intent": "treatment_prescription", "label": "Treatment / prescription / dosing", "mechanism": "-", "action": "blocked"},
    {"intent": "clinical_advice", "label": "Clinical advice / management decisions", "mechanism": "-", "action": "blocked"},
    {"intent": "risk_scoring", "label": "Risk scoring / prediction", "mechanism": "-", "action": "blocked"},
    {"intent": "prompt_injection", "label": "Prompt injection / jailbreak", "mechanism": "-", "action": "blocked"},
    {"intent": "bulk_data_export", "label": "Bulk personal-data export", "mechanism": "-", "action": "blocked"},
    {"intent": "out_of_scope", "label": "Out of scope", "mechanism": "-", "action": "declined"},
]
ALLOWED_INTENTS = {r["intent"] for r in INTENT_MATRIX if r["action"] == "allowed"}

# ---- role access matrix -----------------------------------------------------
ROLE_INTENTS = {
    "doctor": {"patient_retrieval", "patient_summary", "population_analytics", "care_coordination"},
    "coordinator": {"patient_retrieval", "patient_summary", "population_analytics", "care_coordination"},
    "admin": {"population_analytics", "care_coordination"},
}
# Minimum-necessary data scopes per role
ROLE_SCOPES = {
    "doctor": {"identifiers", "contact", "clinical_values", "notes", "share_reports"},
    "coordinator": {"identifiers", "contact"},          # operational view: visits, follow-ups, contact details
    "admin": set(),                                      # de-identified aggregates only
}

REFUSALS = {
    "diagnosis": "ClinieSync does not diagnose or interpret clinical findings. It can retrieve the values and "
                 "reports exactly as documented so the treating clinician can review them.",
    "treatment_prescription": "ClinieSync cannot recommend, prescribe or dose any treatment. Treatment decisions "
                              "stay with the treating clinician. It can show what was documented at previous visits.",
    "clinical_advice": "ClinieSync does not provide clinical advice or management decisions. It can retrieve the "
                       "documented record, summarise it, or show pending follow-ups.",
    "risk_scoring": "ClinieSync does not score, predict or label clinical risk. It can list documented pending or "
                    "overdue follow-ups, which is an operational (not clinical) view.",
    "prompt_injection": "This request tries to change ClinieSync's safety rules, so it was blocked and logged.",
    "bulk_data_export": "Bulk export of personal data is not available through the assistant. Use the governed "
                        "data-export process with your administrator.",
    "out_of_scope": "That is outside ClinieSync's scope. ClinieSync helps with patient record retrieval, "
                    "summaries of documented care, population analytics and care coordination.",
    "access": "Your role does not have access to this kind of information. Administrators see de-identified, "
              "aggregate analytics only.",
}

SUGGESTIONS = {
    "doctor": ["Show the patient's last 3 visits", "Summarize the patient's pregnancy journey so far",
               "Which investigations are pending results for this patient?"],
    "coordinator": ["Show patients with pending documented follow-ups", "List follow-ups due this week",
                    "Which babies are due for vaccination this week?"],
    "admin": ["How many maternal and child healthcare visits occurred this month?",
              "Show ANC drop-off rate trends", "Investigation utilization and turnaround time"],
}

DISCLAIMER = ("AI-organised from documented records only - not clinical advice. "
              "Verify against the source record before use.")
