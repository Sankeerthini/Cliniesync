"""Reference tables for the synthetic Maternal & Child Health (MCH) cohort.

Schedules follow publicly documented Government of India programme guidance
(4+ ANC contacts with the first in the 1st trimester, PNC contacts, and the
Universal Immunization Programme schedule). All people, phone numbers and IDs
are FAKE. Facility names are used only as labels for synthetic data.
"""

FACILITIES = [
    # id, name, type, district, source system, language mix (kn, hi, bn, en)
    {"facility_id": "F1", "name": "PHC Hebbal", "facility_type": "PHC", "district": "Bengaluru Urban",
     "source_system": "ehr_export", "lang_mix": {"kn": .45, "hi": .20, "bn": .15, "en": .20},
     "villages": ["Hebbal", "Yelahanka", "Kodigehalli", "Jakkur", "Sahakarnagar", "Thanisandra"]},
    {"facility_id": "F2", "name": "District Hospital Tumakuru", "facility_type": "District Hospital",
     "district": "Tumakuru", "source_system": "ehr_export", "lang_mix": {"kn": .60, "hi": .10, "bn": .05, "en": .25},
     "villages": ["Kunigal", "Gubbi", "Tiptur", "Sira", "Koratagere", "Tumakuru Town"]},
    {"facility_id": "F3", "name": "CHC Anekal", "facility_type": "CHC", "district": "Bengaluru Urban",
     "source_system": "excel_register", "lang_mix": {"kn": .45, "hi": .20, "bn": .25, "en": .10},
     "villages": ["Chandapura", "Attibele", "Jigani", "Hebbagodi", "Sarjapura", "Anekal Town"]},
]
FACILITY_WEIGHTS = {"F1": .40, "F2": .35, "F3": .25}

PROVIDERS = [
    {"provider_id": "P01", "name": "Dr. Ananya Rao", "role": "Medical Officer (OBG)", "facility_id": "F1"},
    {"provider_id": "P02", "name": "Lakshmi B.", "role": "ANM", "facility_id": "F1"},
    {"provider_id": "P03", "name": "Rekha S.", "role": "Care Coordinator", "facility_id": "F1"},
    {"provider_id": "P04", "name": "Dr. Meera Kulkarni", "role": "Obstetrician", "facility_id": "F2"},
    {"provider_id": "P05", "name": "Dr. Farhan Ali", "role": "Paediatrician", "facility_id": "F2"},
    {"provider_id": "P06", "name": "Joseph T.", "role": "Care Coordinator", "facility_id": "F2"},
    {"provider_id": "P07", "name": "Dr. Sowmya Hegde", "role": "Medical Officer", "facility_id": "F3"},
    {"provider_id": "P08", "name": "Shanthamma K.", "role": "ANM", "facility_id": "F3"},
]
DOCTOR_BY_FACILITY = {"F1": "P01", "F2": "P04", "F3": "P07"}
PAEDIATRICIAN_BY_FACILITY = {"F1": "P01", "F2": "P05", "F3": "P07"}

FIRST_NAMES = {
    "kn": ["Lakshmi", "Shwetha", "Kavya", "Divya", "Ramya", "Pooja", "Asha", "Bhavya", "Sahana", "Nandini",
           "Pavithra", "Sowmya", "Anitha", "Chaitra", "Deepa", "Harini", "Keerthana", "Manjula", "Roopa",
           "Sushma", "Vidya", "Geetha", "Shruthi", "Tejaswini", "Varsha"],
    "hi": ["Priya", "Neha", "Anjali", "Sunita", "Kiran", "Sapna", "Rani", "Meena", "Nisha", "Kajal", "Komal",
           "Sonam", "Rinki", "Khushbu", "Shabnam", "Ruksar", "Afreen", "Savita", "Poonam", "Guddi"],
    "bn": ["Moumita", "Rupa", "Sathi", "Tumpa", "Mampi", "Sangita", "Rina", "Shampa", "Barnali", "Ruma",
           "Payel", "Jhuma", "Mousumi", "Sumana", "Rehana", "Nasrin", "Tania", "Rumki"],
    "en": ["Mary", "Sharon", "Grace", "Jennifer", "Shalini", "Ritu", "Sneha", "Aishwarya", "Fathima",
           "Nikita", "Ayesha", "Joyce", "Swathi", "Megha"],
}
SURNAMES = {
    "kn": ["Gowda", "Shetty", "Naik", "Hegde", "Rao", "Kumar", "Reddy", "Patil", "Bhat", "Murthy", "Prasad", "Achar"],
    "hi": ["Sharma", "Yadav", "Verma", "Gupta", "Kumari", "Singh", "Khatun", "Ansari", "Mishra", "Prajapati"],
    "bn": ["Das", "Mondal", "Ghosh", "Roy", "Biswas", "Saha", "Sarkar", "Paul", "Bibi", "Sheikh", "Halder"],
    "en": ["D'Souza", "Fernandes", "Joseph", "Thomas", "Menon", "Pinto", "Khan", "Nair", "Mathew", "Iyer"],
}
MALE_NAMES = {
    "kn": ["Manjunath", "Ravi", "Suresh", "Mahesh", "Naveen", "Prakash", "Kiran", "Santhosh", "Girish"],
    "hi": ["Rajesh", "Sunil", "Amit", "Rakesh", "Imran", "Salman", "Pappu", "Dinesh", "Vikas"],
    "bn": ["Subrata", "Biswajit", "Tapan", "Rahul", "Sujoy", "Abdul", "Rafiq", "Pintu", "Bapi"],
    "en": ["John", "Arun", "Vivek", "Rohan", "Anand", "Sameer", "Thomas", "Rajiv"],
}
CAREGIVER_RELATIONS = [("Husband", .70), ("Mother-in-law", .15), ("Mother", .15)]
ELDER_NAMES = {
    "kn": ["Gowramma", "Siddamma", "Jayamma"], "hi": ["Kamla Devi", "Shanti Devi", "Saroj"],
    "bn": ["Anima", "Kalpana", "Minati"], "en": ["Lucy", "Mariamma", "Saraswathi"],
}

