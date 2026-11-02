"""Patient summaries: deterministic (template) + LLM (grounded, cited) paths.

The deterministic summary is built directly from records, never interprets a
value, and cites every statement - it is the safe fallback for the LLM path
and also what runs when no model is available.
"""
from __future__ import annotations

from datetime import date

from ai.llm.client import LLMUnavailable, get_llm
from ai.rag.retriever import Evidence, fmt_d

LANG_NAMES = {"en": "English", "hi": "Hindi", "bn": "Bengali", "kn": "Kannada"}

SUMMARY_SYSTEM = """You are ClinieSync's documentation assistant for a maternal & child health clinic.
You ONLY restate facts that appear in the EVIDENCE list. Hard rules:
- Write 4-8 short bullet points (max 170 words).
- End every bullet with the evidence id(s) it uses, e.g. [S3] or [S3][S7] (at most 4 per bullet).
- Each number in a bullet must come from the evidence item(s) cited on that bullet. Never move a value from one
  event to another (e.g. a postnatal weight is not a birth weight).
- Copy numbers and dates exactly as written in the evidence.
- Never interpret values or trends: do not use words like normal, abnormal, high, low, stable, good, increasing,
  improving, concerning, risk. Report the documented value only.
- Never suggest diagnoses, causes, treatments, medicines, referrals or next clinical steps.
- Operational facts (overdue follow-ups, pending results, no-shows) may be stated as documented.
- Use the evidence wording; do not add descriptions that are not written in the evidence.
- Example of the required bullet format:
  - ANC2 on 06 Sep 2026 at 32.6 weeks: weight 60.4 kg and BP 132/62 mmHg recorded [S4]
- If something asked is not in the evidence, write: "Not documented in the available records."
"""

QA_SYSTEM = SUMMARY_SYSTEM.replace("Write 4-8 short bullet points (max 170 words).",
                                   "Answer the QUESTION in 1-5 short bullet points (max 120 words).")


def _cite(*ids) -> str:
    return "".join(f"[{i}]" for i in ids if i)


