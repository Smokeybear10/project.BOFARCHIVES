"""Combined visualizations: subjects considered + budget data, 1897-1908."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ── Design tokens ─────────────────────────────────────────────────────────────

_PLOT_BG   = "#EAE3D8"
_GRID      = "#D6CEBF"
_TEXT_DARK  = "#1A1A2E"
_TEXT_MID   = "#55556A"
_SERIF = "Georgia, 'Times New Roman', serif"
_SANS  = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif"

_CLUSTER_PALETTE = {
    "Artillery":                      "#1D3461",
    "Explosives":                     "#6B2D8B",
    "Small Arms":                     "#0A6E5D",
    "Armor and Protection":           "#7C4318",
    "Fortification and Engineering":  "#2D6A4F",
    "Communications and Observation": "#1B4F72",
    "Logistics and Support":          "#5D4037",
    "Other/Unclassified":             "#546E7A",
}


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _fmt_dollars(value: float) -> str:
    if value >= 1e9:
        return f"${value / 1e9:.1f}B"
    if value >= 1e6:
        return f"${value / 1e6:.0f}M"
    return f"${value:,.0f}"


def _card_html(plot_div: str, title: str, subtitle: str, note: str = "") -> str:
    footer_note = note or (
        "Source: BOF Annual Reports &amp; Congressional Appropriations, 1897–1908"
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{
    font-family:{_SANS};
    background:#E8E2D8;
    min-height:100vh;
    display:flex;
    align-items:flex-start;
    justify-content:center;
    padding:40px 20px 56px;
  }}
  .card{{
    width:100%;
    max-width:1060px;
    background:#FDFBF8;
    border-radius:5px;
    box-shadow:0 2px 20px rgba(0,0,0,0.11),0 1px 4px rgba(0,0,0,0.06);
    border-top:4px solid {_TEXT_DARK};
    padding:36px 42px 22px;
  }}
  .eyebrow{{
    font-size:10px;
    font-weight:700;
    letter-spacing:2px;
    text-transform:uppercase;
    color:#8B6E3C;
    margin-bottom:10px;
  }}
  h1{{
    font-family:{_SERIF};
    font-size:22px;
    font-weight:700;
    color:{_TEXT_DARK};
    line-height:1.3;
    margin-bottom:8px;
  }}
  .sub{{
    font-size:13.5px;
    color:{_TEXT_MID};
    line-height:1.6;
    margin-bottom:22px;
    max-width:720px;
  }}
  .rule{{
    height:1px;
    background:linear-gradient(to right,#C9B99A 35%,transparent);
    margin:0 0 16px;
  }}
  .footer{{
    margin-top:16px;
    padding-top:11px;
    border-top:1px solid #E4DDD3;
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:12px;
  }}
  .src{{font-size:10.5px;color:#9998A8;line-height:1.5}}
  .badge{{
    font-size:9.5px;font-weight:700;letter-spacing:1.2px;
    text-transform:uppercase;color:#FDFBF8;
    background:{_TEXT_DARK};padding:3px 10px;border-radius:3px;
    white-space:nowrap;flex-shrink:0;
  }}
</style>
</head>
<body>
<div class="card">
  <div class="eyebrow">Board of Ordnance &amp; Fortification &nbsp;·&nbsp; Combined Analysis</div>
  <h1>{title}</h1>
  <p class="sub">{subtitle}</p>
  <div class="rule"></div>
  {plot_div}
  <div class="footer">
    <div class="src">{footer_note}</div>
    <div class="badge">Interactive</div>
  </div>
</div>
</body>
</html>"""


# ── 1. Financial data on technology investment ────────────────────────────────

