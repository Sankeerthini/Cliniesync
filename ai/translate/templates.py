"""Patient-facing message templates in English, Hindi, Bengali and Kannada.

Design choice: messages sent to patients/caregivers are TEMPLATES with slots
(name, date, facility) - not free-form generated text. Templates are reviewed
once by native speakers, so every message is safe, consistent and contains no
clinical advice. (Pilot task: have each translation reviewed by a native-speaking
clinician/ANM - see docs/05_safety_guardrails.md.)
"""
from __future__ import annotations

LANGUAGES = {"en": "English", "hi": "हिन्दी (Hindi)", "bn": "বাংলা (Bengali)", "kn": "ಕನ್ನಡ (Kannada)"}

VISIT_NAMES = {
    "ANC visit": {"en": "antenatal check-up", "hi": "प्रसवपूर्व जाँच", "bn": "প্রসবপূর্ব চেক-আপ", "kn": "ಪ್ರಸವಪೂರ್ವ ತಪಾಸಣೆ"},
    "PNC visit": {"en": "postnatal check-up", "hi": "प्रसव के बाद की जाँच", "bn": "প্রসবোত্তর চেক-আপ",
                  "kn": "ಹೆರಿಗೆಯ ನಂತರದ ತಪಾಸಣೆ"},
    "Immunization": {"en": "baby's vaccination", "hi": "शिशु का टीकाकरण", "bn": "শিশুর টিকাকরণ", "kn": "ಮಗುವಿನ ಲಸಿಕೆ"},
    "Investigation review": {"en": "test report review", "hi": "जाँच रिपोर्ट दिखाने", "bn": "পরীক্ষার রিপোর্ট দেখানো",
                             "kn": "ಪರೀಕ್ಷಾ ವರದಿ ಪರಿಶೀಲನೆ"},
}

REMINDER = {
    "overdue": {
        "en": "Namaste {name}, a reminder from {facility}: {for_whom}{visit} was due on {date}. Please visit the "
              "health facility or call {phone} to fix a new date. - {facility}",
        "hi": "नमस्ते {name}, {facility} की ओर से याद दिलाना: {for_whom}{visit} की तारीख {date} थी। कृपया स्वास्थ्य "
              "केंद्र आएँ या नई तारीख के लिए {phone} पर कॉल करें। - {facility}",
        "bn": "নমস্কার {name}, {facility} থেকে মনে করিয়ে দেওয়া হচ্ছে: {for_whom}{visit} {date} তারিখে ছিল। অনুগ্রহ করে "
              "স্বাস্থ্যকেন্দ্রে আসুন অথবা নতুন তারিখের জন্য {phone} নম্বরে ফোন করুন। - {facility}",
        "kn": "ನಮಸ್ಕಾರ {name}, {facility} ಇಂದ ಜ್ಞಾಪನೆ: {for_whom}{visit} {date} ರಂದು ನಿಗದಿಯಾಗಿತ್ತು. ದಯವಿಟ್ಟು "
              "ಆರೋಗ್ಯ ಕೇಂದ್ರಕ್ಕೆ ಬನ್ನಿ ಅಥವಾ ಹೊಸ ದಿನಾಂಕಕ್ಕಾಗಿ {phone} ಗೆ ಕರೆ ಮಾಡಿ. - {facility}",
    },
    "upcoming": {
        "en": "Namaste {name}, a reminder from {facility}: {for_whom}{visit} is due on {date}. Please come on time. "
              "For questions call {phone}. - {facility}",
        "hi": "नमस्ते {name}, {facility} की ओर से याद दिलाना: {for_whom}{visit} {date} को है। कृपया समय पर आएँ। "
              "किसी भी जानकारी के लिए {phone} पर कॉल करें। - {facility}",
        "bn": "নমস্কার {name}, {facility} থেকে মনে করিয়ে দেওয়া হচ্ছে: {for_whom}{visit} {date} তারিখে আছে। অনুগ্রহ করে "
              "সময়মতো আসুন। কোনো প্রশ্ন থাকলে {phone} নম্বরে ফোন করুন। - {facility}",
        "kn": "ನಮಸ್ಕಾರ {name}, {facility} ಇಂದ ಜ್ಞಾಪನೆ: {for_whom}{visit} {date} ರಂದು ಇದೆ. ದಯವಿಟ್ಟು ಸಮಯಕ್ಕೆ ಬನ್ನಿ. "
              "ಯಾವುದೇ ಪ್ರಶ್ನೆಗಳಿಗೆ {phone} ಗೆ ಕರೆ ಮಾಡಿ. - {facility}",
    },
}
# "{patient}'s " prefix when the message goes to a caregiver
FOR_PATIENT = {"en": "{patient}'s ", "hi": "{patient} की ", "bn": "{patient}-এর ", "kn": "{patient} ಅವರ "}
YOUR = {"en": "your ", "hi": "आपकी ", "bn": "আপনার ", "kn": "ನಿಮ್ಮ "}

