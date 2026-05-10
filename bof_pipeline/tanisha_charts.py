"""Technology Type Prevalence — BOF Subjects Considered, 1897-1908.

Original analysis and R/ggplot2 visualizations by **Tanisha**.
Source: team/tanisha/technology_prevalence.R

This module is a Plotly port of her three charts so they can ship in the
dashboard alongside the rest of the team's work. Her data, category
taxonomy, and color palette are preserved verbatim.

Three charts:
  1. save_tanisha_stacked_bars()  — counts per period × category
  2. save_tanisha_heatmap()       — same data, heatmap with row labels
  3. save_tanisha_ranking()       — descending horizontal bars by total
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

# ── Tanisha's data (verbatim from the R script) ─────────────────────────

PERIODS = [
    "1897-98", "1898-99", "1900-01", "1901-02",
    "1903-04", "1904-05", "1905-06", "1906-07", "1907-08",
]

# Category → list of counts in PERIODS order
COUNTS = {
    "Aerial / Aviation":            [29, 51,  1,  5, 18,  4,  7,  8, 13],
    "Artillery & Guns":             [68, 39, 38, 53, 52, 38, 31, 32, 25],
    "Projectiles & Ammunition":     [130, 22, 27, 28, 22, 18, 20, 23, 22],
    "Explosives & Propellants":     [23,  9,  9,  7,  8,  5,  1,  3,  4],
    "Torpedoes & Mines":            [42,  6,  3,  3,  9, 12,  8,  5,  8],
    "Range Finding & Fire Control": [17, 12,  9, 13, 17, 14, 18, 10, 15],
    "Wireless & Electrical":        [ 4,  5,  2,  8,  2,  1,  0,  0,  3],
    "Armor & Fortification":        [23,  4,  3,  9, 17, 11,  6,  9,  7],
    "Searchlights & Optics":        [ 2,  2,  3,  3, 10,  7,  5, 22, 10],
    "Small Arms":                   [ 9,  4,  4, 14,  9,  5,  7,  4,  3],
    "Transportation & Vehicles":    [ 2,  2,  3,  5,  5,  0,  4,  0,  4],
    "Entrenching & Field Equip.":   [ 0,  3, 10, 10,  8,  7,  3,  1,  0],
    "Other":                        [48, 20, 13, 52, 41, 17, 23, 25, 34],
}

# Category color palette (Tanisha's choices, unchanged)
PALETTE = {
    "Aerial / Aviation":            "#378ADD",
    "Artillery & Guns":             "#1D9E75",
    "Projectiles & Ammunition":     "#D85A30",
    "Explosives & Propellants":     "#D4537E",
    "Torpedoes & Mines":            "#888780",
    "Range Finding & Fire Control": "#639922",
    "Wireless & Electrical":        "#BA7517",
    "Armor & Fortification":        "#534AB7",
    "Searchlights & Optics":        "#185FA5",
    "Small Arms":                   "#0F6E56",
    "Transportation & Vehicles":    "#993C1D",
    "Entrenching & Field Equip.":   "#3B6D11",
    "Other":                        "#5F5E5A",
}

# Heatmap blue ramp (Tanisha's gradient)
HEAT_COLORSCALE = [
    [0.00, "#E6F1FB"],
    [0.17, "#B5D4F4"],
    [0.33, "#85B7EB"],
    [0.50, "#378ADD"],
    [0.67, "#185FA5"],
    [0.83, "#0C447C"],
    [1.00, "#042C53"],
]

# Y-axis ordering for the heatmap (Tanisha's manual ranking, top to bottom)
HEATMAP_ORDER = [
    "Projectiles & Ammunition",
    "Artillery & Guns",
    "Other",
    "Torpedoes & Mines",
    "Aerial / Aviation",
    "Armor & Fortification",
    "Explosives & Propellants",
    "Range Finding & Fire Control",
    "Small Arms",
    "Searchlights & Optics",
    "Entrenching & Field Equip.",
    "Transportation & Vehicles",
    "Wireless & Electrical",
]

# Pre-computed totals + percentages from Tanisha's ranking chart
RANKING = [
    ("Artillery & Guns",             376),
    ("Projectiles & Ammunition",     312),
    ("Other",                        273),
    ("Aerial / Aviation",            136),
    ("Range Finding & Fire Control", 125),
    ("Torpedoes & Mines",             96),
    ("Armor & Fortification",         89),
    ("Explosives & Propellants",      69),
    ("Searchlights & Optics",         64),
    ("Small Arms",                    59),
    ("Entrenching & Field Equip.",    42),
    ("Transportation & Vehicles",     25),
    ("Wireless & Electrical",         25),
]

# ── Shared layout (matches dashboard paper theme) ─────────────────────────

_PLOT_BG = "#FAF9F6"  # softer than the rest of the paper theme; matches Tanisha's R panel
_GRID = "#E5E0D5"
_TEXT_DARK = "#2C2C2A"
_TEXT_MID = "#5F5E5A"
_SERIF = "Georgia, 'Times New Roman', serif"
_SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif"

_CREDIT = (
    "Original analysis by <b>Tanisha</b> · "
    "<a href='team/tanisha/technology_prevalence.R' "
    "style='color:#5F5E5A;'>R/ggplot2 source</a>"
)


def _layout(title: str, subtitle: str, height: int = 520) -> dict:
    return dict(
        title=dict(
            text=(
                f"<b>{title}</b>"
                f"<br><span style='font-size:11px;color:{_TEXT_MID};'>{subtitle}</span>"
                f"<br><span style='font-size:10px;color:{_TEXT_MID};'>{_CREDIT}</span>"
            ),
            x=0.04, xanchor="left",
            font=dict(family=_SERIF, size=18, color=_TEXT_DARK),
        ),
        paper_bgcolor=_PLOT_BG,
        plot_bgcolor=_PLOT_BG,
        font=dict(family=_SANS, color=_TEXT_DARK, size=12),
        margin=dict(l=70, r=30, t=120, b=80),
        height=height,
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#888780", font_family=_SERIF),
    )


# ── 1. Stacked bar chart ────────────────────────────────────────────────


def save_tanisha_stacked_bars(out: Path) -> None:
    """Counts per period, stacked by technology category (Tanisha's stacked bar)."""
    fig = go.Figure()

    for cat, counts in COUNTS.items():
        fig.add_trace(go.Bar(
            x=PERIODS, y=counts, name=cat,
            marker_color=PALETTE[cat],
            marker_line_width=0,
            hovertemplate=f"<b>{cat}</b><br>%{{x}}: %{{y}} subjects<extra></extra>",
        ))

    layout = _layout(
        "Technology Type Prevalence by Period",
        "Board of Ordnance &amp; Fortification Annual Reports, 1897–1908 · "
        "13 categories of subjects considered",
        height=560,
    )
    layout["barmode"] = "stack"
    layout["xaxis"] = dict(
        tickangle=-45, gridcolor=_GRID, zerolinecolor=_GRID, showgrid=False,
    )
    layout["yaxis"] = dict(
        title="Number of subjects", gridcolor=_GRID, zerolinecolor=_GRID,
    )
    layout["legend"] = dict(
        orientation="h", yanchor="top", y=-0.16, xanchor="center", x=0.5,
        bgcolor="rgba(0,0,0,0)", font=dict(size=10),
    )
    fig.update_layout(**layout)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(out, include_plotlyjs="cdn", full_html=True)


# ── 2. Heatmap ──────────────────────────────────────────────────────────


def save_tanisha_heatmap(out: Path) -> None:
    """Categories × periods heatmap, with count labels in each cell."""
    # Build matrix in the order Tanisha specified (top → bottom = most → least)
    matrix = [COUNTS[c] for c in HEATMAP_ORDER]
    text = [[str(v) for v in row] for row in matrix]
    # White text where count > 50 (matches her R logic)
    text_color = [
        ["white" if v > 50 else "#0C447C" for v in row] for row in matrix
    ]

    fig = go.Figure(go.Heatmap(
        z=matrix,
        x=PERIODS,
        y=HEATMAP_ORDER,
        text=text,
        texttemplate="%{text}",
        textfont=dict(family=_SERIF, size=11, color="#0C447C"),
        colorscale=HEAT_COLORSCALE,
        colorbar=dict(
            title=dict(text="Subjects", font=dict(family=_SERIF, size=11)),
            tickfont=dict(family=_SANS, size=10),
            thickness=16, len=0.7, outlinewidth=0,
        ),
        xgap=2, ygap=2,
        hovertemplate="<b>%{y}</b><br>%{x}: %{z} subjects<extra></extra>",
    ))

    # Plotly heatmap doesn't support per-cell font colors in textfont (single
    # color only), so we overlay text annotations to recover Tanisha's
    # white-on-dark / blue-on-light contrast rule.
    fig.update_traces(textfont_color=None, texttemplate="")
    annotations = []
    for yi, cat in enumerate(HEATMAP_ORDER):
        for xi, period in enumerate(PERIODS):
            v = matrix[yi][xi]
            annotations.append(dict(
                x=period, y=cat, text=str(v),
                font=dict(
                    family=_SERIF, size=11,
                    color="white" if v > 50 else "#0C447C",
                ),
                showarrow=False,
            ))

    layout = _layout(
        "Technology Prevalence Heatmap by Period",
        "Board of Ordnance &amp; Fortification Annual Reports, 1897–1908 · "
        "shade = subject count, capped at 130",
        height=600,
    )
    layout["xaxis"] = dict(tickangle=-45, gridcolor=_GRID, showgrid=False, side="bottom")
    layout["yaxis"] = dict(autorange="reversed", gridcolor=_GRID, showgrid=False)
    layout["annotations"] = annotations
    fig.update_layout(**layout)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(out, include_plotlyjs="cdn", full_html=True)


# ── 3. Horizontal bar ranking ───────────────────────────────────────────


def save_tanisha_ranking(out: Path) -> None:
    """Descending horizontal bars by total subjects per category."""
    sorted_rows = sorted(RANKING, key=lambda r: r[1])  # ascending so largest at top
    cats = [r[0] for r in sorted_rows]
    totals = [r[1] for r in sorted_rows]
    grand = sum(totals)
    labels = [f"  {t}  ({t/grand*100:.1f}%)" for t in totals]
    colors = [PALETTE[c] for c in cats]

    fig = go.Figure(go.Bar(
        x=totals, y=cats, orientation="h",
        marker_color=colors,
        marker_line_width=0,
        text=labels,
        textposition="outside",
        textfont=dict(family=_SERIF, size=11, color=_TEXT_MID),
        hovertemplate="<b>%{y}</b><br>%{x} subjects total<extra></extra>",
    ))

    layout = _layout(
        "Technology Category Ranking by Total Subjects",
        f"Board of Ordnance &amp; Fortification Annual Reports, 1897–1908 · "
        f"{grand:,} total subject classifications across 13 categories",
        height=560,
    )
    layout["xaxis"] = dict(
        title="Total subjects (1897–1908)",
        gridcolor=_GRID, zerolinecolor=_GRID,
        range=[0, max(totals) * 1.22],
    )
    layout["yaxis"] = dict(showgrid=False)
    layout["showlegend"] = False
    fig.update_layout(**layout)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(out, include_plotlyjs="cdn", full_html=True)


# ── CSV emitter (for replicability) ─────────────────────────────────────


def write_tanisha_data_csv(out: Path) -> None:
    """Tanisha's category × period counts as a long-format CSV."""
    rows = []
    for cat, counts in COUNTS.items():
        for period, count in zip(PERIODS, counts):
            rows.append({"category": cat, "period": period, "count": count})
    df = pd.DataFrame(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)


__all__ = [
    "save_tanisha_stacked_bars",
    "save_tanisha_heatmap",
    "save_tanisha_ranking",
    "write_tanisha_data_csv",
]
