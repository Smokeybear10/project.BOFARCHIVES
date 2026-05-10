"""Build the master 1888-1919 BOF financial ledger.

Concatenates every Completed Spreadsheet, normalizes the schema, dedupes
overlap, and writes two CSVs the dashboard can consume:
  output/master_allotments_1888_1919.csv
  output/master_appropriations_1888_1919.csv

Usage:
    python run_master_ledger.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from bof_pipeline.master_ledger import build_master_ledger
from bof_pipeline.master_visualize import (
    save_attribution_waterfall,
    save_master_timeline,
    save_pareto_top_projects,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the canonical BOF 1888-1919 master ledger from Completed Spreadsheets."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("Data/Appropriations/Completed Spreadsheets"),
        help="Directory containing all completed BOF financial xlsx files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for the output CSVs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Building master ledger from: {args.input_dir}")
    allotments, appropriations = build_master_ledger(args.input_dir)

    allot_path = args.output_dir / "master_allotments_1888_1919.csv"
    allotments.to_csv(allot_path, index=False)
    print(f"  Allotments       → {allot_path}  ({len(allotments)} rows)")
    print(f"    year range:    {int(allotments['year'].min())}–{int(allotments['year'].max())}")
    print(f"    total allotted: ${allotments['allotted'].sum():,.0f}")
    print(f"    revoked count:  {int(allotments['revoked'].fillna(False).sum())}")

    appr_path = args.output_dir / "master_appropriations_1888_1919.csv"
    appropriations.to_csv(appr_path, index=False)
    print(f"  Appropriations   → {appr_path}  ({len(appropriations)} rows)")
    print(f"    year range:    {int(appropriations['year'].min())}–{int(appropriations['year'].max())}")
    print(f"    total approp:  ${appropriations['amount'].sum():,.0f}")

    # ── Legacy-schema CSVs (consumed by app.js Spending view) ──────────────
    # Same data as master_*.csv but with the column names the dashboard parses.
    # Drop these once app.js is rewritten to read master_*.csv directly.
    legacy_allot = allotments.rename(columns={
        "year": "Year",
        "description": "Project/Line Item Description",
        "allotted": "Allotted ($)",
        "date_allotted": "Date Allotted",
        "revoked": "Revoked Allotment?",
        "date_revoked": "Date of Revocation",
        "page": "Page",
        "notes": "Notes",
    }).copy()
    legacy_allot["Revoked Allotment?"] = legacy_allot["Revoked Allotment?"].map({True: "Yes", False: "No"})
    legacy_allot["Allotted_Numeric"] = legacy_allot["Allotted ($)"]
    legacy_allot["stereoscopic"] = ""  # vestigial column from old pipeline
    legacy_allot = legacy_allot[[
        "Year", "Project/Line Item Description", "Allotted ($)", "Date Allotted",
        "Revoked Allotment?", "Date of Revocation", "Page", "Notes",
        "stereoscopic", "Allotted_Numeric",
    ]]
    legacy_allot_path = args.output_dir / "bof_allotments.csv"
    legacy_allot.to_csv(legacy_allot_path, index=False)
    print(f"  Legacy allotments → {legacy_allot_path}  ({len(legacy_allot)} rows)")

    legacy_appr = appropriations.rename(columns={
        "year": "Year",
        "amount": "Amount",
        "remarks": "Remarks",
        "estimate_requested": "Estimate Originally Requested by BOF (Not from the same source, but from the prior year's annual report)",
        "justification": "Justification for Estimate/Request",
        "legislation": "Legislation Making Appropriations for the Board",
        "legislation_url": "Permalink to Legislation/Act",
    }).copy()
    legacy_appr["Amount_Numeric"] = legacy_appr["Amount"]
    legacy_appr_path = args.output_dir / "bof_appropriations.csv"
    legacy_appr.to_csv(legacy_appr_path, index=False)
    print(f"  Legacy approps    → {legacy_appr_path}  ({len(legacy_appr)} rows)")

    # ── Visualizations ────────────────────────────────────────────────────
    print()
    print("Generating visualizations...")

    timeline_path = args.output_dir / "master_timeline.html"
    save_master_timeline(allotments, appropriations, timeline_path)
    print(f"  Timeline        → {timeline_path}")

    waterfall_path = args.output_dir / "master_waterfall.html"
    save_attribution_waterfall(allotments, appropriations, waterfall_path)
    print(f"  Waterfall       → {waterfall_path}")

    pareto_path = args.output_dir / "master_pareto.html"
    save_pareto_top_projects(allotments, pareto_path)
    print(f"  Pareto          → {pareto_path}")

    print("Done.")


if __name__ == "__main__":
    main()