def save_investment_by_technology(
    proposals_df: pd.DataFrame,
    budget_df: pd.DataFrame,
    output_html: Path,
    thumbnail_png: Optional[Path] = None,
) -> None:
    """
    Dual-axis chart: military budget (1897-1908) as area backdrop,
    with proposal volume per technology cluster as stacked bars overlaid.
    Shows where the money was going vs what technologies were being proposed.
    """
    bof_years = range(1897, 1909)

    budget = budget_df[budget_df["year"].isin(bof_years)].copy()
    budget_by_year = (
        budget.groupby("year")
        .agg(total_2025=("appropriation_2025_usd", "sum"))
        .reset_index()
        .sort_values("year")
    )

    props = proposals_df[proposals_df["year"].isin(bof_years)].copy()
    cluster_year = (
        props.groupby(["year", "primary_cluster"])
        .size()
        .reset_index(name="count")
        .sort_values("year")
    )

    clusters = sorted(
        [c for c in cluster_year["primary_cluster"].unique() if c != "Other/Unclassified"]
    ) + ["Other/Unclassified"]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Budget area on secondary axis
    fig.add_trace(
        go.Scatter(
            x=budget_by_year["year"],
            y=budget_by_year["total_2025"],
            name="Total Military Budget (2025 $)",
            fill="tozeroy",
            fillcolor="rgba(26,26,46,0.08)",
            line=dict(color="rgba(26,26,46,0.35)", width=2, dash="dot"),
            hovertemplate="Year: %{x}<br>Budget: %{customdata}<extra></extra>",
            customdata=[_fmt_dollars(v) for v in budget_by_year["total_2025"]],
        ),
        secondary_y=True,
    )

    # Stacked bars for proposal counts by cluster
    for cluster in clusters:
        sub = cluster_year[cluster_year["primary_cluster"] == cluster]
        color = _CLUSTER_PALETTE.get(cluster, "#546E7A")
        fig.add_trace(
            go.Bar(
                x=sub["year"],
                y=sub["count"],
                name=cluster,
                marker=dict(color=_rgba(color, 0.85), line=dict(color=color, width=0.5)),
                hovertemplate=(
                    f"<b>{cluster}</b><br>"
                    "Year: %{x}<br>"
                    "Proposals: %{y}<extra></extra>"
                ),
            ),
            secondary_y=False,
        )

    fig.update_layout(
        barmode="stack",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=_PLOT_BG,
        legend=dict(
            orientation="h", y=-0.18, x=0.5, xanchor="center",
            font=dict(size=10.5, family=_SANS),
            bgcolor="rgba(0,0,0,0)",
        ),
        font=dict(size=12, family=_SANS, color=_TEXT_DARK),
        height=520,
        margin=dict(l=70, r=80, t=20, b=120),
        hoverlabel=dict(bgcolor="#FDFBF8", bordercolor=_GRID,
                        font=dict(size=12, family=_SANS)),
    )
    fig.update_xaxes(
        title_text="Year", tickvals=list(bof_years),
        gridcolor=_GRID, linecolor=_GRID, tickfont=dict(size=11),
    )
    fig.update_yaxes(
        title_text="Proposals Submitted", gridcolor=_GRID,
        linecolor=_GRID, tickfont=dict(size=11), secondary_y=False,
    )
    fig.update_yaxes(
        title_text="Total Budget (2025 $)", tickformat="$,.0f",
        gridcolor="rgba(0,0,0,0)", linecolor=_GRID,
        tickfont=dict(size=11), secondary_y=True,
    )

    if thumbnail_png is not None:
        thumbnail_png.parent.mkdir(parents=True, exist_ok=True)
        fig.write_image(str(thumbnail_png), width=1200, height=750, scale=1)

    plot_div = fig.to_html(full_html=False, include_plotlyjs="cdn")
    html = _card_html(
        plot_div,
        title="Technology Investment vs. Proposal Activity, 1897–1908",
        subtitle=(
            "Stacked bars show proposal volume by technology cluster each year. "
            "The dotted area shows total military budget (2025-adjusted) for context — "
            "revealing whether increased funding correlated with more innovation proposals."
        ),
    )
    output_html.write_text(html, encoding="utf-8")


