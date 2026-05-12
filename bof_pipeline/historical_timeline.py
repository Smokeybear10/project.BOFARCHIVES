"""BOF Historical Events Timeline · 1888-1930.

Reads the 885-event master timeline (Timeline_updated_for_RAs.xlsx),
groups granular Event Type values into broad categories, and produces a
stacked annual-bar visualization showing the rhythm of legislation,
personnel, technology evaluation, and organizational change across the
Board's full lifespan.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

# Match the paper-theme tokens used elsewhere
_PLOT_BG = "#EAE3D8"
_GRID = "#D6CEBF"
_TEXT_DARK = "#1A1A2E"
_TEXT_MID = "#55556A"
_SERIF = "Georgia, 'Times New Roman', serif"
_SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif"

# Brand-aligned categorical palette
_CATEGORY_COLORS = {
    "Legislation":        "#1F3A5F",  # federal navy
    "Organizational":     "#6B89A8",  # steel
    "Personnel":          "#9F8B6B",  # warm taupe
    "Technology":         "#C9A24C",  # brass (the brand color)
    "Machine Gun":        "#A8852E",  # darker brass
    "Airplane":           "#5B7B95",  # dimmer steel
    "Other":              "#8C8273",  # neutral
}

_CATEGORY_ORDER = [
    "Legislation",
    "Organizational",
    "Personnel",
    "Technology",
    "Machine Gun",
    "Airplane",
    "Other",
]


# ── Loading ───────────────────────────────────────────────────────────


_YEAR_RE = re.compile(r"\b(18[89]\d|19[0-3]\d)\b")


def _coerce_year(end_date: object, only_year: object, description: object = None) -> int | None:
    """Extract a 4-digit year (1880-1939) from any of three sources, in
    priority order: End Date, Only Year Available, Event Description.

    The description fallback recovers ~half of the rows where the RA
    didn't fill in the date columns but cited a year inline (e.g.
    'Act of 1891' or 'appointed in 1894').
    """
    for value in (end_date, only_year, description):
        if value is None or pd.isna(value):
            continue
        s = str(value).strip()
        if not s:
            continue
        match = _YEAR_RE.search(s)
        if match:
            return int(match.group(1))
    return None


def _bucket_event_type(raw: object) -> str:
    """Group granular event types into the 7 broad categories.

    Source data has labels like 'Technology, Vickers-Maxim 1-Pounder'
    (45 distinct values). We collapse on the leading token before any
    comma, then map technology-flavored buckets together.
    """
    if pd.isna(raw):
        return "Other"
    s = str(raw).strip()
    if not s:
        return "Other"

    head = s.split(",")[0].strip().lower()

    if head == "legislation":
        return "Legislation"
    if head == "organizational change":
        return "Organizational"
    if head in {"personnel", "chief of ordnance"}:
        return "Personnel"
    if head == "machine gun":
        return "Machine Gun"
    if head == "airplane":
        return "Airplane"
    if head == "technology" or "technology" in head:
        return "Technology"
    # specific gun designs (e.g. "Brown Segmental Wire Wound Gun")
    if any(token in head for token in ["gun", "rifle", "pistol", "tube"]):
        return "Technology"
    return "Other"


def load_historical_events(path: Path) -> pd.DataFrame:
    """Read + normalize Timeline_updated_for_RAs.xlsx.

    Returns columns: year, category, raw_type, description, source, added_by.
    Filters out rows we couldn't pin to a year (pre-1888 or unparseable).
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = pd.read_excel(path, sheet_name="Timeline inputs")

    out = pd.DataFrame()
    out["year"] = df.apply(
        lambda r: _coerce_year(
            r.get("End Date"),
            r.get("Only Year Available"),
            r.get("Event Description"),
        ),
        axis=1,
    )
    out["category"] = df["Event Type"].apply(_bucket_event_type)
    out["raw_type"] = df["Event Type"].astype(str)
    out["description"] = df["Event Description"].astype(str).str.strip()
    out["source"] = df["Source"].astype(str).where(df["Source"].notna(), "")
    out["added_by"] = df["Added By RA"].astype(str).where(df["Added By RA"].notna(), "")

    out = out[out["year"].notna() & (out["year"] >= 1888) & (out["year"] <= 1930)]
    out["year"] = out["year"].astype(int)
    return out.sort_values(["year", "category"]).reset_index(drop=True)


# ── Visualization ─────────────────────────────────────────────────────


