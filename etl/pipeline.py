"""ETL orchestrator: Extract -> Clean/Normalize/Link -> Follow-ups -> Load -> Index -> Quality report.

    python -m etl.pipeline                 # full run
    python -m etl.pipeline --skip-index    # SQL only
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime

import pandas as pd

from common.settings import get_settings
from database.models import EtlRun
from database.session import session_scope
from etl.extract import extract_all
from etl.followups import build_followups
from etl.load import load
from etl.transform import Transformer


def run(skip_index: bool = False) -> dict:
    s = get_settings()
    ref = s.reference_date
    t0 = time.time()
    timings = {}

    st = extract_all(s.raw_dir)
    timings["extract_s"] = round(time.time() - t0, 2)

    t1 = time.time()
    tr = Transformer(st, ref)
    frames = tr.run()
    fu, fu_report = build_followups(tr, st.get("appointments"), ref)
    frames["followups"] = fu
    frames["facilities"] = pd.read_csv(s.raw_dir / "facilities.csv", dtype=str)
    frames["providers"] = pd.read_csv(s.raw_dir / "providers.csv", dtype=str)
    timings["transform_s"] = round(time.time() - t1, 2)

    t2 = time.time()
    load_report = load(frames)
    timings["load_s"] = round(time.time() - t2, 2)

    index_report = {"skipped": True}
    if not skip_index:
        t3 = time.time()
        from ai.rag.indexer import rebuild_index

        index_report = rebuild_index()
        timings["index_s"] = round(time.time() - t3, 2)

    quarantine = tr.q.rows
    s.processed_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(quarantine).to_json(s.processed_dir / "quarantine.json", orient="records", indent=1)
    report = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "reference_date": ref.isoformat(),
        "sources": st.source_stats,
        "steps": tr.report["steps"],
        "followups": fu_report,
        "quarantine": {"total": len(quarantine), "by_reason": tr.q.summary(),
                       "examples": quarantine[:8]},
        "load": load_report,
        "index": index_report,
        "timings": timings,
    }
    (s.processed_dir / "quality_report.json").write_text(json.dumps(report, indent=2, default=str))
    with session_scope() as sess:
        sess.add(EtlRun(at=datetime.now(), report=json.loads(json.dumps(report, default=str))))
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the ClinieSync ETL pipeline")
    ap.add_argument("--skip-index", action="store_true")
    args = ap.parse_args()
    report = run(skip_index=args.skip_index)
    print(json.dumps({k: report[k] for k in ("steps", "followups", "load", "index", "timings")}, indent=2, default=str))
    print("\nQuarantined:", report["quarantine"]["total"], report["quarantine"]["by_reason"])


if __name__ == "__main__":
    main()
