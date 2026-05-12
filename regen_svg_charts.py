"""Regenerate every dashboard chart as a hand-rolled SVG page.

Replaces the Plotly outputs in output/ with SVG-based versions. Run after
any source data refresh:

    python regen_svg_charts.py

Each chart is a complete, self-contained HTML file with an inline SVG —
no Plotly, no chart-library JS, ~15-30 KB per page instead of ~100 KB+.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

from bof_pipeline.svg_charts import (
    save_pareto_svg,
    save_master_timeline_svg,
    save_historical_events_svg,
    save_yunha_treemap_svg,
    save_yunha_trajectory_svg,
    save_tanisha_stacked_bars_svg,
    save_tanisha_heatmap_svg,
)

ROOT = Path(__file__).parent
OUTPUT = ROOT / "output"


def main() -> None:
    print("Loading data…")
    allotments    = pd.read_csv(OUTPUT / "master_allotments_1888_1919.csv")
    appropriations = pd.read_csv(OUTPUT / "master_appropriations_1888_1919.csv")
    events        = pd.read_csv(OUTPUT / "historical_events_1888_1930.csv")
    print(f"  allotments: {len(allotments)} · appropriations: {len(appropriations)} · events: {len(events)}")

    print("\nGenerating SVG charts…")
    targets = [
        ("master_pareto.html",                lambda p: save_pareto_svg(allotments, p)),
        ("master_timeline.html",              lambda p: save_master_timeline_svg(allotments, appropriations, p)),
        ("historical_events_timeline.html",   lambda p: save_historical_events_svg(events, p)),
        ("yunha_dollars_by_cluster.html",     lambda p: save_yunha_treemap_svg(allotments, p)),
        ("yunha_investment_trajectory.html",  lambda p: save_yunha_trajectory_svg(allotments, p)),
        ("tanisha_stacked_bars.html",         save_tanisha_stacked_bars_svg),
        ("tanisha_heatmap.html",              save_tanisha_heatmap_svg),
    ]
    for name, fn in targets:
        path = OUTPUT / name
        fn(path)
        print(f"  ✓ {name}  ({path.stat().st_size:,} bytes)")

    print("\nDone.")


if __name__ == "__main__":
    main()