def save_historical_events_chart(events: pd.DataFrame, out: Path) -> None:
    """Stacked annual bar — counts per year × category, BOF lifespan 1888-1920."""

    # The Board was active 1888-1920. The source spreadsheet has a handful of
    # retrospective 1930 entries; chart only the active period so we don't draw
    # a 9-year empty gap (1921-1929) just to surface 8 1930 rows.
    events = events[events["year"].between(1888, 1920)]
    years = list(range(1888, 1921))
    pivot = (
        events.groupby(["year", "category"])
        .size()
        .unstack("category", fill_value=0)
        .reindex(years, fill_value=0)
    )

    # Sample event descriptions per year for hover
    examples = (
        events.groupby(["year", "category"])["description"]
        .apply(lambda s: " · ".join(s.head(3).str.slice(0, 80)))
        .unstack("category", fill_value="")
        .reindex(years, fill_value="")
    )

    fig = go.Figure()

    for cat in _CATEGORY_ORDER:
        if cat not in pivot.columns:
            continue
        fig.add_trace(go.Bar(
            x=years,
            y=pivot[cat].values,
            name=cat,
            marker_color=_CATEGORY_COLORS[cat],
            marker_line_width=0,
            customdata=examples[cat].values,
            hovertemplate=(
                f"<b>%{{x}}</b><br><b>{cat}</b>: %{{y}} events"
                "<br><span style='font-size:11px;'>%{customdata}</span><extra></extra>"
            ),
        ))

    # Mark the canonical milestones
    annotations = [
        dict(x=1888, y=pivot.sum(axis=1).get(1888, 0) + 2,
             text="BOF<br>established",
             showarrow=False,
             font=dict(family=_SERIF, size=10, color=_TEXT_MID),
             align="center"),
        dict(x=1898, y=pivot.sum(axis=1).get(1898, 0) + 2,
             text="Spanish-American<br>War",
             showarrow=False,
             font=dict(family=_SERIF, size=10, color=_TEXT_MID),
             align="center"),
        dict(x=1917, y=pivot.sum(axis=1).get(1917, 0) + 2,
             text="U.S. enters<br>WWI",
             showarrow=False,
             font=dict(family=_SERIF, size=10, color=_TEXT_MID),
             align="center"),
        dict(x=1920, y=pivot.sum(axis=1).get(1920, 0) + 2,
             text="BOF<br>dissolved",
             showarrow=False,
             font=dict(family=_SERIF, size=10, color=_TEXT_MID),
             align="center"),
    ]

    total = len(events)
    most_common = events["category"].value_counts().head(3)
    subtitle = (
        f"{total:,} events across {len(years)} years.  "
        f"{most_common.index[0]} ({most_common.iloc[0]}) · "
        f"{most_common.index[1]} ({most_common.iloc[1]}) · "
        f"{most_common.index[2]} ({most_common.iloc[2]})"
    )

    fig.update_layout(
        title=dict(
            text=(
                f"<b>BOF Historical Events · 1888–1920</b>"
                f"<br><span style='font-size:12px;color:{_TEXT_MID};'>{subtitle}</span>"
            ),
            x=0.04, xanchor="left",
            font=dict(family=_SERIF, size=20, color=_TEXT_DARK),
        ),
        paper_bgcolor=_PLOT_BG,
        plot_bgcolor=_PLOT_BG,
        font=dict(family=_SANS, color=_TEXT_DARK, size=12),
        margin=dict(l=80, r=30, t=110, b=110),
        height=560,
        barmode="stack",
        xaxis=dict(
            title="Year", tickmode="linear", dtick=2,
            range=[1887.5, 1920.5],
            gridcolor=_GRID, zerolinecolor=_GRID,
        ),
        yaxis=dict(
            title="Events recorded", gridcolor=_GRID, zerolinecolor=_GRID,
        ),
        legend=dict(
            orientation="h", yanchor="top", y=-0.14, xanchor="center", x=0.5,
            bgcolor="rgba(0,0,0,0)",
        ),
        hoverlabel=dict(
            bgcolor="#FFF8EC", bordercolor=_CATEGORY_COLORS["Technology"],
            font_family=_SERIF,
        ),
        annotations=annotations,
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(
        out,
        include_plotlyjs="cdn",
        full_html=True,
        config={"displayModeBar": False, "responsive": True},
    )


__all__ = ["load_historical_events", "save_historical_events_chart"]
