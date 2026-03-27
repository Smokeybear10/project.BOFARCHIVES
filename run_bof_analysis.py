"""Run BOF 1901-1902 qualitative-to-quantitative pipeline.

Usage:
    python run_bof_analysis.py --input-dir Subject --output-dir output
"""

from __future__ import annotations

import argparse
from pathlib import Path

from bof_pipeline import run_batch_analysis
from bof_pipeline.visualize import (
    save_proposer_success_by_year,
    save_ratio_dashboard_1901,
    save_status_cluster_sankey,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transform BOF non-numerical records into structured analytics outputs."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing CSV/XLSX files (supports 9-file batch runs).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for structured outputs and visualizations.",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="*",
        help="Glob pattern for selecting input files (e.g. '*.xlsx' or '*').",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    globbed_files = sorted(args.input_dir.glob(args.pattern))
    input_files = [
        path
        for path in globbed_files
        if path.suffix.lower() in {".csv", ".xlsx", ".xls"}
    ]

    if not input_files:
        raise SystemExit(f"No files matched pattern {args.pattern!r} in {args.input_dir}")

    all_data = run_batch_analysis(input_files=input_files, output_dir=args.output_dir)

    save_status_cluster_sankey(all_data, args.output_dir / "flow_cluster_to_status.html")
    save_proposer_success_by_year(all_data, args.output_dir / "network_proposer_cluster.html")
    save_ratio_dashboard_1901(all_data, args.output_dir / "dashboard_1901_ratio.html")

    print(f"Processed {len(input_files)} files.")
    print(f"Outputs written to: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
