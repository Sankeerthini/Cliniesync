"""CLI: generate the synthetic clinic sources.

    python -m data_generator.run --mothers 600 --seed 42
    python -m data_generator.run --reference-date 2026-10-19   # freeze 'today'
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import date

from common.settings import get_settings
from data_generator.simulate import simulate
from data_generator.writers import write_all


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate synthetic MCH clinic data for ClinieSync")
    ap.add_argument("--mothers", type=int, default=600)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--reference-date", type=str, default=None, help="YYYY-MM-DD (defaults to settings/today)")
    args = ap.parse_args()

    s = get_settings()
    ref = date.fromisoformat(args.reference_date) if args.reference_date else s.reference_date
    if s.raw_dir.exists():
        shutil.rmtree(s.raw_dir)
    s.raw_dir.mkdir(parents=True)
    cohort = simulate(args.mothers, args.seed, ref)
    manifest = write_all(cohort, s.raw_dir)
    print(json.dumps(manifest, indent=2))
    print(f"\nSynthetic sources written to {s.raw_dir}")


if __name__ == "__main__":
    main()
