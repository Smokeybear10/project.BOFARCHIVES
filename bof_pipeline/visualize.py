"""Plotly visualizations for BOF structured data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ── Shared color palette ──────────────────────────────────────────────────────

_STATUS_COLORS = {
    "Approved": "#2E7D32",       # forest green
    "Rejected": "#B71C1C",       # deep red
    "Investigating": "#E65100",  # burnt orange
}

_CLUSTER_COLORS = [
    "#1A237E",  # deep indigo
    "#4527A0",  # purple
    "#00695C",  # teal
    "#1565C0",  # blue
    "#558B2F",  # olive
    "#6D4C41",  # brown
    "#00838F",  # cyan-teal
    "#37474F",  # dark blue-gray
]

_FONT = "Georgia, 'Times New Roman', serif"


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ── 1. Sankey: cluster → decision status ─────────────────────────────────────

def save_status_cluster_sankey(df: pd.DataFrame, output_html: Path) -> None:
    """Sankey diagram showing how technology clusters flow to board decisions."""
    edge_df = (
        df.groupby(["primary_cluster", "status"], dropna=False)
        .size()
        .reset_index(name="value")
        .query("value > 0")
    )

    left_nodes = sorted(edge_df["primary_cluster"].astype(str).unique())
    right_nodes = sorted(edge_df["status"].astype(str).unique())
    labels = left_nodes + right_nodes
    index = {label: i for i, label in enumerate(labels)}

    # Node colors: clusters get palette colors, statuses get semantic colors
    node_colors = []
    for i, label in enumerate(labels):
        if label in _STATUS_COLORS:
            node_colors.append(_STATUS_COLORS[label])
        else:
            node_colors.append(_CLUSTER_COLORS[i % len(_CLUSTER_COLORS)])

    # Link colors: tinted by destination status, semi-transparent
    link_colors = [
        _hex_to_rgba(_STATUS_COLORS.get(str(row.status), "#90A4AE"), 0.40)
        for row in edge_df.itertuples()
    ]

    sources = [index[str(v)] for v in edge_df["primary_cluster"]]
    targets = [index[str(v)] for v in edge_df["status"]]

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                label=labels,
                color=node_colors,
                pad=22,
                thickness=24,
                line=dict(color="rgba(255,255,255,0.6)", width=0.8),
            ),
            link=dict(
                source=sources,
                target=targets,
                value=edge_df["value"].tolist(),
                color=link_colors,
                hovertemplate=(
                    "<b>%{source.label}</b> → <b>%{target.label}</b><br>"
                    "Proposals: %{value:,}<extra></extra>"
                ),
            ),
        )
    )
    fig.update_layout(
        title=dict(
            text="Board of Ordnance & Fortification — Proposal Flow by Technology Cluster",
            font=dict(size=17, color="#212121", family=_FONT),
            x=0.5,
            xanchor="center",
        ),
        font=dict(size=13, family=_FONT),
        paper_bgcolor="#FAFAFA",
        margin=dict(l=20, r=20, t=65, b=20),
        height=520,
    )
    fig.write_html(str(output_html), include_plotlyjs="cdn")


# ── 2. Multi-year proposer success (replaces the network graph) ───────────────

def save_proposer_success_by_year(df: pd.DataFrame, output_html: Path) -> None:
    """
    Two-panel chart: approval rate % and submission volume,
    both broken out by year and proposer type (Government vs Private).
    """
    agg = (
        df[df["year"].notna() & df["proposer_type"].isin(["Government", "Private"])]
        .groupby(["year", "proposer_type"])
        .agg(submissions=("primary_cluster", "count"), approved=("is_approved", "sum"))
        .reset_index()
    )
    agg["rate_pct"] = (agg["approved"] / agg["submissions"] * 100).round(1)
    agg["year"] = agg["year"].astype(int)
    agg = agg.sort_values("year")

    _PROPOSER_COLORS = {"Government": "#1565C0", "Private": "#E65100"}

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        subplot_titles=("Approval Rate (%)", "Total Submissions"),
        vertical_spacing=0.10,
        row_heights=[0.58, 0.42],
    )

    for proposer, color in _PROPOSER_COLORS.items():
        subset = agg[agg["proposer_type"] == proposer]

        # Top panel: approval rate bars
        fig.add_trace(
            go.Bar(
                x=subset["year"],
                y=subset["rate_pct"],
                name=proposer,
                marker_color=color,
                text=subset["rate_pct"].apply(lambda v: f"{v:.1f}%"),
                textposition="outside",
                textfont=dict(size=10, color="#424242"),
                hovertemplate=(
                    f"<b>{proposer}</b><br>"
                    "Year: %{x}<br>"
                    "Approval rate: %{y:.1f}%<br>"
                    "<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

        # Bottom panel: submission volume bars
        fig.add_trace(
            go.Bar(
                x=subset["year"],
                y=subset["submissions"],
                name=proposer,
                marker_color=color,
                opacity=0.70,
                showlegend=False,
                hovertemplate=(
                    f"<b>{proposer}</b><br>"
                    "Year: %{x}<br>"
                    "Submissions: %{y:,}<br>"
                    "<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )

    years = sorted(agg["year"].unique())
    fig.update_layout(
        title=dict(
            text="Government vs. Private Proposal Success, 1897–1907",
            font=dict(size=17, color="#212121", family=_FONT),
            x=0.5,
            xanchor="center",
        ),
        barmode="group",
        bargap=0.18,
        bargroupgap=0.06,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=12),
        ),
        font=dict(size=12, family=_FONT),
        paper_bgcolor="#FAFAFA",
        plot_bgcolor="#F5F5F5",
        height=580,
        margin=dict(l=60, r=40, t=80, b=60),
    )
    fig.update_xaxes(
        tickvals=years,
        ticktext=[str(y) for y in years],
        tickangle=0,
        gridcolor="#E0E0E0",
        row=2,
        col=1,
    )
    fig.update_xaxes(gridcolor="#E0E0E0", row=1, col=1)
    fig.update_yaxes(title_text="Approval Rate (%)", gridcolor="#E0E0E0", row=1, col=1)
    fig.update_yaxes(title_text="Submissions", gridcolor="#E0E0E0", row=2, col=1)

    fig.write_html(str(output_html), include_plotlyjs="cdn")


# ── 3. Horizontal bar chart: 1901 cluster approval rates ─────────────────────

def save_ratio_dashboard_1901(df: pd.DataFrame, output_html: Path) -> None:
    """Horizontal bar chart of 1901 approval rates with inline approved/total labels."""
    ratio = (
        df[df["year"] == 1901]
        .groupby("primary_cluster", dropna=False)
        .agg(submissions=("primary_cluster", "count"), approved=("is_approved", "sum"))
        .reset_index()
    )
    ratio["rate_pct"] = (ratio["approved"] / ratio["submissions"] * 100).round(1)
    ratio = ratio.sort_values("rate_pct", ascending=True)  # ascending → tallest bar on top

    max_rate = ratio["rate_pct"].max() or 1.0

    fig = go.Figure(
        go.Bar(
            x=ratio["rate_pct"],
            y=ratio["primary_cluster"],
            orientation="h",
            marker=dict(
                color=ratio["rate_pct"],
                colorscale=[
                    [0.00, "#B71C1C"],
                    [0.25, "#E65100"],
                    [0.60, "#F9A825"],
                    [1.00, "#2E7D32"],
                ],
                cmin=0,
                cmax=max_rate,
                colorbar=dict(
                    title=dict(text="Approval<br>Rate (%)", font=dict(size=11)),
                    len=0.65,
                    thickness=14,
                ),
                line=dict(color="rgba(255,255,255,0.4)", width=0.5),
            ),
            text=[
                f"  {row.rate_pct:.1f}%   ({int(row.approved)}/{int(row.submissions)})"
                for row in ratio.itertuples()
            ],
            textposition="outside",
            textfont=dict(size=12, color="#424242"),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Approval rate: %{x:.1f}%<br>"
                "<extra></extra>"
            ),
            cliponaxis=False,
        )
    )
    fig.update_layout(
        title=dict(
            text="1901 Board of Ordnance — Approval Rate by Technology Cluster",
            font=dict(size=17, color="#212121", family=_FONT),
            x=0.5,
            xanchor="center",
        ),
        xaxis=dict(
            title="Approval Rate (%)",
            range=[0, max_rate * 1.55],
            gridcolor="#E0E0E0",
            zeroline=True,
            zerolinecolor="#BDBDBD",
        ),
        yaxis=dict(title=""),
        font=dict(size=13, family=_FONT),
        paper_bgcolor="#FAFAFA",
        plot_bgcolor="#F5F5F5",
        height=400,
        margin=dict(l=220, r=60, t=70, b=60),
    )
    fig.write_html(str(output_html), include_plotlyjs="cdn")
