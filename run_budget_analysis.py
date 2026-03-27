"""Run BOF military budget analysis pipeline.

Usage:
    python run_budget_analysis.py --input "Military Budgets, 1865-1920.xlsx" --output-dir output
"""

from __future__ import annotations

import argparse
from pathlib import Path

from bof_pipeline.budget import load_budget_master
from bof_pipeline.budget_visualize import (
    save_budget_area_chart,
    save_budget_share_chart,
    save_budget_treemap,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate visualizations from the BOF military budget workbook."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("Military Budgets, 1865-1920.xlsx"),
        help="Path to the budget Excel workbook.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for HTML visualization outputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading budget data from: {args.input}")
    df = load_budget_master(args.input)
    print(f"  {len(df)} rows loaded — years {df['year'].min()}–{df['year'].max()}")

    # Export master ledger CSV
    csv_path = args.output_dir / "budget_master_ledger.csv"
    df.to_csv(csv_path, index=False)
    print(f"  Master ledger → {csv_path}")

    # Generate visualizations
    out = args.output_dir

    path = out / "budget_area_chart.html"
    save_budget_area_chart(df, path)
    print(f"  Stacked area chart → {path}")

    path = out / "budget_treemap.html"
    save_budget_treemap(df, path)
    print(f"  Treemap            → {path}")

    path = out / "budget_share_chart.html"
    save_budget_share_chart(df, path)
    print(f"  Share area chart   → {path}")

    print("Done.")


if __name__ == "__main__":
    main()