REPORT_LABELS = {
    "title": {"en": "Visit summary", "hi": "जाँच सारांश", "bn": "ভিজিট সারাংশ", "kn": "ಭೇಟಿಯ ಸಾರಾಂಶ"},
    "patient": {"en": "Patient", "hi": "मरीज़", "bn": "রোগী", "kn": "ರೋಗಿ"},
    "facility": {"en": "Health facility", "hi": "स्वास्थ्य केंद्र", "bn": "স্বাস্থ্যকেন্দ্র", "kn": "ಆರೋಗ್ಯ ಕೇಂದ್ರ"},
    "verified_by": {"en": "Verified by", "hi": "सत्यापित", "bn": "যাচাই করেছেন", "kn": "ಪರಿಶೀಲಿಸಿದವರು"},
    "date": {"en": "Date", "hi": "तारीख", "bn": "তারিখ", "kn": "ದಿನಾಂಕ"},
    "pregnancy": {"en": "Pregnancy details", "hi": "गर्भावस्था विवरण", "bn": "গর্ভাবস্থার বিবরণ", "kn": "ಗರ್ಭಧಾರಣೆಯ ವಿವರಗಳು"},
    "lmp": {"en": "Last menstrual period", "hi": "अंतिम माहवारी", "bn": "শেষ মাসিক", "kn": "ಕೊನೆಯ ಮುಟ್ಟಿನ ದಿನ"},
    "edd": {"en": "Expected date of delivery", "hi": "प्रसव की संभावित तारीख", "bn": "প্রসবের সম্ভাব্য তারিখ",
            "kn": "ಹೆರಿಗೆಯ ನಿರೀಕ್ಷಿತ ದಿನಾಂಕ"},
    "visits": {"en": "Visits", "hi": "जाँच के लिए आना", "bn": "ভিজিট", "kn": "ಭೇಟಿಗಳು"},
    "visit": {"en": "Visit", "hi": "जाँच", "bn": "ভিজিট", "kn": "ಭೇಟಿ"},
    "tests": {"en": "Tests", "hi": "जाँचें (टेस्ट)", "bn": "পরীক্ষা", "kn": "ಪರೀಕ್ಷೆಗಳು"},
    "test": {"en": "Test", "hi": "टेस्ट", "bn": "পরীক্ষা", "kn": "ಪರೀಕ್ಷೆ"},
    "result": {"en": "Result (as recorded)", "hi": "परिणाम (जैसा दर्ज है)", "bn": "ফলাফল (যেমন লেখা আছে)",
               "kn": "ಫಲಿತಾಂಶ (ದಾಖಲಿಸಿದಂತೆ)"},
    "awaited": {"en": "Result awaited", "hi": "परिणाम आना बाकी", "bn": "ফলাফল আসা বাকি", "kn": "ಫಲಿತಾಂಶ ಬರಬೇಕಿದೆ"},
    "next": {"en": "Next appointments", "hi": "अगली तारीखें", "bn": "পরবর্তী তারিখ", "kn": "ಮುಂದಿನ ದಿನಾಂಕಗಳು"},
    "doctor_note": {"en": "Doctor's note", "hi": "डॉक्टर का नोट", "bn": "ডাক্তারের নোট", "kn": "ವೈದ್ಯರ ಟಿಪ್ಪಣಿ"},
    "note_in_english": {"en": "", "hi": "(अंग्रेज़ी में)", "bn": "(ইংরেজিতে)", "kn": "(ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿ)"},
    "machine_translated": {"en": "", "hi": "मशीन अनुवाद - मूल अंग्रेज़ी नीचे है", "bn": "মেশিন অনুবাদ - মূল ইংরেজি নিচে",
                           "kn": "ಯಂತ್ರ ಅನುವಾದ - ಮೂಲ ಇಂಗ್ಲಿಷ್ ಕೆಳಗೆ"},
    "footer": {
        "en": "This summary lists information recorded at your health facility. It is not a prescription. "
              "For any question, please contact your health facility.",
        "hi": "इस सारांश में आपके स्वास्थ्य केंद्र में दर्ज जानकारी है। यह पर्ची (प्रिस्क्रिप्शन) नहीं है। "
              "किसी भी सवाल के लिए अपने स्वास्थ्य केंद्र से संपर्क करें।",
        "bn": "এই সারাংশে আপনার স্বাস্থ্যকেন্দ্রে লেখা তথ্য রয়েছে। এটি প্রেসক্রিপশন নয়। "
              "যেকোনো প্রশ্নের জন্য আপনার স্বাস্থ্যকেন্দ্রে যোগাযোগ করুন।",
        "kn": "ಈ ಸಾರಾಂಶದಲ್ಲಿ ನಿಮ್ಮ ಆರೋಗ್ಯ ಕೇಂದ್ರದಲ್ಲಿ ದಾಖಲಾದ ಮಾಹಿತಿ ಇದೆ. ಇದು ಔಷಧಿ ಚೀಟಿ ಅಲ್ಲ. "
              "ಯಾವುದೇ ಪ್ರಶ್ನೆಗೆ ನಿಮ್ಮ ಆರೋಗ್ಯ ಕೇಂದ್ರವನ್ನು ಸಂಪರ್ಕಿಸಿ.",
    },
    "sms": {
        "en": "{facility}: your visit summary dated {date} has been verified by {doctor}. Next appointment: {next}. "
              "The full summary has been sent to you.",
        "hi": "{facility}: {date} का आपका जाँच सारांश {doctor} द्वारा सत्यापित किया गया है। अगली तारीख: {next}। "
              "पूरा सारांश आपको भेज दिया गया है।",
        "bn": "{facility}: {date} তারিখের আপনার ভিজিট সারাংশ {doctor} যাচাই করেছেন। পরবর্তী তারিখ: {next}। "
              "সম্পূর্ণ সারাংশ আপনাকে পাঠানো হয়েছে।",
        "kn": "{facility}: {date} ರ ನಿಮ್ಮ ಭೇಟಿಯ ಸಾರಾಂಶವನ್ನು {doctor} ಪರಿಶೀಲಿಸಿದ್ದಾರೆ. ಮುಂದಿನ ದಿನಾಂಕ: {next}. "
              "ಪೂರ್ಣ ಸಾರಾಂಶವನ್ನು ನಿಮಗೆ ಕಳುಹಿಸಲಾಗಿದೆ.",
    },
    "none": {"en": "none scheduled", "hi": "कोई तय नहीं", "bn": "নির্ধারিত নেই", "kn": "ನಿಗದಿಯಾಗಿಲ್ಲ"},
}

