"""Deterministic pattern library for the input and output guards.

Patterns are deliberately conservative (fail-closed): a false block costs the
user a rephrase (and is logged for review via 'report wrong block'), while a
false allow could put clinical decision-making into an assistive tool.
"""
from __future__ import annotations

import re

from ai.router.parameters import TERMS as PARAMS   # haemoglobin, BP, OGTT, TSH, ultrasound, ...

_I = re.I
_VALUES = rf"(results?|readings?|values?|labs?|reports?|vitals?|levels?|findings?|{PARAMS})"

CONDITIONS = (r"pre-?eclampsia|eclampsia|an(a)?emi(a|c)|gdm|gestational diabetes|diabet\w*|hypertensi\w*|\bpih\b|"
              r"sepsis|infection|jaundice|iugr|fgr|growth restriction|placenta previa|abruption|hypothyroid\w*|"
              r"hyperthyroid\w*|thyroid disorder|preterm labou?r|haemorrhage|hemorrhage|\bpph\b|oligohydramnios|"
              r"polyhydramnios|malnutrition|stunting|wasting|depression|fetal distress")

INPUT_PATTERNS: dict[str, list[re.Pattern]] = {
    "prompt_injection": [re.compile(p, _I) for p in [
        r"\bignore (all |any |the )?(previous|prior|above|earlier|your) (instructions|rules|prompts?|guidelines)",
        r"\bdisregard (your|the|all|any) (rules|instructions|guardrails|policy|policies)",
        r"\b(you are now|from now on you are|act as|pretend (to be|you are)|roleplay as)\b",
        r"\b(system prompt|developer mode|jailbreak|do anything now|\bDAN\b)",
        r"\bbypass\b.*\b(guard\w*|safety|filters?|rules|policy)",
        r"\breveal\b.*\b(prompt|instructions|password|api[ -]?key|secret)",
        r"\b(drop table|delete from|insert into|truncate table|union select)\b|;\s*--",
        r"</?\s*(system|assistant|instruction)s?\s*>",
        r"\brules? (do not|don'?t|no longer) apply\b|\b(no|without (any )?)(rules|restrictions|guardrails|filters)\b",
    ]],
    "bulk_data_export": [re.compile(p, _I) for p in [
        r"\b(export|download|dump|extract)\b.*\b(all|entire|whole|every)\b.*\b(patients?|data|database|records|numbers)\b",
        r"\b(all|every|list of all)\b.*\b(phone|mobile) numbers\b",
        r"\b(every|all) (patients?|mothers?)'?s? (address|addresses|phone|mobile|contact)",
    ]],
    "risk_scoring": [re.compile(p, _I) for p in [
        r"\brisk (score|scoring|stratif\w*|level|prediction|assessment|factors?)\b",
        r"\b(high|low|moderate)[- ]risk\b", r"\bat risk\b", r"\bpredict\w*\b", r"\bforecast\w*\b",
        r"\blikel(y|ihood)\b.*\b(develop|have|deliver|complications?|die|death|preterm)\b",
        r"\bprobability\b", r"\bprognos\w*\b", r"\bchances? of\b",
        r"\bwill (she|he|the baby|the patient|the mother) (have|develop|need|die|survive)\b",
        r"\b(rank|prioriti[sz]e|triage)\b.*\b(risk|severity|sickest|clinical)\b",
        r"\b(most|least|more|less) likely\b", r"\b(sickest|most (critical|serious|unwell|vulnerable))\b",
        r"\b(urgent|immediate) (attention|care|review)\b", r"\bneeds? (urgent )?attention\b", r"\bdeteriorat\w*\b",
        r"\b(red flags?|warning signs?)\b",
    ]],
    "treatment_prescription": [re.compile(p, _I) for p in [
        r"\bprescri(be|ption|bing)\b(?!.*\b(documented|recorded|was|were)\b)",
        r"\b(dose|dosage|dosing)\b", r"\b\d+\s?(mg|mcg|ml|iu)\b",
        r"\bwhat (medicine|medication|drug|tablet|injection|treatment|therapy|antibiotic)s?\b.*\b(give|start|use|take|"
        r"prescribe|should|for (her|him|the patient|this))\b",
        r"\bshould (i|we|she|he|the patient|they) (give|start|stop|take|increase|decrease|continue|change|switch)\b",
        r"\b(how to|how do (i|we)|best way to) (treat|manage|cure)\b",
        r"\b(treatment|management) (plan|options?|of|for)\b",
        r"\bwhich (antibiotic|drug|medicine|medication)\b",
        r"\bcan (she|he|i|we|the patient|the mother|the baby) (take|be given|have|use|get)\b(?!.*\b(appointment|"
        r"follow[- ]?up|reminder|report|copy)\b)",
        r"\b(start|stop|increase|decrease|titrate)\b.*\b(insulin|labetalol|nifedipine|iron|ifa|calcium|antibiotic|"
        r"methyldopa|aspirin|oxytocin|misoprostol|magnesium)\b",
    ]],
    "clinical_advice": [re.compile(p, _I) for p in [
        r"\b(what|how) should (i|we) (do|manage|treat|proceed)\b",
        r"\bwhat (would|do) you (do|suggest|recommend|advise)\b", r"\bfit (for|to) (discharge|travel|deliver\w*|work)\b",
        r"\b(should|do) (i|we) (worry|be worried|be concerned)\b",
        r"\bis it safe (to|for)\b",
        r"\b(recommend|suggest|advise)\b.*\b(treatment|medicine|drug|dose|tests?|investigations?|management|delivery|"
        r"admission|referral|scan)\b",
        r"\bnext (clinical )?steps?\b.*\b(management|treatment|care)\b",
        r"\b(does|do) (she|he|the patient|the mother|the baby) need\b(?!.*\b(follow[- ]?up|appointment|reminder|call)\b)",
        r"\bshould (she|he|the patient|the mother|the baby)\b(?!.*\b(remind\w*|call\w*|contact\w*|messag\w*|sms|"
        r"follow[- ]?up|appointment|come|visit)\b)",
        r"\b(induce|induction|c-?section|caesarean|cesarean|admit|admission|refer)\b.*\b(should|need|needed|indicated|"
        r"required|necessary)\b",
        r"\b(should|need to)\b.*\b(induce|admit|refer|operate|deliver)\b",
    ]],
    "diagnosis": [re.compile(p, _I) for p in [
        r"\bdiagnos\w*\b", r"\bdifferential\b", r"\brule out\b",
        rf"\b({CONDITIONS})\b",
        r"\b(is|are|was|were) (this|these|that|her|his|the|its)?\s*(\w+\s){0,2}(values?|results?|bp|blood pressure|hb|"
        r"ha?emoglobin|readings?|levels?|reports?|scan|weight)\s+(normal|abnormal|high|low|ok|okay|fine|concerning|"
        r"dangerous|worrying|worse|better)\b",
        r"\b(normal|abnormal)\b(?!.*\bdeliver)", r"\binterpret\w*\b",
        r"\bwhat (do|does|did) (this|these|the|her|his|that|those|they) .{0,50}\b(mean|indicate|suggest|imply)\b",
        # interpretive verbs applied to values: "assess her BP readings", "evaluate her lab results"
        rf"\b(assess\w*|evaluat\w*|appraise|comment on|judge|clinically (review|interpret))\b.{{0,40}}\b{_VALUES}",
        r"\bclinical(ly)? (significan\w*|meaning|implications?|relevance)\b|\b(mean|matter)s? clinically\b",
        r"\b(something|anything) to (worry|be worried|be concerned) about\b|\bworr(y|ied|ying) about\b|"
        r"\bcause for concern\b|\bunder control\b|\b(good|safe|high|low|well|fit) enough\b|\bdangerous\w*|\balarming\w*|\bhow (bad|serious|severe|worrying)\b",
        # direction-of-change questions are interpretation: "is her Hb dropping?", "has her Hb improved?"
        rf"\b(is|are|was|were|has|have)\b.{{0,30}}\b{_VALUES}\b.{{0,20}}\b(dropping|falling|rising|increasing|"
        r"decreasing|declining|improving|worsening|improved|worsened|deteriorated|dropped|fallen|risen|increased|"
        r"decreased|declined|going (up|down)|gone (up|down)|getting (better|worse)|got (better|worse))\b",
        # value + judgement: "her BP is high", "readings look bad", "within limits", "in range"
        rf"\b{_VALUES}\s+(is|are|was|were|looks?|seems?|appears?|came out)\s+(too |very |quite |a bit )?(normal|"
        r"abnormal|high|low|ok|okay|fine|bad|good|concerning|dangerous|worrying|worse|better|elevated|raised|reduced|"
        r"deranged|borderline|acceptable)\b",
        r"\b(within|outside|out of|in) (the )?(normal |reference |acceptable |safe )?(limits?|range)\b",
        r"\b(bad|harmful|dangerous|safe|good|risky) for (the |her )?(baby|fetus|foetus|mother|pregnancy|delivery)\b",
        r"\bwhat (is|could be) wrong\b", r"\bwhat condition\b",
        # interpretation questions: "is the FHR fine?", "is the baby growing okay?", "is 140/90 a concern?"
        r"\b(is|are|was|were)\b.{0,40}\b(ok|okay|fine|alright|good|bad|concerning|a concern|a problem|worrying|"
        r"serious|adequate|on track|appropriate|reassuring)\s*\??$",
        r"\b(a |any )?(concern|problem|worry)\b.{0,30}\b(pregnan\w*|her|his|baby|bp|hb|weight|values?|results?|"
        r"readings?|count)\b",
        r"\bcould .{0,40}\bbe (a |an )?(problem|concern|issue|sign)\b",
        # value-threshold cohorts = clinical flagging, e.g. "women whose Hb is below 9"
        r"\b(hb|ha?emoglobin|bp|blood pressure|systolic|diastolic|weight|sugar|glucose|platelets?|tsh|fhr|heart rate)\b"
        r".{0,25}\b(below|above|under|over|less than|more than|greater than|lower than|higher than|<|>)\s*\d",
        r"\b(low|high|raised|elevated|reduced|abnormal|poor)\s+(hb|ha?emoglobin|bp|blood pressure|platelets?( count)?|"
        r"sugar|glucose|tsh|weight( gain)?|fhr|heart rate|growth)\b",
        r"\b(does|did|could|might) (she|he|the patient|the mother|the baby|this patient) (have|has)\b"
        r"(?!.*\b(follow[- ]?ups?|appointments?|visits?|reports?|investigations?|tests?|records?|notes?|due|pending)\b)",
    ]],
    "out_of_scope": [re.compile(p, _I) for p in [
        r"\b(weather|joke|poem|song|cricket|football|movie|film|stock|bitcoin|crypto|recipe|horoscope)\b",
        r"\b(write|generate) (code|python|javascript|an essay|a story)\b",
    ]],
}

