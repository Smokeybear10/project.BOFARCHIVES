"""Budget ingestion and aggregation pipeline for Military Budgets, 1865-1920.xlsx."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


# ── Column layout shared by Army and Navy sheets ──────────────────────────────

_SHEET_COLS = [
    "organization",
    "year",
    "appropriation_usd",
    "appropriation_2025_usd",
    "source",
    "notes",
    "links",
]

# Sheets that hold time-series appropriation data (skip "Total War Spending")
_DATA_SHEETS = ("Army", "Navy")


def load_budget_master(filepath: str | Path) -> pd.DataFrame:
    """
    Load and clean all Army/Navy appropriation sheets from the budget workbook.

    Returns a tidy DataFrame with columns:
        organization, year, appropriation_usd, appropriation_2025_usd,
        decade, branch
    """
    filepath = Path(filepath)
    xl = pd.ExcelFile(filepath)
    frames: list[pd.DataFrame] = []

    for sheet in _DATA_SHEETS:
        # Row 0 is a header row (parsed as header=1 gives us data starting at row 2)
        df = xl.parse(sheet, header=1)

        # Rename to standard schema regardless of actual header text
        if len(df.columns) >= 4:
            df = df.iloc[:, :7]
            df.columns = _SHEET_COLS[: len(df.columns)]
            # Pad missing columns
            for col in _SHEET_COLS:
                if col not in df.columns:
                    df[col] = pd.NA
        else:
            raise ValueError(f"Sheet '{sheet}' has unexpected structure: {list(df.columns)}")

        # Forward-fill organization name (some cells are blank in multi-row entries)
        df["organization"] = df["organization"].ffill()

        # Cast numeric columns — strip stray string characters first
        for col in ("year", "appropriation_usd", "appropriation_2025_usd"):
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(r"[\$,\s]", "", regex=True)
                .replace({"nan": pd.NA, "": pd.NA})
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["year", "appropriation_usd"])
        df["year"] = df["year"].astype(int)

        # Add derived columns
        df["branch"] = sheet  # "Army" or "Navy"
        df["decade"] = (df["year"] // 10 * 10).astype(str) + "s"

        frames.append(df[["organization", "branch", "year", "decade",
                           "appropriation_usd", "appropriation_2025_usd"]])

    master = pd.concat(frames, ignore_index=True).sort_values(["year", "branch"])
    return master


def aggregate_by_year(df: pd.DataFrame) -> pd.DataFrame:
    """Total appropriations per year across all branches."""
    return (
        df.groupby("year")
        .agg(
            total_usd=("appropriation_usd", "sum"),
            total_2025_usd=("appropriation_2025_usd", "sum"),
        )
        .reset_index()
    )


def aggregate_by_decade_branch(df: pd.DataFrame) -> pd.DataFrame:
    """Total appropriations per decade × branch, for treemap."""
    return (
        df.groupby(["decade", "branch"])
        .agg(
            total_usd=("appropriation_usd", "sum"),
            total_2025_usd=("appropriation_2025_usd", "sum"),
        )
        .reset_index()
    )
