"""Test configuration: run the API against a temporary copy of the synthetic database, LLM disabled."""
import os
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_src = ROOT / "data" / "cliniesync.db"
_tmp = Path(tempfile.mkdtemp(prefix="cliniesync-test-"))
if _src.exists():
    shutil.copy(_src, _tmp / "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp / 'test.db'}"
os.environ.setdefault("REFERENCE_DATE", "2026-10-19")
os.environ["LLM_ENABLED"] = "false"
os.environ["DELIVERY_MODE"] = "sandbox"
