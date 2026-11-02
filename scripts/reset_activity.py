"""Clear demo activity (what users did in the portal) without touching the clinical data or the users.

    .venv/bin/python scripts/reset_activity.py --dry-run     # only show what would be deleted
    .venv/bin/python scripts/reset_activity.py               # reviews: AI answers + their feedback + shared reports
    .venv/bin/python scripts/reset_activity.py --all         # everything users did: also reminders/outbox, contact logs,
                                                             # status overrides, time-motion timings, audit trail
Add --yes to skip the confirmation prompt. Works with SQLite and PostgreSQL (uses DATABASE_URL).
Demo use only: in a real deployment the audit trail must never be deleted.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, select, update  # noqa: E402

from common.settings import get_settings  # noqa: E402
from database import models as M  # noqa: E402
from database.session import session_scope  # noqa: E402

REVIEW_MODELS = [M.AIResponse, M.Feedback, M.Report]
ALL_MODELS = REVIEW_MODELS + [M.OutboxMessage, M.ContactEvent, M.BaselineTiming, M.AuditLog]
WAS = re.compile(r"was '([a-z_]+)'\)$")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="clear all portal activity, not only reviews")
    ap.add_argument("--dry-run", action="store_true", help="show counts, change nothing")
    ap.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    a = ap.parse_args()
    models = ALL_MODELS if a.all else REVIEW_MODELS

    with session_scope() as s:
        counts = {m.__tablename__: s.scalar(select(func.count()).select_from(m)) for m in models}
        if a.all:
            counts["followups (workflow state reset)"] = s.scalar(select(func.count()).select_from(M.FollowUp).where(
                (M.FollowUp.workflow_state != "none") | M.FollowUp.override_reason.is_not(None)))
            counts["report rows in outbox"] = 0
        else:
            counts["report rows in outbox"] = s.scalar(select(func.count()).select_from(M.OutboxMessage)
                                                       .where(M.OutboxMessage.kind == "report"))
        print(f"Database: {get_settings().database_url}")
        for k, v in counts.items():
            print(f"  {k:<36} {v}")
        if a.dry_run or not any(counts.values()):
            print("Nothing changed." if a.dry_run else "Already empty.")
            return
        if not a.yes and input("Delete these rows? [y/N] ").strip().lower() != "y":
            print("Cancelled.")
            return

        if a.all:
            for f in s.scalars(select(M.FollowUp).where(M.FollowUp.override_reason.is_not(None))):
                if m := WAS.search(f.override_reason):   # restore the status derived from the records
                    f.status = m.group(1)
            s.execute(update(M.FollowUp).values(workflow_state="none", contact_attempts=0, last_contact_on=None,
                                                first_contact_on=None, assigned_to=None, override_reason=None))
        else:
            s.execute(delete(M.OutboxMessage).where(M.OutboxMessage.kind == "report"))
        for m in models:
            s.execute(delete(m))

    if a.all and get_settings().outbox_dir.exists():   # sandbox copies of "sent" messages
        shutil.rmtree(get_settings().outbox_dir)
        get_settings().outbox_dir.mkdir(parents=True)
    print("Done. Refresh the browser (no restart needed).")


if __name__ == "__main__":
    main()
