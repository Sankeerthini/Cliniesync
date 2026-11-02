"""LLM text-to-SQL fallback (only when no governed metric matches).

Open-source model via Ollama (default qwen2.5:7b-instruct; qwen2.5-coder:7b is a
good SQL specialist - set LLM_SQL_MODEL). The model only sees the documented
de-identified views; its SQL is validated (ai/sql/validator.py) and executed
on a read-only connection.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import text

from ai.llm.client import LLMUnavailable, get_llm
from ai.sql.validator import validate
from database.session import get_engine, read_only_connection
from database.views import VIEW_DOCS

SYSTEM = """You translate operational questions about a maternal & child health programme into ONE SQLite SELECT query.
Rules:
- Use ONLY these views and columns:
{views}
- Today's date is {today}. Dates are ISO strings; month columns are 'YYYY-MM'.
- Return aggregate, operational numbers (counts, rates, durations). Never select free text.
- No clinical interpretation, no risk scores.
- Respond with JSON: {{"sql": "...", "title": "short chart title", "chart": "bar|line|table"}}"""

EXAMPLES = [
    ("How many PNC visits per month this year?",
     '{"sql": "SELECT visit_month, COUNT(*) AS visits FROM v_visits WHERE visit_category = \'PNC\' AND status = '
     '\'completed\' AND visit_date >= \'2026-01-01\' GROUP BY visit_month ORDER BY visit_month", '
     '"title": "PNC visits per month", "chart": "line"}'),
    ("Which facility has the most pending investigation results?",
     '{"sql": "SELECT facility_name, COUNT(*) AS pending FROM v_investigations WHERE status = \'pending\' '
     'GROUP BY facility_name ORDER BY pending DESC", "title": "Pending results by facility", "chart": "bar"}'),
]


def generate_and_run(question: str, role: str, today: date) -> dict:
    llm = get_llm()
    msgs = [{"role": "system", "content": SYSTEM.format(views=VIEW_DOCS, today=today.isoformat())}]
    for q, a in EXAMPLES:
        msgs += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    msgs.append({"role": "user", "content": question})
    try:
        out = llm.chat_json(msgs, model=llm.s.sql_model, max_tokens=400)
    except LLMUnavailable:
        raise
    except Exception as exc:
        return {"ok": False, "reason": f"model output could not be parsed: {exc}"}
    dialect = "postgres" if get_engine().url.get_backend_name().startswith("postgres") else "sqlite"
    v = validate(out.get("sql", ""), role, dialect)
    if not v.ok:
        return {"ok": False, "reason": v.reason, "sql": out.get("sql")}
    conn = read_only_connection()
    try:
        df = pd.read_sql(text(v.sql), conn)
    except Exception as exc:
        return {"ok": False, "reason": f"query failed: {exc}", "sql": v.sql}
    finally:
        conn.close()
    chart = None
    if out.get("chart") in ("bar", "line") and df.shape[1] >= 2 and len(df) > 1:
        num_cols = [c for c in df.columns[1:] if pd.api.types.is_numeric_dtype(df[c])]
        if num_cols:
            chart = {"id": "llm_sql", "type": out["chart"], "title": out.get("title") or question, "x": df.columns[0],
                     "series": [{"key": num_cols[0], "label": num_cols[0].replace("_", " ")}],
                     "data": df[[df.columns[0], num_cols[0]]].astype(object).to_dict("records"), "value_format": "num"}
    return {"ok": True, "sql": v.sql, "title": out.get("title") or question,
            "table": {"columns": [{"key": c, "label": c.replace("_", " ").capitalize()} for c in df.columns],
                      "rows": df.astype(object).where(pd.notna(df), None).to_dict("records")},
            "chart": chart, "rows": len(df)}