# ---- antenatal care schedule (target gestational weeks after registration) ----
ANC_TARGET_WEEKS = [20, 26, 32, 36]           # ANC2-ANC4 per GoI windows; ANC5 at 38w for some
ANC_EXTRA_WEEK = 38

# ---- PNC contacts (days after delivery) ----
PNC_DAYS = [(3, "PNC-D3", .78), (7, "PNC-D7", .68), (42, "PNC-D42", .55)]

# ---- Universal Immunization Programme (subset), days after birth ----
UIP_SCHEDULE = [
    ("Birth", 0, ["BCG", "OPV-0", "Hep B (birth)"], 1.00),
    ("6 weeks", 42, ["Pentavalent-1", "OPV-1", "Rotavirus-1", "fIPV-1", "PCV-1"], .90),
    ("10 weeks", 70, ["Pentavalent-2", "OPV-2", "Rotavirus-2"], .84),
    ("14 weeks", 98, ["Pentavalent-3", "OPV-3", "Rotavirus-3", "fIPV-2", "PCV-2"], .78),
    ("9 months", 270, ["MR-1", "PCV-Booster"], .70),
]

# ---- investigations: canonical code -> (display, category, local-name variants used by sources) ----
TESTS = {
    "cbc":            ("Complete Blood Count / Haemoglobin", "lab", ["CBC", "Complete Blood Count", "Hb/CBC"]),
    "blood_group":    ("Blood Group & Rh", "lab", ["Blood Group & Rh", "BG & Rh", "ABO-Rh typing"]),
    "hiv":            ("HIV I & II screening", "lab", ["HIV I & II", "HIV screening", "HIV 1/2"]),
    "vdrl":           ("Syphilis screening (VDRL/RPR)", "lab", ["VDRL", "RPR/VDRL", "Syphilis (VDRL)"]),
    "hbsag":          ("HBsAg", "lab", ["HBsAg", "Hepatitis B surface Ag"]),
    "urine_routine":  ("Urine routine", "lab", ["Urine R/M", "Urine Routine", "Urine (Alb/Sugar)"]),
    "ogtt":           ("OGTT 75 g (2-hour)", "lab", ["OGTT 75g", "GTT 75 gm", "OGTT (2 hr)"]),
    "tsh":            ("TSH", "lab", ["TSH", "Thyroid (TSH)"]),
    "usg_dating":     ("USG obstetric - dating", "imaging", ["USG Obstetric (Dating)", "Dating scan", "USG early pregnancy"]),
    "usg_anomaly":    ("USG obstetric - anomaly (18-22 w)", "imaging", ["TIFFA scan", "Anomaly scan", "USG Level II"]),
    "usg_growth":     ("USG obstetric - growth", "imaging", ["Growth scan", "USG growth & liquor", "USG 3rd trimester"]),
}

# ---- observation codes: canonical code -> (display, unit, LOINC) ----
OBS_CODES = {
    "weight":         ("Body weight", "kg", "29463-7"),
    "bp_systolic":    ("Systolic blood pressure", "mmHg", "8480-6"),
    "bp_diastolic":   ("Diastolic blood pressure", "mmHg", "8462-4"),
    "hemoglobin":     ("Haemoglobin", "g/dL", "718-7"),
    "fundal_height":  ("Fundal height", "cm", "11881-0"),
    "fetal_heart_rate": ("Fetal heart rate", "bpm", "55283-6"),
    "urine_albumin":  ("Urine albumin (dipstick)", None, None),
    "infant_weight":  ("Infant weight", "kg", "29463-7"),
}

COMPLAINTS = ["No fresh complaints", "Routine visit, no complaints", "Mild backache", "Occasional nausea",
              "Mild pedal swelling in evenings", "Feels well", "Mild fatigue", "Came for report review"]
