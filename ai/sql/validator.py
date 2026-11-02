"""SQL safety validator for LLM-generated queries (defence in depth).

1. parse with sqlglot - must be exactly ONE read-only SELECT
2. only the de-identified analytics views may be referenced
3. no dangerous functions; no comments/stacked statements
4. LIMIT enforced (<= 500)
5. administrators: aggregate-only (no row-level patient keys)
The query then runs on a read-only connection (PRAGMA query_only / READ ONLY txn).
"""
from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from database.views import ANALYTICS_VIEWS

ALLOWED_TABLES = set(ANALYTICS_VIEWS)
FORBIDDEN_FUNCS = {"load_extension", "readfile", "writefile", "pg_sleep", "sleep", "pg_read_file", "lo_import",
                   "dblink", "copy", "randomblob", "zeroblob"}
MAX_LIMIT = 500


@dataclass
class ValidationResult:
    ok: bool
    sql: str
    reason: str = ""


def validate(sql: str, role: str, dialect: str = "sqlite") -> ValidationResult:
    if "--" in sql or "/*" in sql:
        return ValidationResult(False, sql, "comments are not allowed")
    try:
        statements = sqlglot.parse(sql, read=dialect)
    except Exception as exc:
        return ValidationResult(False, sql, f"unparseable SQL: {exc}")
    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        return ValidationResult(False, sql, "exactly one statement is allowed")
    tree = statements[0]
    if not isinstance(tree, exp.Select):
        return ValidationResult(False, sql, "only SELECT statements are allowed")
    for bad in (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Command, exp.Alter):
        if tree.find(bad):
            return ValidationResult(False, sql, f"{bad.__name__} is not allowed")
    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    tables = {t.name.lower() for t in tree.find_all(exp.Table)} - cte_names
    illegal = tables - ALLOWED_TABLES
    if illegal:
        return ValidationResult(False, sql, f"tables not allowed: {', '.join(sorted(illegal))}")
    for f in tree.find_all(exp.Func):
        name = (f.sql_name() if hasattr(f, "sql_name") else type(f).__name__).lower()
        if name in FORBIDDEN_FUNCS or (isinstance(f, exp.Anonymous) and f.name.lower() in FORBIDDEN_FUNCS):
            return ValidationResult(False, sql, f"function not allowed: {name}")
    if role == "admin":
        has_agg = any(True for _ in tree.find_all(exp.AggFunc)) or tree.args.get("group")
        if not has_agg:
            return ValidationResult(False, sql, "administrators may run aggregate queries only")
        for col in tree.find_all(exp.Column):
            if col.name.lower() in ("patient_key", "child_key") and not col.find_ancestor(exp.AggFunc):
                return ValidationResult(False, sql, "row-level patient keys are not available to administrators")
    limit = tree.args.get("limit")
    if limit is None:
        tree = tree.limit(MAX_LIMIT)
    else:
        try:
            if int(limit.expression.name) > MAX_LIMIT:
                tree = tree.limit(MAX_LIMIT)
        except Exception:
            tree = tree.limit(MAX_LIMIT)
    return ValidationResult(True, tree.sql(dialect=dialect))
