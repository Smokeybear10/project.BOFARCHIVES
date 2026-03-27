"""Run combined BOF + budget visualizations for 1897-1908.

Usage:
    python run_combined_analysis.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from bof_pipeline import run_batch_analysis
from bof_pipeline.budget import load_budget_master
from bof_pipeline.combined_visualize import (
    save_investment_by_technology,
    save_technology_prevalence,
    save_technology_timeline,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate combined subjects + budget visualizations for 1897-1908."
    )
    parser.add_argument(
        "--input-dir", type=Path, default=Path("Subject"),
        help="Directory containing BOF Excel files.",
    )
    parser.add_argument(
        "--budget", type=Path, default=Path("Military Budgets, 1865-1920.xlsx"),
        help="Path to the budget Excel workbook.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output"),
        help="Directory for HTML outputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    input_files = sorted(
        p for p in args.input_dir.glob("*")
        if p.suffix.lower() in {".csv", ".xlsx", ".xls"}
    )
    if not input_files:
        raise SystemExit(f"No files found in {args.input_dir}")

    print("Loading proposal data...")
    proposals = run_batch_analysis(input_files=input_files, output_dir=args.output_dir)

    print("Loading budget data...")
    budget = load_budget_master(args.budget)

    out = args.output_dir

    path = out / "investment_by_technology.html"
    save_investment_by_technology(proposals, budget, path)
    print(f"  Investment chart    -> {path}")

    path = out / "technology_timeline.html"
    save_technology_timeline(proposals, path)
    print(f"  Technology timeline -> {path}")

    path = out / "technology_prevalence.html"
    save_technology_prevalence(proposals, path)
    print(f"  Prevalence chart   -> {path}")

    print("Done.")


if __name__ == "__main__":
    main()
