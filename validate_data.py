"""Data validation pass for the FORTIFY project.

Run from repo root: `python validate_data.py`
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent
OUTPUT = ROOT / "output"
DATA = ROOT / "Data"

PASS, WARN, FAIL = [], [], []

def ok(msg):    PASS.append(msg);    print(f"  [OK]   {msg}")
def warn(msg):  WARN.append(msg);    print(f"  [WARN] {msg}")
def fail(msg):  FAIL.append(msg);    print(f"  [FAIL] {msg}")
def section(t): print(f"\n=== {t} ===")


# ============================================================
# 1. Subjects Considered per-year structured CSVs
# ============================================================
section("Subjects Considered per-year CSVs")

per_year_files = sorted(OUTPUT.glob("Copy of Subjects Considered *_structured.csv"))
year_re = re.compile(r"(\d{4})-(\d{4})")
expected_cols_min = {"BOF Annual Report #", "Subject", "Proposed By", "Action",
                     "status", "primary_cluster", "proposer_type", "year",
                     "is_approved", "is_rejected", "is_investigating"}

year_counts = {}
for f in per_year_files:
    df = pd.read_csv(f)
    m = year_re.search(f.name)
    if not m:
        warn(f"{f.name}: cannot parse year range from filename")
        continue
    start_y = int(m.group(1))
    missing = expected_cols_min - set(df.columns)
    if missing:
        fail(f"{f.name}: missing columns {missing}")
        continue

    # All rows must have the matching year
    yrs = df["year"].dropna().unique()
    if not set(yrs).issubset({start_y}):
        fail(f"{f.name}: year column has {sorted(yrs)} but filename says {start_y}")
    else:
        ok(f"{f.name}: {len(df)} rows, year={start_y}")
    year_counts[start_y] = len(df)

    # Mutually-exclusive booleans (Unknown rows have all four is_* flags = 0
    # in the old schema; the new pipeline adds is_unknown).
    bool_cols = [c for c in ("is_approved", "is_rejected", "is_investigating", "is_unknown") if c in df.columns]
    bool_sum = df[bool_cols].sum(axis=1)
    bad = (bool_sum != 1).sum()
    if bad:
        fail(f"{f.name}: {bad} rows have sum({bool_cols}) != 1")

    # status matches the booleans
    inferred = pd.Series(index=df.index, dtype=object)
    inferred[df["is_approved"] == 1] = "Approved"
    inferred[df["is_rejected"] == 1] = "Rejected"
    inferred[df["is_investigating"] == 1] = "Investigating"
    if "is_unknown" in df.columns:
        inferred[df["is_unknown"] == 1] = "Unknown"
    mismatch = (inferred != df["status"]).sum()
    if mismatch:
        fail(f"{f.name}: {mismatch} rows where status disagrees with is_* flags")

    # proposer_type sanity
    bad_types = set(df["proposer_type"].dropna().unique()) - {"Government", "Private", "Unknown"}
    if bad_types:
        warn(f"{f.name}: unexpected proposer_type values {bad_types}")

    # Years must be 1897-1907 in this corpus
    yr_series = df["year"].dropna()
    if not yr_series.between(1897, 1907).all():
        fail(f"{f.name}: year values outside 1897-1907")
    null_yrs = df["year"].isna().sum()
    if null_yrs:
        warn(f"{f.name}: {null_yrs} rows with null year")

    # No empty Subject
    if df["Subject"].isna().any() or (df["Subject"].astype(str).str.strip() == "").any():
        warn(f"{f.name}: {(df['Subject'].isna() | (df['Subject'].astype(str).str.strip()=='' )).sum()} rows have empty Subject")

# Master file aggregation check
master = pd.read_csv(OUTPUT / "all_structured_records.csv")
ok(f"all_structured_records.csv: {len(master)} rows total")

# Reconciliation: master row count should be near the sum of per-year files
per_year_sum = sum(year_counts.values())
ok(f"sum of per-year row counts (excluding 1902-only file): {per_year_sum}")
if abs(len(master) - per_year_sum) > 1:
    warn(f"master ({len(master)}) and per-year sum ({per_year_sum}) differ by {len(master) - per_year_sum} — check for duplicate-year files")

# Detect duplicate 1901-1902 files (cleaned up — should be exactly one)
candidates = sorted(OUTPUT.glob("Copy of Subjects Considered 1901-1902*_structured.csv"))
candidates = [c for c in candidates if c.suffix == ".csv"]
if len(candidates) > 1:
    fail(f"Multiple 1901-1902 structured CSVs: {[c.name for c in candidates]}")
elif len(candidates) == 1:
    ok(f"Single canonical 1901-1902 file: {candidates[0].name}")


# ============================================================
# 2. Master allotments + appropriations ledgers
# ============================================================
section("Master allotments & appropriations ledgers")

ml = pd.read_csv(OUTPUT / "master_allotments_1888_1919.csv")
ma = pd.read_csv(OUTPUT / "master_appropriations_1888_1919.csv")
print(f"  allotments columns: {list(ml.columns)}")
print(f"  appropriations columns: {list(ma.columns)}")
ok(f"master_allotments_1888_1919.csv: {len(ml)} rows")
ok(f"master_appropriations_1888_1919.csv: {len(ma)} rows")

# year ranges — appropriations extends to 1920 (final $0 stub recording Treasury return)
if "year" in ml.columns:
    ml_yr = ml["year"].dropna()
    if not ml_yr.between(1888, 1920).all():
        fail(f"allotments: year values outside 1888-1920: min={ml_yr.min()}, max={ml_yr.max()}")
    else:
        ok(f"allotments year range: {int(ml_yr.min())}-{int(ml_yr.max())}")

if "year" in ma.columns:
    ma_yr = ma["year"].dropna()
    if not ma_yr.between(1888, 1920).all():
        fail(f"appropriations: year values outside 1888-1920: min={ma_yr.min()}, max={ma_yr.max()}")
    else:
        ok(f"appropriations year range: {int(ma_yr.min())}-{int(ma_yr.max())}")

# Check appropriations are non-negative
for col in ma.columns:
    if col == "year": continue
    if pd.api.types.is_numeric_dtype(ma[col]):
        neg = (ma[col].fillna(0) < 0).sum()
        if neg: warn(f"appropriations: {neg} negative values in '{col}'")

# Compare total allotments per year vs appropriation per year (where comparable)
if "amount" in ml.columns and "year" in ml.columns:
    by_yr = ml.groupby("year")["amount"].sum()
    print(f"  total allotments (sum): ${by_yr.sum():,.0f}")
elif {"Amount", "year"}.issubset(ml.columns):
    by_yr = ml.groupby("year")["Amount"].sum()
    print(f"  total allotments (sum): ${by_yr.sum():,.0f}")

# bof_allotments.csv / bof_appropriations.csv
bof_al = pd.read_csv(OUTPUT / "bof_allotments.csv")
bof_ap = pd.read_csv(OUTPUT / "bof_appropriations.csv")
ok(f"bof_allotments.csv: {len(bof_al)} rows")
ok(f"bof_appropriations.csv: {len(bof_ap)} rows")
print(f"  bof_allotments columns: {list(bof_al.columns)[:10]}")
print(f"  bof_appropriations columns: {list(bof_ap.columns)[:10]}")


# ============================================================
# 3. Historical events timeline
# ============================================================
section("Historical events timeline")

he = pd.read_csv(OUTPUT / "historical_events_1888_1930.csv")
ok(f"historical_events_1888_1930.csv: {len(he)} rows")
print(f"  columns: {list(he.columns)}")

# Each event should have a year inside 1888-1930
if "year" in he.columns:
    he_yr = pd.to_numeric(he["year"], errors="coerce").dropna()
    if not he_yr.between(1888, 1930).all():
        out = he_yr[~he_yr.between(1888, 1930)]
        fail(f"historical events: {len(out)} years outside 1888-1930: {sorted(out.unique())[:10]}")
    else:
        ok(f"historical events year range: {int(he_yr.min())}-{int(he_yr.max())}")
    nulls = he["year"].isna().sum()
    if nulls: warn(f"historical events: {nulls} rows have null year")


# ============================================================
# 4. Team derived datasets
# ============================================================
section("Team-derived datasets")

t1 = pd.read_csv(OUTPUT / "tanisha_technology_prevalence.csv")
ok(f"tanisha_technology_prevalence.csv: {len(t1)} rows, cols={list(t1.columns)}")
t2 = pd.read_csv(OUTPUT / "approval_ratio_by_cluster_1901.csv")
ok(f"approval_ratio_by_cluster_1901.csv: {len(t2)} rows, cols={list(t2.columns)}")
t3 = pd.read_csv(OUTPUT / "proposer_success_rate_by_year.csv")
ok(f"proposer_success_rate_by_year.csv: {len(t3)} rows, cols={list(t3.columns)}")
t4 = pd.read_csv(OUTPUT / "budget_master_ledger.csv")
ok(f"budget_master_ledger.csv: {len(t4)} rows, cols={list(t4.columns)}")

# Ratios must be in [0,1]
for name, df in [("approval_ratio_by_cluster_1901", t2), ("proposer_success_rate_by_year", t3)]:
    ratio_cols = [c for c in df.columns if "ratio" in c.lower() or "rate" in c.lower() or "success" in c.lower()]
    for c in ratio_cols:
        if pd.api.types.is_numeric_dtype(df[c]):
            bad = ((df[c] < 0) | (df[c] > 1)).sum()
            if bad: fail(f"{name}: {bad} '{c}' values outside [0,1]")
            else: ok(f"{name}: '{c}' all in [0,1]")


# ============================================================
# 5. Cross-check README claims
# ============================================================
section("Cross-check README headline numbers")

claims = {"proposals": 1691, "allotments": 1144, "technologies": 202, "years": 33}

actual_proposals = len(master)
if actual_proposals == claims["proposals"]:
    ok(f"README claims 1,691 proposals → master CSV: {actual_proposals}")
else:
    fail(f"README claims 1,691 proposals → master CSV: {actual_proposals}")

# Distinct technologies / subjects
distinct_subjects = master["Subject"].astype(str).str.strip().str.lower().nunique()
print(f"  distinct unique subject strings in master: {distinct_subjects}")

# Years
year_min = int(master["year"].min())
year_max = int(master["year"].max())
print(f"  master year range: {year_min}-{year_max} (proposals span; budget data covers 1888-1920)")

# Allotment count claim
if {"year"}.issubset(ml.columns):
    if len(ml) == claims["allotments"]:
        ok(f"README claims 1,144 allotments → master_allotments: {len(ml)}")
    else:
        fail(f"README claims 1,144 allotments → master_allotments: {len(ml)}")

# Year range of full project (allotments → 1920)
if "year" in ml.columns:
    all_year_min = int(ml["year"].min())
    all_year_max = int(ml["year"].max())
    print(f"  master_allotments year range: {all_year_min}-{all_year_max}")


# ============================================================
# 6. Spot-check timeline-data.js front-end source
# ============================================================
section("timeline-data.js")

tdj = (ROOT / "timeline-data.js").read_text()
# Count technologies (top-level entries)
techs = re.findall(r'"technology"\s*:\s*"([^"]+)"', tdj)
periods = re.findall(r'"period"\s*:\s*"([^"]+)"', tdj)
print(f"  technology entries in timeline-data.js: {len(techs)}")
print(f"  period entries in timeline-data.js:     {len(periods)}")
if techs:
    distinct_techs = len(set(techs))
    print(f"  distinct technologies: {distinct_techs}")
if periods:
    distinct_periods = sorted(set(periods))
    print(f"  distinct periods: {distinct_periods}")


# ============================================================
# Summary
# ============================================================
section("SUMMARY")
print(f"  PASS: {len(PASS)}")
print(f"  WARN: {len(WARN)}")
print(f"  FAIL: {len(FAIL)}")
if WARN:
    print("\nWarnings:")
    for w in WARN: print(f"  - {w}")
if FAIL:
    print("\nFailures:")
    for f_ in FAIL: print(f"  - {f_}")
sys.exit(1 if FAIL else 0)
