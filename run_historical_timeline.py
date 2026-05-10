"""Build the BOF Historical Events Timeline (1888-1930).

Reads the master 885-event timeline xlsx from the data repo, normalizes it
into a clean CSV, and produces a stacked annual-bar visualization.

Usage:
    python run_historical_timeline.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from bof_pipeline.historical_timeline import (
    load_historical_events,
    save_historical_events_chart,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the BOF historical events timeline visualization."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("Data/BOF Timeline Assignment/Timeline_updated_for_RAs.xlsx"),
        help="Path to the master timeline xlsx.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for the output CSV + HTML.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading timeline events from: {args.input}")
    events = load_historical_events(args.input)
    print(f"  {len(events)} events  ·  {events['year'].min()}–{events['year'].max()}")
    print(f"  category mix:")
    for cat, n in events["category"].value_counts().items():
        print(f"    {cat:20s} {n:4d}")

    csv_path = args.output_dir / "historical_events_1888_1930.csv"
    events.to_csv(csv_path, index=False)
    print(f"  Events CSV  → {csv_path}")

    chart_path = args.output_dir / "historical_events_timeline.html"
    save_historical_events_chart(events, chart_path)
    print(f"  Timeline    → {chart_path}")

    print("Done.")


if __name__ == "__main__":
    main()
