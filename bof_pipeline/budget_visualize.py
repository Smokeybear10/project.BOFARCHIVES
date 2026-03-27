"""Budget visualizations for BOF Military Budgets, 1865-1920."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

# ── Design tokens (mirrors visualize.py) ─────────────────────────────────────

_PLOT_BG  = "#EAE3D8"
_GRID     = "#D6CEBF"
_TEXT_DARK = "#1A1A2E"
_TEXT_MID  = "#55556A"
_SERIF = "Georgia, 'Times New Roman', serif"
_SANS  = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif"

_BRANCH_COLORS = {
    "Army": {"fill": "rgba(29,52,97,0.50)",  "line": "#1D3461"},
    "Navy": {"fill": "rgba(10,110,93,0.50)", "line": "#0A6E5D"},
}

_EVENTS = [
    (1865, "Civil War ends"),
    (1898, "Spanish-American War"),
    (1917, "U.S. enters WWI"),
]


def _fmt_billions(value: float) -> str:
    if value >= 1e9:
        return f"${value / 1e9:.1f}B"
    if value >= 1e6:
        return f"${value / 1e6:.0f}M"
    return f"${value:,.0f}"


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _card_html(plot_div: str, title: str, subtitle: str, note: str = "") -> str:
    footer_note = note or (
        "Source: U.S. Congressional Appropriations Acts, 1865–1920 &nbsp;·&nbsp; "
        "Inflation adjustment to 2025 dollars via CPI"
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
  <div class="eyebrow">U.S. Military Budget &nbsp;·&nbsp; Historical Analysis</div>
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


# ── 1. Stacked area chart ─────────────────────────────────────────────────────

def save_budget_area_chart(df: pd.DataFrame, output_html: Path) -> None:
    """Stacked area: Army + Navy appropriations 1865–1920, nominal vs. adjusted toggle."""
    branches = ["Navy", "Army"]  # Navy on bottom, Army stacks on top

    traces_nominal:  list[go.Scatter] = []
    traces_adjusted: list[go.Scatter] = []

    for branch in branches:
        sub    = df[df["branch"] == branch].sort_values("year")
        colors = _BRANCH_COLORS[branch]

        traces_nominal.append(
            go.Scatter(
                x=sub["year"],
                y=sub["appropriation_usd"],
                name=branch,
                stackgroup="nominal",
                fillcolor=colors["fill"],
                line=dict(color=colors["line"], width=2),
                hovertemplate=(
                    f"<b>{branch}</b><br>"
                    "Year: %{x}<br>"
                    "Appropriation: %{customdata}<extra></extra>"
                ),
                customdata=[_fmt_billions(v) for v in sub["appropriation_usd"]],
                visible=True,
            )
        )
        traces_adjusted.append(
            go.Scatter(
                x=sub["year"],
                y=sub["appropriation_2025_usd"],
                name=f"{branch} (2025 $)",
                stackgroup="adjusted",
                fillcolor=colors["fill"],
                line=dict(color=colors["line"], width=2),
                hovertemplate=(
                    f"<b>{branch}</b><br>"
                    "Year: %{x}<br>"
                    "2025 Value: %{customdata}<extra></extra>"
                ),
                customdata=[_fmt_billions(v) for v in sub["appropriation_2025_usd"]],
                visible=False,
            )
        )

    n            = len(branches)
    vis_nominal  = [True]  * n + [False] * n
    vis_adjusted = [False] * n + [True]  * n

    fig = go.Figure(data=traces_nominal + traces_adjusted)

    # Event annotation lines
    ymax = df.groupby("year")["appropriation_usd"].sum().max()
    shapes, annotations = [], []
    for year, label in _EVENTS:
        shapes.append(dict(
            type="line", x0=year, x1=year, y0=0, y1=ymax * 1.02,
            line=dict(color=_rgba(_TEXT_DARK, 0.28), width=1.3, dash="dot"),
            layer="below",
        ))
        annotations.append(dict(
            x=year, y=ymax * 1.055,
            text=label, showarrow=False,
            font=dict(size=10, color=_TEXT_MID, family=_SANS),
            xanchor="center",
        ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=_PLOT_BG,
        updatemenus=[dict(
            type="buttons",
            direction="right",
            x=1.0, xanchor="right",
            y=1.0, yanchor="bottom",
            showactive=True,
            buttons=[
                dict(
                    label="Nominal $",
                    method="update",
                    args=[{"visible": vis_nominal},
                          {"yaxis.title.text": "Appropriation (Nominal $)"}],
                ),
                dict(
                    label="2025 Inflation-Adjusted",
                    method="update",
                    args=[{"visible": vis_adjusted},
                          {"yaxis.title.text": "Appropriation (2025 $)"}],
                ),
            ],
            bgcolor="#FDFBF8",
            bordercolor=_GRID,
            borderwidth=1,
            font=dict(size=11, family=_SANS, color=_TEXT_DARK),
        )],
        xaxis=dict(
            title="Fiscal Year",
            title_font=dict(size=11, family=_SANS),
            gridcolor=_GRID, linecolor=_GRID,
            tickmode="linear", dtick=5,
            tickfont=dict(size=11),
        ),
        yaxis=dict(
            title="Appropriation (Nominal $)",
            title_font=dict(size=11, family=_SANS),
            gridcolor=_GRID, linecolor=_GRID,
            tickformat="$,.0f",
            tickfont=dict(size=11),
        ),
        legend=dict(
            orientation="h", y=1.01, x=0,
            xanchor="left", yanchor="bottom",
            font=dict(size=12, family=_SANS),
            bgcolor="rgba(0,0,0,0)",
        ),
        font=dict(size=12, family=_SANS, color=_TEXT_DARK),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#FDFBF8", bordercolor=_GRID,
                        font=dict(size=12, family=_SANS)),
        height=500,
        margin=dict(l=80, r=36, t=40, b=60),
        shapes=shapes,
        annotations=annotations,
    )

    plot_div = fig.to_html(full_html=False, include_plotlyjs="cdn")
    html = _card_html(
        plot_div,
        title="U.S. Military Appropriations, 1865–1920",
        subtitle=(
            "Stacked area showing Army and Navy appropriations over 55 fiscal years. "
            "Toggle between nominal and 2025 inflation-adjusted dollars. "
            "Dotted lines mark the three major military inflection points of the era."
        ),
    )
    output_html.write_text(html, encoding="utf-8")


# ── 2. Treemap ────────────────────────────────────────────────────────────────

def save_budget_treemap(df: pd.DataFrame, output_html: Path) -> None:
    """Treemap: total 2025-adjusted spending per decade × branch."""
    agg = (
        df.groupby(["decade", "branch"])
        .agg(total_2025=("appropriation_2025_usd", "sum"))
        .reset_index()
    )

    branch_colors = {"Army": "#1D3461", "Navy": "#0A6E5D"}
    decades = sorted(agg["decade"].unique())

    ids, labels, parents, values, custom, colors = [], [], [], [], [], []

    grand_total = agg["total_2025"].sum()
    ids.append("all");       labels.append("Total Military Spending")
    parents.append("");      values.append(grand_total)
    custom.append(_fmt_billions(grand_total))
    colors.append("#D6CEBF")

    for decade in decades:
        decade_total = agg[agg["decade"] == decade]["total_2025"].sum()
        ids.append(decade);     labels.append(decade)
        parents.append("all");  values.append(decade_total)
        custom.append(_fmt_billions(decade_total))
        colors.append("#B0A898")

    for decade in decades:
        for _, row in agg[agg["decade"] == decade].iterrows():
            node_id = f"{row['decade']}_{row['branch']}"
            ids.append(node_id)
            labels.append(row["branch"])
            parents.append(decade)
            values.append(row["total_2025"])
            custom.append(_fmt_billions(row["total_2025"]))
            colors.append(branch_colors.get(row["branch"], "#546E7A"))

    fig = go.Figure(
        go.Treemap(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            customdata=custom,
            texttemplate="<b>%{label}</b><br>%{customdata}",
            textfont=dict(size=13, family=_SANS),
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Total (2025 $): %{customdata}<br>"
                "<extra></extra>"
            ),
            marker=dict(
                colors=colors,
                line=dict(width=2, color="#FDFBF8"),
            ),
            branchvalues="total",
            maxdepth=3,
            pathbar=dict(
                visible=True,
                thickness=22,
                textfont=dict(size=11, family=_SANS),
            ),
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=13, family=_SANS, color="#FDFBF8"),
        height=540,
        margin=dict(l=4, r=4, t=4, b=4),
    )

    plot_div = fig.to_html(full_html=False, include_plotlyjs="cdn")
    html = _card_html(
        plot_div,
        title="Military Budget by Decade, 1865–1920",
        subtitle=(
            "Hierarchical breakdown of total 2025-adjusted appropriations by decade and branch. "
            "Rectangle area is proportional to spending. Click a decade to drill down; "
            "use the breadcrumb bar to navigate back."
        ),
        note=(
            "Source: U.S. Congressional Appropriations Acts, 1865–1920 &nbsp;·&nbsp; "
            "Values in 2025-adjusted dollars &nbsp;·&nbsp; Click to explore"
        ),
    )
    output_html.write_text(html, encoding="utf-8")


# ── 3. Army vs Navy share ─────────────────────────────────────────────────────

def save_budget_share_chart(df: pd.DataFrame, output_html: Path) -> None:
    """100% stacked area: Army vs Navy share of total military spending, 1865–1920."""
    pivot = (
        df.groupby(["year", "branch"])["appropriation_usd"]
        .sum()
        .unstack(fill_value=0)
        .reset_index()
    )
    total = pivot["Army"] + pivot["Navy"]
    pivot["army_pct"] = pivot["Army"] / total * 100
    pivot["navy_pct"] = pivot["Navy"] / total * 100

    fig = go.Figure()

    for branch, col, color_key in [
        ("Navy", "navy_pct", "Navy"),
        ("Army", "army_pct", "Army"),
    ]:
        colors = _BRANCH_COLORS[color_key]
        fig.add_trace(
            go.Scatter(
                x=pivot["year"],
                y=pivot[col],
                name=branch,
                stackgroup="share",
                fillcolor=colors["fill"],
                line=dict(color=colors["line"], width=2),
                hovertemplate=(
                    f"<b>{branch}</b><br>"
                    "Year: %{x}<br>"
                    "Share: %{y:.1f}%<extra></extra>"
                ),
            )
        )

    # Event lines + labels
    for year, label in _EVENTS:
        fig.add_vline(
            x=year,
            line=dict(color=_rgba(_TEXT_DARK, 0.28), width=1.3, dash="dot"),
        )
        fig.add_annotation(
            x=year, y=106,
            text=label, showarrow=False,
            xanchor="center",
            font=dict(size=10, color=_TEXT_MID, family=_SANS),
        )

    # Mid-point label for each area (static annotation to orient reader)
    fig.add_annotation(
        x=1882, y=60,
        text="<b>Army</b>",
        showarrow=False,
        font=dict(size=14, color="#FDFBF8", family=_SERIF),
        opacity=0.85,
    )
    fig.add_annotation(
        x=1882, y=10,
        text="<b>Navy</b>",
        showarrow=False,
        font=dict(size=14, color="#FDFBF8", family=_SERIF),
        opacity=0.85,
    )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=_PLOT_BG,
        xaxis=dict(
            title="Fiscal Year",
            title_font=dict(size=11, family=_SANS),
            gridcolor=_GRID, linecolor=_GRID,
            dtick=5, tickfont=dict(size=11),
        ),
        yaxis=dict(
            title="Share of Total Budget (%)",
            title_font=dict(size=11, family=_SANS),
            range=[0, 112],
            gridcolor=_GRID, linecolor=_GRID,
            ticksuffix="%", tickfont=dict(size=11),
        ),
        legend=dict(
            orientation="h", y=1.01, x=0,
            xanchor="left", yanchor="bottom",
            font=dict(size=12, family=_SANS),
            bgcolor="rgba(0,0,0,0)",
        ),
        font=dict(size=12, family=_SANS, color=_TEXT_DARK),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#FDFBF8", bordercolor=_GRID,
                        font=dict(size=12, family=_SANS)),
        height=460,
        margin=dict(l=70, r=36, t=28, b=60),
    )

    plot_div = fig.to_html(full_html=False, include_plotlyjs="cdn")
    html = _card_html(
        plot_div,
        title="Army vs. Navy Share of Military Budget, 1865–1920",
        subtitle=(
            "Proportional breakdown of total appropriations between the two branches each year. "
            "The Army's dominance narrows after the Spanish-American War as naval expansion "
            "accelerates, then surges again with WWI mobilization."
        ),
    )
    output_html.write_text(html, encoding="utf-8")