def deterministic_summary(ev: Evidence, scopes: set[str], ref: date) -> str:
    p = ev.patient
    lines = [f"**{p.full_name}** ({p.patient_id}) · {p.age_years} y · prefers {LANG_NAMES.get(p.preferred_language, p.preferred_language)}"
             f" · {ev.facility_names.get(p.facility_id)} {_cite(ev.find('patient', p.patient_id))}"]
    pr = ev.pregnancies[-1] if ev.pregnancies else None
    if pr:
        s_pr = ev.find("pregnancy", pr.pregnancy_id)
        line = (f"- **Pregnancy:** G{pr.gravida}P{pr.parity}; LMP {fmt_d(pr.lmp)}; EDD {fmt_d(pr.edd)}; registered "
                f"{fmt_d(pr.registration_date)} at {pr.registration_ga_weeks} weeks")
        if pr.status == "antenatal" and pr.lmp:
            line += f"; gestational age today by LMP ≈ {(ref - pr.lmp).days / 7:.1f} weeks (calculated)"
        lines.append(line + f". {_cite(s_pr)}")
        anc = [v for v in ev.visits if v.visit_category == "ANC" and v.pregnancy_id == pr.pregnancy_id]
        done = [v for v in anc if v.status == "completed"]
        ns = [v for v in anc if v.status == "no_show"]
        if done:
            lst = "; ".join(f"{v.visit_type} {fmt_d(v.visit_date)}" + (f" ({v.ga_weeks} w)" if v.ga_weeks else "") for v in done)
            lines.append(f"- **Antenatal contacts:** {len(done)} documented - {lst}. "
                         f"{_cite(*[ev.find('visit', v.visit_id) for v in done])}")
        if ns:
            lines.append(f"- **No-shows documented:** {len(ns)} ({', '.join(fmt_d(v.visit_date) for v in ns)}). "
                         f"{_cite(*[ev.find('visit', v.visit_id) for v in ns])}")
        if "clinical_values" in scopes and done:
            last = done[-1]
            obs = ev.observations.get(last.visit_id, [])
            by = {o.code: o for o in obs}
            vals = []
            if "weight" in by:
                vals.append(f"weight {by['weight'].value_num:g} kg")
            if "bp_systolic" in by and "bp_diastolic" in by:
                vals.append(f"BP {by['bp_systolic'].value_num:g}/{by['bp_diastolic'].value_num:g} mmHg")
            if vals:
                lines.append(f"- **Values recorded at the latest ANC contact** ({fmt_d(last.visit_date)}, as documented): "
                             f"{', '.join(vals)}. {_cite(ev.find('visit', last.visit_id))}")
            hb = [(v, o) for v in done for o in ev.observations.get(v.visit_id, []) if o.code == "hemoglobin"]
            if hb:
                hb_txt = "; ".join(f"{o.value_num:g} g/dL ({fmt_d(o.observed_on)})" for _, o in hb)
                lines.append(f"- **Haemoglobin as recorded:** {hb_txt}. {_cite(*[ev.find('visit', v.visit_id) for v, _ in hb])}")
        if pr.delivery_date:
            kid = next((c for c in ev.children if c.pregnancy_id == pr.pregnancy_id), None)
            line = f"- **Delivery:** {fmt_d(pr.delivery_date)}" + (f" - {pr.delivery_mode} (as documented)" if pr.delivery_mode else "")
            if kid:
                line += f"; {kid.sex.lower() if kid.sex else ''} baby, birth weight {kid.birth_weight_g} g"
            lines.append(line + f". {_cite(s_pr, ev.find('child', kid.child_id) if kid else None)}")
            pnc = [v for v in ev.visits if v.visit_category == "PNC" and v.status == "completed"]
            if pnc:
                lines.append(f"- **Postnatal contacts:** {', '.join(f'{v.visit_type} {fmt_d(v.visit_date)}' for v in pnc)}. "
                             f"{_cite(*[ev.find('visit', v.visit_id) for v in pnc])}")
    if ev.immunizations:
        seen = {}
        for im in ev.immunizations:
            seen.setdefault(im.schedule_label, im)
        parts = [f"{lab} {'✓ ' + fmt_d(im.given_on) if im.given_on else '- not documented (due ' + fmt_d(im.due_on) + ')'}"
                 for lab, im in seen.items()]
        lines.append(f"- **Child immunization sessions:** {'; '.join(parts)}. "
                     f"{_cite(*[ev.find('immunization', im.imm_id) for im in seen.values()])}")
    inv = ev.investigations
    if inv:
        pending = [i for i in inv if i.status == "pending"]
        line = f"- **Investigations:** {len(inv)} ordered, {len(inv) - len(pending)} with a documented result"
        if pending:
            line += "; awaiting result: " + ", ".join(f"{i.test_name} (ordered {fmt_d(i.ordered_on)})" for i in pending)
        lines.append(line + f". {_cite(*[ev.find('investigation', i.investigation_id) for i in (pending or inv[-2:])])}")
    open_fu = [f for f in ev.followups if f.status in ("due", "overdue", "missed", "upcoming")]
    if open_fu:
        def desc(f):
            if f.status in ("overdue", "missed"):
                return f"{f.followup_type} due {fmt_d(f.due_on)} - {f.status}, {(ref - f.due_on).days} days past due"
            return f"{f.followup_type} due {fmt_d(f.due_on)} - {f.status}"
        lines.append(f"- **Open follow-ups:** " + "; ".join(desc(f) for f in open_fu[-4:]) +
                     f". {_cite(*[ev.find('followup', f.followup_id) for f in open_fu[-4:]])}")
    past_due = [f for f in ev.followups if f.due_on <= ref and f.status != "cancelled"]
    if past_due:
        lines.append(f"- **Follow-up history:** {sum(f.status == 'completed' for f in past_due)} of {len(past_due)} "
                     "documented follow-ups due so far were completed.")
    return "\n".join(lines)


def llm_answer(ev: Evidence, question: str, mode: str = "summary") -> str:
    """Raises LLMUnavailable when no model is reachable."""
    llm = get_llm()
    system = SUMMARY_SYSTEM if mode == "summary" else QA_SYSTEM
    msgs = [{"role": "system", "content": system},
            {"role": "user", "content": f"QUESTION: {question}\n\nEVIDENCE:\n{ev.blob()}"}]
    return llm.chat(msgs, max_tokens=500)


__all__ = ["deterministic_summary", "llm_answer", "LLMUnavailable", "LANG_NAMES"]