# ── 2. Technology timeline — development periods ─────────────────────────────

def save_technology_timeline(
    proposals_df: pd.DataFrame,
    output_html: Path,
    thumbnail_png: Optional[Path] = None,
) -> None:
    """
    Gantt-style timeline showing when each technology cluster was active
    (had proposals submitted), with bubble size = proposal count per year.
    """
    bof_years = range(1897, 1909)
    props = proposals_df[proposals_df["year"].isin(bof_years)].copy()

    cluster_year = (
        props.groupby(["primary_cluster", "year"])
        .agg(
            count=("primary_cluster", "size"),
            approved=("is_approved", "sum"),
        )
        .reset_index()
    )
    cluster_year["approval_pct"] = (
        cluster_year["approved"] / cluster_year["count"] * 100
    ).round(1)

    clusters = sorted(
        [c for c in cluster_year["primary_cluster"].unique() if c != "Other/Unclassified"]
    ) + (["Other/Unclassified"] if "Other/Unclassified" in cluster_year["primary_cluster"].values else [])

    fig = go.Figure()

    # Horizontal span lines (light bars showing active range)
    for i, cluster in enumerate(clusters):
        sub = cluster_year[cluster_year["primary_cluster"] == cluster]
        if sub.empty:
            continue
        color = _CLUSTER_PALETTE.get(cluster, "#546E7A")
        min_year, max_year = sub["year"].min(), sub["year"].max()
        fig.add_shape(
            type="rect",
            x0=min_year - 0.4, x1=max_year + 0.4,
            y0=i - 0.3, y1=i + 0.3,
            fillcolor=_rgba(color, 0.12),
            line=dict(width=0),
            layer="below",
        )

    # Bubbles
    for i, cluster in enumerate(clusters):
        sub = cluster_year[cluster_year["primary_cluster"] == cluster].sort_values("year")
        if sub.empty:
            continue
        color = _CLUSTER_PALETTE.get(cluster, "#546E7A")
        max_count = cluster_year["count"].max()
        sizes = [max(8, (c / max_count) * 45) for c in sub["count"]]

        fig.add_trace(
            go.Scatter(
                x=sub["year"],
                y=[i] * len(sub),
                mode="markers",
                name=cluster,
                marker=dict(
                    size=sizes,
                    color=_rgba(color, 0.75),
                    line=dict(color=color, width=1.5),
                ),
                hovertemplate=(
                    f"<b>{cluster}</b><br>"
                    "Year: %{x}<br>"
                    "Proposals: %{customdata[0]}<br>"
                    "Approved: %{customdata[1]} (%{customdata[2]:.1f}%)"
                    "<extra></extra>"
                ),
                customdata=list(zip(sub["count"], sub["approved"], sub["approval_pct"])),
                showlegend=False,
            )
        )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=_PLOT_BG,
        xaxis=dict(
            title="Year", tickvals=list(bof_years),
            gridcolor=_GRID, linecolor=_GRID,
            tickfont=dict(size=11),
            range=[1896.2, 1908.8],
        ),
        yaxis=dict(
            tickvals=list(range(len(clusters))),
            ticktext=clusters,
            tickfont=dict(size=12, family=_SERIF),
            gridcolor="rgba(0,0,0,0)",
            linecolor=_GRID,
        ),
        font=dict(size=12, family=_SANS, color=_TEXT_DARK),
        height=460,
        margin=dict(l=230, r=40, t=20, b=60),
        hoverlabel=dict(bgcolor="#FDFBF8", bordercolor=_GRID,
                        font=dict(size=12, family=_SANS)),
    )

    # Size legend annotation
    fig.add_annotation(
        x=1908.5, y=-0.8,
        text="Bubble size = proposal count",
        showarrow=False, xanchor="right",
        font=dict(size=10.5, color=_TEXT_MID, family=_SANS),
    )

    if thumbnail_png is not None:
        thumbnail_png.parent.mkdir(parents=True, exist_ok=True)
        fig.write_image(str(thumbnail_png), width=1200, height=750, scale=1)

    plot_div = fig.to_html(full_html=False, include_plotlyjs="cdn")
    html = _card_html(
        plot_div,
        title="Technology Development Timeline, 1897–1908",
        subtitle=(
            "Each row is a technology cluster. Bubble size reflects the number of proposals "
            "submitted that year; shaded bars show the active period. Hover for approval rates. "
            "Tracks which technologies peaked, emerged, or faded across the BOF era."
        ),
    )
    output_html.write_text(html, encoding="utf-8")


