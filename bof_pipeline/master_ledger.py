"""Build the master 1888-1919 BOF financial ledger.

Reads every xlsx in `Data/Appropriations/Completed Spreadsheets/`, normalizes
the schema, deduplicates overlapping line items across files, and writes two
canonical CSVs: master_allotments_1888_1919.csv (line-item allotments) and
master_appropriations_1888_1919.csv (annual congressional appropriations).
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pandas as pd

ALLOTMENTS_SHEET = "Allotments and Expenditures"
APPROPRIATIONS_SHEET = "Statement of Appropriations Mad"

ALLOTMENT_COLS = [
    "Year",
    "Project/Line Item Description",
    "Allotted ($)",
    "Date Allotted",
    "Revoked Allotment?",
    "Date of Revocation",
    "Page",
    "Notes",
]


def _normalize_year_column(df: pd.DataFrame) -> pd.DataFrame:
    """Some files have a typo'd first column ('stereoscopic', 'Column 1').
    If column 0 isn't named 'Year' but its values look like fiscal years,
    rename it.
    """
    if df.columns[0] == "Year":
        return df
    sample = pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna()
    if len(sample) and sample.between(1880, 1925).mean() > 0.8:
        df = df.rename(columns={df.columns[0]: "Year"})
    return df


def _coerce_date(value: object) -> str | None:
    """Excel stores dates inconsistently (datetime, '11/17/1897', '1907-06-06 00:00:00').
    Return ISO YYYY-MM-DD or None.
    """
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return pd.to_datetime(s, format=fmt).date().isoformat()
        except (ValueError, TypeError):
            continue
    try:
        return pd.to_datetime(s, errors="raise").date().isoformat()
    except (ValueError, TypeError):
        return None


_AMOUNT_RE = re.compile(r"[^\d.\-]")


def _coerce_amount(value: object) -> float | None:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = _AMOUNT_RE.sub("", str(value))
    if cleaned in {"", "-", "."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _coerce_revoked(value: object) -> bool | None:
    if pd.isna(value):
        return None
    s = str(value).strip().lower()
    if s in {"yes", "y", "true", "1"}:
        return True
    if s in {"no", "n", "false", "0"}:
        return False
    return None


def _read_allotments(path: Path) -> pd.DataFrame:
    """Read one xlsx's allotments sheet, normalize to canonical schema."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = pd.read_excel(path, sheet_name=ALLOTMENTS_SHEET)

    df = _normalize_year_column(df)
    df = df.dropna(how="all")

    if "Year" not in df.columns:
        return pd.DataFrame(columns=ALLOTMENT_COLS + ["source_file"])

    out = pd.DataFrame()
    out["year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")
    out["description"] = df["Project/Line Item Description"].astype(str).str.strip()
    out["allotted"] = df["Allotted ($)"].apply(_coerce_amount)
    out["date_allotted"] = df["Date Allotted"].apply(_coerce_date)
    out["revoked"] = df["Revoked Allotment?"].apply(_coerce_revoked)
    out["date_revoked"] = df["Date of Revocation"].apply(_coerce_date)
    out["page"] = pd.to_numeric(df["Page"], errors="coerce").astype("Int64")
    out["notes"] = df["Notes"].astype(str).where(df["Notes"].notna(), None)
    out["source_file"] = path.name

    out = out[
        out["year"].notna()
        & out["description"].notna()
        & (out["description"] != "nan")
        & (out["description"].str.len() > 0)
    ]
    return out.reset_index(drop=True)


def _read_appropriations(path: Path) -> pd.DataFrame:
    """The 'Statement of Appropriations' sheet is identical across all files
    (sourced from the 1920 Annual Report). Read once.

    The sheet has unnamed columns and a header in row 1. Promote that header.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = pd.read_excel(path, sheet_name=APPROPRIATIONS_SHEET, header=None)

    header_row_idx = next(
        (i for i, row in df.iterrows() if str(row[0]).strip().lower() == "year"),
        None,
    )
    if header_row_idx is None:
        return pd.DataFrame()

    header = [str(c).strip() for c in df.iloc[header_row_idx]]
    body = df.iloc[header_row_idx + 1 :].copy()
    body.columns = header

    out = pd.DataFrame()
    out["year"] = pd.to_numeric(body["Year"], errors="coerce").astype("Int64")
    out["amount"] = body["Amount"].apply(_coerce_amount)
    out["remarks"] = body.get("Remarks")
    out["estimate_requested"] = body.get(
        "Estimate Originally Requested by BOF (Not from the same source, but from the prior year's annual report)"
    )
    out["justification"] = body.get("Justification for Estimate/Request")
    out["legislation"] = body.get("Legislation Making Appropriations for the Board")
    out["legislation_url"] = body.get("Permalink to Legislation/Act")

    return out[out["year"].notna()].reset_index(drop=True)


def build_master_ledger(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Concatenate all completed spreadsheets, dedupe, return (allotments, appropriations)."""
    files = sorted(input_dir.glob("*.xlsx"))
    if not files:
        raise SystemExit(f"No xlsx files found in {input_dir}")

    allot_frames = []
    for path in files:
        try:
            frame = _read_allotments(path)
            if len(frame):
                allot_frames.append(frame)
        except Exception as e:
            print(f"  WARN  {path.name}: {e}")

    allotments = pd.concat(allot_frames, ignore_index=True)

    # Dedupe across overlapping annual reports.
    # Same allotment shouldn't legitimately appear in two source files, but
    # researchers transcribed from different documents — same line-item with
    # same year + description + amount + date is the same row.
    before = len(allotments)
    allotments = allotments.drop_duplicates(
        subset=["year", "description", "allotted", "date_allotted"],
        keep="first",
    ).reset_index(drop=True)
    print(f"  Dedup: {before} → {len(allotments)} allotments")

    # Appropriations sheet is identical across files; read once.
    appropriations = _read_appropriations(files[0])

    return allotments, appropriations


__all__ = ["build_master_ledger"]