# Phrases that turn a medication/treatment *word* into a retrieval of documentation.
DOCUMENTATION_FRAMING = re.compile(
    r"\b(documented|recorded|noted|written|charted|as per (the )?(notes?|records?)|in (the|her|his) (notes?|records?)|"
    r"was (given|prescribed|advised)|were (given|prescribed|advised))\b", _I)
SOFT_TREATMENT_WORDS = re.compile(r"\b(medications?|medicines?|drugs?|tablets?|treatments?|supplements?)\b", _I)

# ---- output guard: language an assistive tool must never generate ----------
OUTPUT_PATTERNS: dict[str, list[re.Pattern]] = {
    "diagnostic_language": [re.compile(p, _I) for p in [
        r"\b(is|are) (likely|probably|possibly) (to have|having|suffering)\b",
        r"\b(suggestive|indicative|consistent) (of|with)\b",
        r"\b(suggests|indicates|points to|signs of)\b.{0,40}\b(" + CONDITIONS + r"|risk|problem|complications?)\b",
        r"\bdiagnos(is|ed|e)\b", r"\b(she|he|the patient|the baby) (has|have) (an? )?(" + CONDITIONS + r")\b",
        r"\b(abnormal|within normal limits|normal range|elevated|decreased|deranged)\b",
        # interpretive adjectives applied to measurements ("normal blood pressure", "Hb was low")
        r"\b(normal|healthy|stable|reassuring|concerning|worrying|good|poor|adequate|inadequate|satisfactory|high|low|raised)"
        r"\s+(blood pressure|bp|hb|ha?emoglobin|values?|results?|readings?|growth|weight( gain)?|levels?|sugar|glucose|fhr|heart rate|vitals)\b",
        r"\b(blood pressure|bp|hb|ha?emoglobin|values?|results?|readings?|vitals|levels?)\s+(is|are|was|were|remained|remains)\s+"
        r"(normal|fine|stable|ok|okay|good|satisfactory|high|low|reassuring|within)\b",
        r"\b(improv\w*|worsen\w*|deteriorat\w*)\b",
    ]],
    "treatment_advice": [re.compile(p, _I) for p in [
        r"\b(i|we) (recommend|suggest|advise)\b", r"\b(you|she|he|the patient) should\b",
        r"\bconsider (starting|stopping|prescribing|increasing|decreasing|giving|admitting|referring|inducing)\b",
        r"\b(start|stop|increase|decrease|titrate)\b.{0,30}\b(dose|tablets?|medication|insulin|iron|antibiotics?)\b",
        r"\b(recommended|advisable|indicated) (to|for|that)\b",
    ]],
    "risk_language": [re.compile(p, _I) for p in [
        r"\b(high|increased|elevated|low)[- ]risk\b", r"\bat risk\b", r"\b(likely|unlikely) to (develop|have|need)\b",
        r"\bprognosis\b",
    ]],
}


def find(patterns: dict[str, list[re.Pattern]], text: str) -> list[tuple[str, str]]:
    """Return (category, matched text) for every pattern that fires."""
    hits = []
    for cat, pats in patterns.items():
        for p in pats:
            m = p.search(text)
            if m:
                hits.append((cat, m.group(0)))
    return hits
