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
        height=560,
    )
    layout["barmode"] = "stack"
    # Pin x-axis to data range so Plotly doesn't pad out to 1886-1922.
    layout["xaxis"] = dict(
        title="Fiscal year", tickmode="linear", dtick=2,
        range=[min(years) - 0.6, max(years) + 0.6],
        gridcolor=_GRID, zerolinecolor=_GRID,
    )
    layout["yaxis"] = dict(
        title="USD (nominal)", tickformat="$,.0f",
        gridcolor=_GRID, zerolinecolor=_GRID,
    )
    # Push legend BELOW the title block (subtitle takes 2 lines on narrow viewports)
    layout["legend"] = dict(
        orientation="h", yanchor="top", y=-0.16, xanchor="center", x=0.5,
        bgcolor="rgba(0,0,0,0)",
    )
    layout["margin"] = dict(l=80, r=30, t=110, b=110)
    fig.update_layout(**layout)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(
        out,
        include_plotlyjs="cdn",
        full_html=True,
        config={"displayModeBar": False, "responsive": True},
    )


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
    top_n: int = 20,
) -> None:
    """Horizontal Pareto: top projects by total allotment, cumulative-share line on top.

    Horizontal layout lets long project descriptions read naturally instead of
    rotating 45° into illegibility.
    """
    by_proj = (
        allotments.groupby("description", as_index=False)
        .agg(total=("allotted", "sum"), count=("allotted", "size"))
        .sort_values("total", ascending=False)
    )
    grand = by_proj["total"].sum()
    by_proj["cum_pct"] = by_proj["total"].cumsum() / grand * 100

    # How many projects reach 80% — referenced in subtitle, not as an in-chart line
    n80 = int((by_proj["cum_pct"] <= 80).sum()) + 1
    top_share_pct = by_proj.head(top_n)["total"].sum() / grand * 100

    top = by_proj.head(top_n).copy()

    # Smart truncate: strip boilerplate prefixes + keep the meaningful tail
    import re as _re
    _PREFIX_RE = _re.compile(
        r"^(For\s+(the\s+)?(purchase|manufacture\s+and\s+test|construction|completing"
        r"|finishing\s+and\s+assembling|carriages\s+for|purchase\s+and\s+delivery)\s+of\s+"
        r"|To\s+apply\s+on\s+purchase\s+of\s+(experimental\s+)?"
        r"|To\s+enable\s+the\s+Chief\s+of\s+Ordnance\s+to\s+"
        r"|For\s+the\s+|For\s+|To\s+|Construction\s+of\s+(a\s+)?"
        r"|Tests?\s+of\s+|Purchase\s+of\s+(a\s+|one\s+)?"
        r"|Experiments?\s+and\s+tests?\s+of\s+)",
        flags=_re.IGNORECASE,
    )
    def _short(desc: str, line_len: int = 36, max_lines: int = 2) -> str:
        """Strip boilerplate, then word-wrap to <= max_lines lines of <= line_len chars."""
        body = _PREFIX_RE.sub("", desc, count=1).strip()
        # Drop trailing legalese / dates
        body = _re.sub(r",?\s*procured\s+under.+$", "", body, flags=_re.IGNORECASE)
        body = _re.sub(r",?\s*(in\s+accordance\s+with|approved\s+\w+).+$", "", body, flags=_re.IGNORECASE)
        body = body.replace("\n", " ").replace("  ", " ").strip()
        # Preserve proper-noun casing — only capitalize the leading char if it's lowercase
        if body and body[0].islower():
            body = body[0].upper() + body[1:]

        words = body.split(" ")
        lines: list[str] = []
        current = ""
        for w in words:
            candidate = (current + " " + w).strip() if current else w
            if len(candidate) <= line_len:
                current = candidate
            else:
                if current:
                    lines.append(current)
                if len(lines) == max_lines - 1:
                    # Last line: pack what we can, then ellipsis if overflow
                    remaining = " ".join(words[words.index(w):])
                    if len(remaining) <= line_len:
                        lines.append(remaining)
                    else:
                        lines.append(remaining[:line_len].rsplit(" ", 1)[0] + "…")
                    current = ""
                    break
                current = w
        if current and len(lines) < max_lines:
            lines.append(current)
        return "<br>".join(lines)
    top["short"] = top["description"].map(_short)
    # Plotly renders y-axis top→bottom; reverse so #1 sits at top
    top = top.iloc[::-1].reset_index(drop=True)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=top["short"], x=top["total"],
        orientation="h",
        name="Total allotted",
        marker=dict(
            color=_BRASS,
            line=dict(width=0),
        ),
        text=top["total"].map(lambda v: f"${v/1000:,.0f}k" if v >= 1000 else f"${v:,.0f}"),
        textposition="outside",
        textfont=dict(family=_SERIF, size=11, color=_TEXT_DARK),
        cliponaxis=False,
        customdata=top[["count", "description", "cum_pct"]].values,
        hovertemplate=(
            "<b>%{customdata[1]}</b><br>"
            "Total allotted: $%{x:,.0f}<br>"
            "Allotment events: %{customdata[0]}<br>"
            "Cumulative share through here: %{customdata[2]:.1f}%<extra></extra>"
        ),
    ))

    layout = _layout(
        f"Top {top_n} Projects by Total Allotment",
        f"These {top_n} projects account for "
        f"<b>{top_share_pct:.0f}%</b> of the ${grand:,.0f} the Board allotted 1888–1918. "
        f"It takes <b>{n80} of {len(by_proj):,}</b> projects to reach 80% of total spend — "
        f"the long tail is real.",
        height=720,
    )
    layout["xaxis"] = dict(
        title="Total allotted ($)",
        tickformat="$,.0f",
        gridcolor=_GRID,
        zerolinecolor=_GRID,
        showline=False,
    )
    layout["yaxis"] = dict(
        title="",
        automargin=True,
        showgrid=False,
        tickfont=dict(family=_SERIF, size=12, color=_TEXT_DARK),
    )
    layout["showlegend"] = False
    layout["bargap"] = 0.42
    # automargin handles the left edge so wrapped 2-line labels don't get clipped
    layout["margin"] = dict(l=20, r=110, t=110, b=60)
    layout["yaxis"]["tickfont"] = dict(family=_SERIF, size=11.5, color=_TEXT_DARK)
    fig.update_layout(**layout)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(
        out,
        include_plotlyjs="cdn",
        full_html=True,
        config={
            "displayModeBar": False,
            "responsive": True,
        },
    )


__all__ = [
    "save_master_timeline",
    "save_attribution_waterfall",
    "save_pareto_top_projects",
]
