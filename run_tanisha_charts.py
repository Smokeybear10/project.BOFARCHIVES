"""Build Tanisha's three Technology Type Prevalence charts.

Original analysis + R/ggplot2 source: team/tanisha/technology_prevalence.R
This entry script generates the Plotly dashboard versions.

Usage:
    python run_tanisha_charts.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from bof_pipeline.tanisha_charts import (
    save_tanisha_heatmap,
    save_tanisha_ranking,
    save_tanisha_stacked_bars,
    write_tanisha_data_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Tanisha's three technology-prevalence charts."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for output HTML + CSV.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("Building Tanisha's technology-prevalence charts...")

    csv_path = args.output_dir / "tanisha_technology_prevalence.csv"
    write_tanisha_data_csv(csv_path)
    print(f"  Data CSV    → {csv_path}")

    stacked_path = args.output_dir / "tanisha_stacked_bars.html"
    save_tanisha_stacked_bars(stacked_path)
    print(f"  Stacked bar → {stacked_path}")

    heatmap_path = args.output_dir / "tanisha_heatmap.html"
    save_tanisha_heatmap(heatmap_path)
    print(f"  Heatmap     → {heatmap_path}")

    ranking_path = args.output_dir / "tanisha_ranking.html"
    save_tanisha_ranking(ranking_path)
    print(f"  Ranking     → {ranking_path}")

    print("Done.")


if __name__ == "__main__":
    main()