VISIT_TYPE_NAMES = {
    "ANC": {"en": "Antenatal check-up", "hi": "प्रसवपूर्व जाँच", "bn": "প্রসবপূর্ব চেক-আপ", "kn": "ಪ್ರಸವಪೂರ್ವ ತಪಾಸಣೆ"},
    "Delivery": {"en": "Delivery", "hi": "प्रसव", "bn": "প্রসব", "kn": "ಹೆರಿಗೆ"},
    "PNC": {"en": "Postnatal check-up", "hi": "प्रसव के बाद की जाँच", "bn": "প্রসবোত্তর চেক-আপ", "kn": "ಹೆರಿಗೆಯ ನಂತರದ ತಪಾಸಣೆ"},
    "Child": {"en": "Baby's vaccination", "hi": "शिशु का टीकाकरण", "bn": "শিশুর টিকাকরণ", "kn": "ಮಗುವಿನ ಲಸಿಕೆ"},
}


def label(key: str, lang: str) -> str:
    return REPORT_LABELS[key].get(lang) or REPORT_LABELS[key]["en"]


def reminder_text(lang: str, *, overdue: bool, name: str, facility: str, followup_type: str, date_str: str,
                  phone: str, patient_name: str | None = None) -> str:
    lang = lang if lang in LANGUAGES else "en"
    for_whom = FOR_PATIENT[lang].format(patient=patient_name) if patient_name else YOUR[lang]
    visit = VISIT_NAMES.get(followup_type, VISIT_NAMES["ANC visit"])[lang]
    return REMINDER["overdue" if overdue else "upcoming"][lang].format(
        name=name, facility=facility, for_whom=for_whom, visit=visit, date=date_str, phone=phone)
