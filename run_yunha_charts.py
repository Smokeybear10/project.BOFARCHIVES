"""Build Yunha's three financial × technology investment charts.

Reads master allotments + structured proposals from output/ and produces
three Plotly HTMLs covering total investment by cluster, year-over-year
trajectory, and proposal-volume vs approval-rate ROI.

Usage:
    python run_yunha_charts.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from bof_pipeline.yunha_charts import (
    save_yunha_approval_roi,
    save_yunha_dollars_by_cluster,
    save_yunha_investment_trajectory,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Yunha's three financial × technology investment charts."
    )
    parser.add_argument(
        "--allotments",
        type=Path,
        default=Path("output/master_allotments_1888_1919.csv"),
        help="Path to the master allotments CSV (from run_master_ledger.py).",
    )
    parser.add_argument(
        "--proposals",
        type=Path,
        default=Path("output/all_structured_records.csv"),
        help="Path to the structured proposals CSV (from run_bof_analysis.py).",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output"),
        help="Directory for output HTML files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("Building Yunha's financial × technology charts...")

    allotments = pd.read_csv(args.allotments)
    proposals = pd.read_csv(args.proposals)
    print(f"  Loaded {len(allotments):,} allotments + {len(proposals):,} proposals")

    dollars_path = args.output_dir / "yunha_dollars_by_cluster.html"
    save_yunha_dollars_by_cluster(allotments, dollars_path)
    print(f"  Dollars treemap → {dollars_path}")

    trajectory_path = args.output_dir / "yunha_investment_trajectory.html"
    save_yunha_investment_trajectory(allotments, trajectory_path)
    print(f"  Trajectory      → {trajectory_path}")

    roi_path = args.output_dir / "yunha_approval_roi.html"
    save_yunha_approval_roi(proposals, roi_path)
    print(f"  Approval ROI    → {roi_path}")

    print("Done.")


if __name__ == "__main__":
    main()