# ── 3. Technology type prevalence by period ───────────────────────────────────

def save_technology_prevalence(
    proposals_df: pd.DataFrame,
    output_html: Path,
    thumbnail_png: Optional[Path] = None,
) -> None:
    """
    100% stacked area showing the proportion of each technology cluster over time.
    Reveals shifting priorities across the BOF reporting period.
    """
    bof_years = range(1897, 1909)
    props = proposals_df[proposals_df["year"].isin(bof_years)].copy()

    cluster_year = (
        props.groupby(["year", "primary_cluster"])
        .size()
        .reset_index(name="count")
    )
    pivot = cluster_year.pivot_table(
        index="year", columns="primary_cluster", values="count", fill_value=0
    )
    totals = pivot.sum(axis=1)
    pct = pivot.div(totals, axis=0) * 100

    clusters = sorted(
        [c for c in pct.columns if c != "Other/Unclassified"]
    ) + (["Other/Unclassified"] if "Other/Unclassified" in pct.columns else [])

    fig = go.Figure()

    for cluster in clusters:
        if cluster not in pct.columns:
            continue
        color = _CLUSTER_PALETTE.get(cluster, "#546E7A")
        counts = pivot[cluster] if cluster in pivot.columns else [0] * len(pct)
        fig.add_trace(
            go.Scatter(
                x=pct.index,
                y=pct[cluster],
                name=cluster,
                stackgroup="prevalence",
                fillcolor=_rgba(color, 0.65),
                line=dict(color=color, width=1),
                hovertemplate=(
                    f"<b>{cluster}</b><br>"
                    "Year: %{x}<br>"
                    "Share: %{y:.1f}%<br>"
                    "Count: %{customdata}<extra></extra>"
                ),
                customdata=counts.values if hasattr(counts, 'values') else counts,
            )
        )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=_PLOT_BG,
        xaxis=dict(
            title="Year", tickvals=list(bof_years),
            gridcolor=_GRID, linecolor=_GRID,
            tickfont=dict(size=11),
        ),
        yaxis=dict(
            title="Share of Proposals (%)",
            range=[0, 105],
            gridcolor=_GRID, linecolor=_GRID,
            ticksuffix="%", tickfont=dict(size=11),
        ),
        legend=dict(
            orientation="h", y=-0.18, x=0.5, xanchor="center",
            font=dict(size=10.5, family=_SANS),
            bgcolor="rgba(0,0,0,0)",
        ),
        font=dict(size=12, family=_SANS, color=_TEXT_DARK),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#FDFBF8", bordercolor=_GRID,
                        font=dict(size=12, family=_SANS)),
        height=500,
        margin=dict(l=70, r=36, t=20, b=110),
    )

    if thumbnail_png is not None:
        thumbnail_png.parent.mkdir(parents=True, exist_ok=True)
        fig.write_image(str(thumbnail_png), width=1200, height=750, scale=1)

    plot_div = fig.to_html(full_html=False, include_plotlyjs="cdn")
    html = _card_html(
        plot_div,
        title="Technology Type Prevalence by Year, 1897–1908",
        subtitle=(
            "Proportional breakdown of proposal submissions by technology cluster each year. "
            "Shows how the Board's attention shifted — from fortification-heavy early years "
            "toward explosives and small arms as the period progressed."
        ),
    )
    output_html.write_text(html, encoding="utf-8")
