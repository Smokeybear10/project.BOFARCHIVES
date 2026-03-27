"""Budget visualizations for BOF Military Budgets, 1865-1920."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

_FONT = "Georgia, 'Times New Roman', serif"

_BRANCH_COLORS = {
    "Army": {"fill": "rgba(21,101,192,0.55)", "line": "#1565C0"},
    "Navy": {"fill": "rgba(0,105,92,0.55)",   "line": "#00695C"},
}

# Key historical events to annotate on time-series charts
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


# ── 1. Stacked area chart ─────────────────────────────────────────────────────

def save_budget_area_chart(df: pd.DataFrame, output_html: Path) -> None:
    """
    Stacked area chart: Army + Navy appropriations 1865-1920.
    Includes toggle buttons for nominal vs. 2025-inflation-adjusted dollars
    and vertical annotations for key historical events.
    """
    branches = ["Navy", "Army"]  # Navy on bottom so Army stacks on top visually

    # Build one trace per branch per dollar mode
    # We'll use updatemenus to toggle visibility
    traces_nominal: list[go.Scatter] = []
    traces_adjusted: list[go.Scatter] = []

    for branch in branches:
        sub = df[df["branch"] == branch].sort_values("year")
        colors = _BRANCH_COLORS[branch]

        traces_nominal.append(
            go.Scatter(
                x=sub["year"],
                y=sub["appropriation_usd"],
                name=branch,
                stackgroup="nominal",
                fillcolor=colors["fill"],
                line=dict(color=colors["line"], width=1.5),
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
                line=dict(color=colors["line"], width=1.5),
                hovertemplate=(
                    f"<b>{branch}</b><br>"
                    "Year: %{x}<br>"
                    "2025 Value: %{customdata}<extra></extra>"
                ),
                customdata=[_fmt_billions(v) for v in sub["appropriation_2025_usd"]],
                visible=False,
            )
        )

    all_traces = traces_nominal + traces_adjusted
    n = len(branches)

    # Toggle: show nominal traces, hide adjusted (and vice-versa)
    vis_nominal  = [True] * n + [False] * n
    vis_adjusted = [False] * n + [True] * n

    fig = go.Figure(data=all_traces)

    # Event annotation shapes + labels
    shapes, annotations = [], []
    ymax_nominal = df.groupby("year")["appropriation_usd"].sum().max()
    for year, label in _EVENTS:
        shapes.append(dict(
            type="line", x0=year, x1=year, y0=0, y1=ymax_nominal * 1.05,
            line=dict(color="rgba(100,100,100,0.5)", width=1.2, dash="dot"),
            layer="below",
        ))
        annotations.append(dict(
            x=year, y=ymax_nominal * 1.07,
            text=label, showarrow=False,
            font=dict(size=10, color="#555555", family=_FONT),
            xanchor="center",
        ))

    fig.update_layout(
        title=dict(
            text="U.S. Military Appropriations, 1865–1920",
            font=dict(size=18, color="#212121", family=_FONT),
            x=0.5, xanchor="center",
        ),
        updatemenus=[dict(
            type="buttons",
            direction="right",
            x=0.5, xanchor="center",
            y=1.08, yanchor="top",
            showactive=True,
            buttons=[
                dict(label="Nominal Dollars",
                     method="update",
                     args=[{"visible": vis_nominal},
                           {"yaxis.title.text": "Appropriation (Nominal $)"}]),
                dict(label="2025 Inflation-Adjusted",
                     method="update",
                     args=[{"visible": vis_adjusted},
                           {"yaxis.title.text": "Appropriation (2025 $)"}]),
            ],
            bgcolor="#ECEFF1",
            bordercolor="#B0BEC5",
            font=dict(size=12),
        )],
        xaxis=dict(
            title="Fiscal Year",
            gridcolor="#E0E0E0",
            tickmode="linear",
            dtick=5,
        ),
        yaxis=dict(
            title="Appropriation (Nominal $)",
            gridcolor="#E0E0E0",
            tickformat="$,.0f",
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        font=dict(size=12, family=_FONT),
        paper_bgcolor="#FAFAFA",
        plot_bgcolor="#F5F5F5",
        hovermode="x unified",
        height=520,
        margin=dict(l=80, r=40, t=110, b=60),
        shapes=shapes,
        annotations=annotations,
    )
    fig.write_html(str(output_html), include_plotlyjs="cdn")


# ── 2. Treemap: spending by decade and branch ─────────────────────────────────

def save_budget_treemap(df: pd.DataFrame, output_html: Path) -> None:
    """
    Treemap showing total 2025-adjusted spending per decade × branch.
    Hierarchy: root → decade → branch.
    """
    agg = (
        df.groupby(["decade", "branch"])
        .agg(total_2025=("appropriation_2025_usd", "sum"))
        .reset_index()
    )

    branch_colors = {"Army": "#1565C0", "Navy": "#00695C"}
    decades = sorted(agg["decade"].unique())

    # Build treemap node lists
    ids, labels, parents, values, custom, colors = [], [], [], [], [], []

    # Root — value = grand total (required for branchvalues="total")
    grand_total = agg["total_2025"].sum()
    ids.append("all")
    labels.append("Total Military Spending")
    parents.append("")
    values.append(grand_total)
    custom.append(_fmt_billions(grand_total))
    colors.append("#ECEFF1")

    # Decade nodes — value = sum of their children
    for decade in decades:
        decade_total = agg[agg["decade"] == decade]["total_2025"].sum()
        ids.append(decade)
        labels.append(decade)
        parents.append("all")
        values.append(decade_total)
        custom.append(_fmt_billions(decade_total))
        colors.append("#B0BEC5")

    # Branch leaf nodes
    for decade in decades:
        for _, row in agg[agg["decade"] == decade].iterrows():
            node_id = f"{row['decade']}_{row['branch']}"
            ids.append(node_id)
            labels.append(row["branch"])
            parents.append(decade)
            values.append(row["total_2025"])
            custom.append(_fmt_billions(row["total_2025"]))
            colors.append(branch_colors.get(row["branch"], "#607D8B"))

    fig = go.Figure(
        go.Treemap(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            customdata=custom,
            texttemplate="<b>%{label}</b><br>%{customdata}",
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Total (2025 $): %{customdata}<br>"
                "<extra></extra>"
            ),
            marker=dict(
                colors=colors,
                line=dict(width=1.5, color="white"),
            ),
            branchvalues="total",
            maxdepth=3,
        )
    )
    fig.update_layout(
        title=dict(
            text="U.S. Military Budget by Decade, 1865–1920  (2025-Adjusted Dollars)",
            font=dict(size=17, color="#212121", family=_FONT),
            x=0.5, xanchor="center",
        ),
        font=dict(size=13, family=_FONT),
        paper_bgcolor="#FAFAFA",
        height=560,
        margin=dict(l=20, r=20, t=70, b=20),
    )
    fig.write_html(str(output_html), include_plotlyjs="cdn")


# ── 3. Army vs Navy share — proportional area chart ──────────────────────────

def save_budget_share_chart(df: pd.DataFrame, output_html: Path) -> None:
    """
    100 % stacked area chart showing the Army/Navy share of total spending by year.
    Highlights shifting strategic priorities over the period.
    """
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
    for branch, col, color_fill, color_line in [
        ("Navy", "navy_pct", "rgba(0,105,92,0.6)",   "#00695C"),
        ("Army", "army_pct", "rgba(21,101,192,0.6)", "#1565C0"),
    ]:
        fig.add_trace(
            go.Scatter(
                x=pivot["year"],
                y=pivot[col],
                name=branch,
                stackgroup="share",
                fillcolor=color_fill,
                line=dict(color=color_line, width=1.5),
                hovertemplate=(
                    f"<b>{branch}</b><br>"
                    "Year: %{x}<br>"
                    "Share: %{y:.1f}%<extra></extra>"
                ),
            )
        )

    # Add event lines
    for year, label in _EVENTS:
        fig.add_vline(
            x=year,
            line=dict(color="rgba(100,100,100,0.5)", width=1.2, dash="dot"),
        )
        fig.add_annotation(
            x=year, y=105,
            text=label, showarrow=False,
            font=dict(size=10, color="#555555", family=_FONT),
            xanchor="center",
        )

    fig.update_layout(
        title=dict(
            text="Army vs. Navy Share of Military Budget, 1865–1920",
            font=dict(size=17, color="#212121", family=_FONT),
            x=0.5, xanchor="center",
        ),
        xaxis=dict(title="Fiscal Year", gridcolor="#E0E0E0", dtick=5),
        yaxis=dict(
            title="Share of Total Budget (%)",
            range=[0, 115],
            gridcolor="#E0E0E0",
            ticksuffix="%",
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        font=dict(size=12, family=_FONT),
        paper_bgcolor="#FAFAFA",
        plot_bgcolor="#F5F5F5",
        hovermode="x unified",
        height=460,
        margin=dict(l=70, r=40, t=90, b=60),
    )
    fig.write_html(str(output_html), include_plotlyjs="cdn")
