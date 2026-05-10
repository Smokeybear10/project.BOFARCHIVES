"""Master ledger 1888-1919 visualizations.

Three charts off the master allotments + appropriations CSVs:
  - Master Timeline (annual appropriated vs allotted vs revoked)
  - Attribution Waterfall (total approp → revoked → net spent)
  - Pareto of Top Projects (descending bars + cumulative % line)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

# ── Design tokens (mirrors budget_visualize.py paper theme) ─────────────────
_PLOT_BG = "#EAE3D8"
_GRID = "#D6CEBF"
_TEXT_DARK = "#1A1A2E"
_TEXT_MID = "#55556A"
_SERIF = "Georgia, 'Times New Roman', serif"
_SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif"

# Brand colors from /brand-kit
_BRASS = "#C9A24C"
_BRASS_SOFT = "rgba(201,162,76,0.55)"
_VERMILLION = "#C5483D"
_STEEL = "#6B89A8"
_BONE = "#EBE2CC"


def _layout(title: str, subtitle: str = "", height: int = 480) -> dict:
    return dict(
        title=dict(
            text=f"<b>{title}</b><br><span style='font-size:12px;color:{_TEXT_MID};'>{subtitle}</span>",
            x=0.04, xanchor="left",
            font=dict(family=_SERIF, size=20, color=_TEXT_DARK),
        ),
        paper_bgcolor=_PLOT_BG,
        plot_bgcolor=_PLOT_BG,
        font=dict(family=_SANS, color=_TEXT_DARK, size=12),
        margin=dict(l=70, r=30, t=90, b=60),
        height=height,
        hoverlabel=dict(bgcolor="#FFF8EC", bordercolor=_BRASS, font_family=_SERIF),
    )


# ── 1. Master Timeline ──────────────────────────────────────────────────────


def save_master_timeline(
    allotments: pd.DataFrame,
    appropriations: pd.DataFrame,
    out: Path,
) -> None:
    """Annual stacked bars: appropriated (line), allotted (bars, split active/revoked)."""
    by_year = allotments.copy()
    by_year["revoked"] = by_year["revoked"].fillna(False)
    grp = by_year.groupby(["year", "revoked"])["allotted"].sum().unstack(fill_value=0)
    grp = grp.rename(columns={False: "active", True: "revoked"})
    if "active" not in grp.columns:
        grp["active"] = 0
    if "revoked" not in grp.columns:
        grp["revoked"] = 0

    appr = appropriations.groupby("year")["amount"].sum()

    years = sorted(set(grp.index) | set(appr.index))
    active = [grp["active"].get(y, 0) for y in years]
    revoked = [grp["revoked"].get(y, 0) for y in years]
    appr_vals = [appr.get(y, 0) for y in years]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=years, y=active,
        name="Allotted (active)",
        marker_color=_BRASS,
        marker_line_width=0,
        hovertemplate="<b>%{x}</b><br>Active allotments: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=years, y=revoked,
        name="Allotted (revoked)",
        marker_color=_VERMILLION,
        marker_line_width=0,
        opacity=0.85,
        hovertemplate="<b>%{x}</b><br>Revoked allotments: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=years, y=appr_vals,
        name="Congressional appropriation",
        mode="lines+markers",
        line=dict(color=_TEXT_DARK, width=2.5),
        marker=dict(size=7, color=_TEXT_DARK, line=dict(width=2, color=_PLOT_BG)),
        hovertemplate="<b>%{x}</b><br>Appropriated: $%{y:,.0f}<extra></extra>",
    ))

    layout = _layout(
        "Master Ledger · 1888–1919",
        f"Annual congressional appropriation vs. line-item allotments. Bars = allotments; line = appropriations.  "
        f"{len(allotments):,} line items · ${allotments['allotted'].sum():,.0f} total allotted",
        height=520,
    )
    layout["barmode"] = "stack"
    layout["xaxis"] = dict(
        title="Fiscal year", tickmode="linear", dtick=2,
        gridcolor=_GRID, zerolinecolor=_GRID,
    )
    layout["yaxis"] = dict(
        title="USD (nominal)", tickformat="$,.0f",
        gridcolor=_GRID, zerolinecolor=_GRID,
    )
    layout["legend"] = dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(**layout)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(out, include_plotlyjs="cdn", full_html=True)


# ── 2. Attribution Waterfall ────────────────────────────────────────────────


def save_attribution_waterfall(
    allotments: pd.DataFrame,
    appropriations: pd.DataFrame,
    out: Path,
) -> None:
    """Classic finance waterfall: appropriated → allotted → revoked → net.

    Tells the story of each dollar:
      Congressional appropriation (positive)
      → minus what wasn't allotted out
      → plus carryover/special funds
      → minus revoked allotments
      → ending in "net spent"
    """
    total_appr = appropriations["amount"].sum()
    total_allot = allotments["allotted"].sum()
    revoked_mask = allotments["revoked"].fillna(False)
    revoked_amt = allotments.loc[revoked_mask, "allotted"].sum()
    net_spent = total_allot - revoked_amt

    # Carryover/special funds = excess of allotments over appropriations
    # (allotments include re-allotment of revoked + carryover from prior years)
    carryover = max(0, total_allot - total_appr)
    unallotted = max(0, total_appr - (total_allot - carryover))

    fig = go.Figure(go.Waterfall(
        orientation="h",
        measure=["absolute", "relative", "relative", "relative", "total"],
        y=[
            "Congressional appropriation",
            "Carryover / re-allotment",
            "Less: unallotted balance",
            "Less: revoked allotments",
            "Net allotments retained",
        ][::-1],
        x=[total_appr, carryover, -unallotted, -revoked_amt, net_spent][::-1],
        text=[
            f"${total_appr:,.0f}",
            f"+${carryover:,.0f}",
            f"−${unallotted:,.0f}" if unallotted > 0 else "$0",
            f"−${revoked_amt:,.0f}",
            f"${net_spent:,.0f}",
        ][::-1],
        textposition="outside",
        textfont=dict(family=_SERIF, size=13, color=_TEXT_DARK),
        connector=dict(line=dict(color=_TEXT_MID, width=1, dash="dot")),
        increasing=dict(marker=dict(color=_BRASS, line=dict(color=_TEXT_DARK, width=0))),
        decreasing=dict(marker=dict(color=_VERMILLION, line=dict(color=_TEXT_DARK, width=0))),
        totals=dict(marker=dict(color=_STEEL, line=dict(color=_TEXT_DARK, width=0))),
        hovertemplate="<b>%{y}</b><br>%{x:$,.0f}<extra></extra>",
    ))

    layout = _layout(
        "Attribution Waterfall · Where the dollars went",
        f"From {len(appropriations)} congressional appropriations to {len(allotments):,} line-item allotments, "
        f"1888–1919.  ${revoked_amt:,.0f} revoked ({revoked_amt/total_allot*100:.0f}% of allotted)",
        height=420,
    )
    layout["xaxis"] = dict(title="USD (nominal)", tickformat="$,.0f", gridcolor=_GRID, zerolinecolor=_TEXT_MID)
    layout["yaxis"] = dict(gridcolor=_GRID)
    layout["showlegend"] = False
    fig.update_layout(**layout)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(out, include_plotlyjs="cdn", full_html=True)


# ── 3. Pareto of Top Projects (the "P shape") ───────────────────────────────


def save_pareto_top_projects(
    allotments: pd.DataFrame,
    out: Path,
    top_n: int = 25,
) -> None:
    """Pareto chart: descending bars by project total allotment + cumulative % line.

    Reveals the "vital few" — how many projects account for what share of total spend.
    """
    by_proj = (
        allotments.groupby("description", as_index=False)
        .agg(total=("allotted", "sum"), count=("allotted", "size"))
        .sort_values("total", ascending=False)
    )
    grand = by_proj["total"].sum()
    by_proj["cum_pct"] = by_proj["total"].cumsum() / grand * 100

    top = by_proj.head(top_n).copy()

    # Truncate long descriptions for display
    top["short"] = top["description"].str.slice(0, 60).where(
        top["description"].str.len() <= 60,
        top["description"].str.slice(0, 57) + "…"
    )

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=top["short"], y=top["total"],
        name="Total allotted",
        marker_color=_BRASS,
        marker_line_width=0,
        yaxis="y",
        customdata=top[["count", "description"]].values,
        hovertemplate=(
            "<b>%{customdata[1]}</b><br>"
            "Total allotted: $%{y:,.0f}<br>"
            "Allotment count: %{customdata[0]}<extra></extra>"
        ),
    ))

    fig.add_trace(go.Scatter(
        x=top["short"], y=top["cum_pct"],
        name="Cumulative share (%)",
        mode="lines+markers",
        line=dict(color=_TEXT_DARK, width=2.5),
        marker=dict(size=7, color=_TEXT_DARK, line=dict(width=2, color=_PLOT_BG)),
        yaxis="y2",
        hovertemplate="<b>Through this project</b><br>%{y:.1f}% of all spending<extra></extra>",
    ))

    # 80% reference line
    fig.add_hline(
        y=80, line_dash="dot", line_color=_VERMILLION, line_width=1,
        yref="y2", annotation_text="80% line", annotation_position="top right",
        annotation_font=dict(family=_SERIF, color=_VERMILLION, size=11),
    )

    layout = _layout(
        f"Pareto · Top {top_n} Projects by Allotment",
        f"Cumulative share of all ${grand:,.0f} allotted, 1888–1919.  "
        f"Read left-to-right: how few projects account for how much.",
        height=540,
    )
    layout["xaxis"] = dict(title="", tickangle=-45, gridcolor=_GRID, automargin=True)
    layout["yaxis"] = dict(
        title="Total allotted ($)", tickformat="$,.0f",
        gridcolor=_GRID, zerolinecolor=_GRID, side="left",
    )
    layout["yaxis2"] = dict(
        title="Cumulative %", overlaying="y", side="right",
        range=[0, 105], tickformat=",.0f", ticksuffix="%",
        showgrid=False,
    )
    layout["legend"] = dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        bgcolor="rgba(0,0,0,0)",
    )
    layout["margin"] = dict(l=70, r=70, t=100, b=180)
    fig.update_layout(**layout)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(out, include_plotlyjs="cdn", full_html=True)


__all__ = [
    "save_master_timeline",
    "save_attribution_waterfall",
    "save_pareto_top_projects",
]
