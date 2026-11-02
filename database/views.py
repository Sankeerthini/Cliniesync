"""De-identified analytics views.

These are the ONLY relations the natural-language-to-SQL path may query. They
contain no names, phone numbers or free text, so even a mis-generated query
cannot leak identity to an administrator. Kept to portable SQL (no date
functions) so they run on SQLite and PostgreSQL unchanged.
"""

ANALYTICS_VIEWS: dict[str, str] = {
    "v_visits": """
        SELECT v.visit_id, v.patient_id AS patient_key, v.facility_id, f.name AS facility_name,
               f.source_system AS facility_source, v.visit_date, v.visit_month, v.visit_category, v.visit_type, v.sequence,
               v.ga_weeks, v.status
        FROM visits v JOIN facilities f ON f.facility_id = v.facility_id
    """,
    "v_pregnancies": """
        SELECT p.pregnancy_id, p.patient_id AS patient_key, pt.facility_id, f.name AS facility_name,
               p.registration_date, p.registration_month, p.registration_ga_weeks, p.edd,
               p.status, p.delivery_date, p.delivery_mode, p.anc_visits_completed
        FROM pregnancies p
        JOIN patients pt ON pt.patient_id = p.patient_id
        JOIN facilities f ON f.facility_id = pt.facility_id
    """,
    "v_investigations": """
        SELECT i.investigation_id, i.patient_id AS patient_key, v.facility_id, f.name AS facility_name,
               i.test_code, i.test_name, i.category, i.ordered_on, i.ordered_month,
               i.resulted_on, i.status, i.turnaround_days
        FROM investigations i
        LEFT JOIN visits v ON v.visit_id = i.visit_id
        LEFT JOIN facilities f ON f.facility_id = v.facility_id
    """,
    "v_followups": """
        SELECT fu.followup_id, fu.patient_id AS patient_key, fu.facility_id, f.name AS facility_name,
               fu.followup_type, fu.due_on, fu.due_month, fu.status, fu.workflow_state,
               fu.contact_attempts, fu.completed_on, fu.origin
        FROM followups fu JOIN facilities f ON f.facility_id = fu.facility_id
    """,
    "v_immunizations": """
        SELECT im.imm_id, im.child_id AS child_key, c.facility_id, im.vaccine, im.schedule_label,
               im.due_on, im.given_on, im.status
        FROM immunizations im JOIN children c ON c.child_id = im.child_id
    """,
}

# Column documentation handed to the LLM for text-to-SQL (schema grounding).
VIEW_DOCS = """
v_visits(visit_id, patient_key, facility_id, facility_name, facility_source TEXT ('ehr_export' or 'excel_register'), visit_date DATE, visit_month TEXT 'YYYY-MM',
         visit_category TEXT one of ['ANC','Delivery','PNC','Child'], visit_type TEXT e.g. 'ANC1','ANC2','PNC-D7','Immunization-6w',
         sequence INT, ga_weeks REAL, status TEXT one of ['completed','no_show'])
v_pregnancies(pregnancy_id, patient_key, facility_id, facility_name, registration_date DATE, registration_month TEXT 'YYYY-MM',
         registration_ga_weeks REAL, edd DATE, status TEXT one of ['antenatal','delivered','postnatal_closed','no_recent_contact'],
         delivery_date DATE, delivery_mode TEXT, anc_visits_completed INT)
v_investigations(investigation_id, patient_key, facility_id, facility_name, test_code TEXT, test_name TEXT,
         category TEXT one of ['lab','imaging'], ordered_on DATE, ordered_month TEXT 'YYYY-MM', resulted_on DATE,
         status TEXT one of ['resulted','pending'], turnaround_days INT)
v_followups(followup_id, patient_key, facility_id, facility_name, followup_type TEXT one of
         ['ANC visit','PNC visit','Immunization','Investigation review'], due_on DATE, due_month TEXT 'YYYY-MM',
         status TEXT one of ['upcoming','due','overdue','completed','missed','cancelled'], workflow_state TEXT,
         contact_attempts INT, completed_on DATE, origin TEXT)
v_immunizations(imm_id, child_key, facility_id, vaccine TEXT, schedule_label TEXT, due_on DATE, given_on DATE,
         status TEXT one of ['given','due','overdue'])
Dates are ISO strings 'YYYY-MM-DD'; compare them with string literals. Use visit_month/due_month/ordered_month
for monthly grouping (no date functions).
""".strip()
