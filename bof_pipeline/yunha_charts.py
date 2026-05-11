"""Financial × Technology Investment Analysis — Yunha · 1888-1918.

Three views of how BOF dollars flowed into different technology areas,
built directly off the master 1888-1918 allotment ledger and the 1897-1908
subjects-considered records.

The classifier reuses the project's existing TECHNOLOGY_CLUSTER_PATTERNS
(seven categories: Artillery, Explosives, Small Arms, Armor & Protection,
Fortification & Engineering, Communications & Observation, Logistics &
Support) so cluster taxonomy is identical across the dashboard.

Charts:
  1. save_yunha_dollars_by_cluster()      — treemap, total $ per cluster
  2. save_yunha_investment_trajectory()   — line chart, $ per cluster × year
  3. save_yunha_approval_roi()            — bubble chart, cluster size vs approval rate
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from bof_pipeline.config import TECHNOLOGY_CLUSTER_PATTERNS
from bof_pipeline.transform import _match_multiple_categories, _to_lower

# ── Design tokens ───────────────────────────────────────────────────────
_PLOT_BG = "#EAE3D8"
_GRID = "#D6CEBF"
_TEXT_DARK = "#1A1A2E"
_TEXT_MID = "#55556A"
_SERIF = "Georgia, 'Times New Roman', serif"
_SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif"

# Mirror combined_visualize.py palette so Yunha's charts read consistently
# with the existing investment_by_technology chart (which is also her).
CLUSTER_PALETTE = {
    "Artillery":                      "#1D3461",
    "Explosives":                     "#6B2D8B",
    "Small Arms":                     "#0A6E5D",
    "Armor and Protection":           "#7C4318",
    "Fortification and Engineering":  "#2D6A4F",
    "Communications and Observation": "#1B4F72",
    "Logistics and Support":          "#5D4037",
    "Other/Unclassified":             "#546E7A",
}

CLUSTER_ORDER = list(CLUSTER_PALETTE.keys())

_CREDIT = (
    "Original analysis by <b>Yunha</b> · Financial data on technology investment"
)


def _layout(title: str, subtitle: str, height: int = 540) -> dict:
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
        margin=dict(l=70, r=30, t=110, b=70),
        height=height,
        hoverlabel=dict(bgcolor="#FFF8EC", bordercolor="#1D3461", font_family=_SERIF),
    )


def classify_allotments(allotments: pd.DataFrame) -> pd.DataFrame:
    """Apply the existing cluster classifier to every allotment line item.

    Adds two columns: technology_clusters (list) + primary_cluster (str).
    Reuses the same regex rules the proposals pipeline uses, so a cluster
    label means the same thing whether you're looking at a 1901 proposal
    or a 1908 allotment.
    """
    out = allotments.copy()
    out["description"] = out["description"].astype(str)
    out["technology_clusters"] = out["description"].map(
        lambda t: _match_multiple_categories(_to_lower(t), TECHNOLOGY_CLUSTER_PATTERNS)
    )
    out["primary_cluster"] = out["technology_clusters"].map(
        lambda tags: tags[0] if tags else "Other/Unclassified"
    )
    return out


# ── 1. Dollars by Cluster (treemap) ─────────────────────────────────────


def save_yunha_dollars_by_cluster(allotments: pd.DataFrame, out: Path) -> None:
    """Treemap: total dollars allotted to each technology cluster, 1888-1918."""
    classified = classify_allotments(allotments)
    classified["allotted"] = pd.to_numeric(classified["allotted"], errors="coerce").fillna(0)

    grp = (
        classified.groupby("primary_cluster")
        .agg(
            total=("allotted", "sum"),
            count=("allotted", "size"),
            revoked_n=("revoked", lambda s: int(s.fillna(False).sum())),
        )
        .reset_index()
        .sort_values("total", ascending=False)
    )
    grand = grp["total"].sum()

    labels = grp["primary_cluster"].tolist()
    parents = ["Total"] * len(labels)
    values = grp["total"].tolist()
    colors = [CLUSTER_PALETTE.get(c, "#546E7A") for c in labels]

    fig = go.Figure(go.Treemap(
        labels=labels + ["Total"],
        parents=parents + [""],
        values=values + [grand],
        branchvalues="total",
        marker=dict(
            colors=colors + ["#1A1A2E"],
            line=dict(color=_PLOT_BG, width=2),
        ),
        text=[
            f"${t:,.0f}<br>{n} line items · {r} revoked"
            for t, n, r in zip(grp["total"], grp["count"], grp["revoked_n"])
        ] + [""],
        textinfo="label+text",
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Total allotted: $%{value:,.0f}<br>"
            "%{percentParent} of grand total<extra></extra>"
        ),
        textfont=dict(family=_SERIF, size=14, color="white"),
    ))

    layout = _layout(
        "Investment Dollars by Technology Cluster",
        f"BOF allotments classified by primary technology cluster · "
        f"1888–1918 · ${grand:,.0f} total across {len(classified):,} line items",
        height=520,
    )
    fig.update_layout(**layout)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(out, include_plotlyjs="cdn", full_html=True)


# ── 2. Investment Trajectory (line chart) ───────────────────────────────


def save_yunha_investment_trajectory(allotments: pd.DataFrame, out: Path) -> None:
    """Annual line chart: $ allotted to each cluster, 1888-1918."""
    classified = classify_allotments(allotments)
    classified["allotted"] = pd.to_numeric(classified["allotted"], errors="coerce").fillna(0)
    classified["year"] = pd.to_numeric(classified["year"], errors="coerce")
    classified = classified.dropna(subset=["year"])
    classified["year"] = classified["year"].astype(int)

    pivot = (
        classified.groupby(["year", "primary_cluster"])["allotted"]
        .sum()
        .unstack("primary_cluster", fill_value=0)
        .sort_index()
    )

    fig = go.Figure()

    # Order traces by total descending so legend reads top-to-bottom by importance
    cluster_totals = pivot.sum().sort_values(ascending=False)
    for cluster in cluster_totals.index:
        if cluster not in CLUSTER_PALETTE:
            continue
        fig.add_trace(go.Scatter(
            x=pivot.index,
            y=pivot[cluster].values,
            name=cluster,
            mode="lines+markers",
            line=dict(color=CLUSTER_PALETTE[cluster], width=2),
            marker=dict(size=5, color=CLUSTER_PALETTE[cluster],
                        line=dict(width=1.5, color=_PLOT_BG)),
            hovertemplate=(
                f"<b>{cluster}</b><br>%{{x}}: $%{{y:,.0f}}<extra></extra>"
            ),
        ))

    # Era markers
    for x, label in [(1898, "Spanish-American War"), (1917, "U.S. enters WWI")]:
        fig.add_vline(
            x=x, line_dash="dot", line_color=_TEXT_MID, line_width=1, opacity=0.4,
            annotation_text=label,
            annotation_position="top",
            annotation_font=dict(family=_SERIF, size=10, color=_TEXT_MID),
        )

    layout = _layout(
        "Investment Trajectory by Technology Cluster",
        f"Annual dollar allotments per cluster, 1888–1918 · "
        f"sorted by total spend (legend reads top-to-bottom)",
        height=560,
    )
    layout["xaxis"] = dict(
        title="Year", tickmode="linear", dtick=2,
        gridcolor=_GRID, zerolinecolor=_GRID,
    )
    layout["yaxis"] = dict(
        title="Allotted ($, nominal)", tickformat="$,.0f",
        gridcolor=_GRID, zerolinecolor=_GRID,
    )
    layout["legend"] = dict(
        orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.02,
        bgcolor="rgba(0,0,0,0)", font=dict(size=10),
    )
    layout["margin"] = dict(l=70, r=200, t=110, b=70)
    fig.update_layout(**layout)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(out, include_plotlyjs="cdn", full_html=True)


# ── 3. Approval ROI (bubble chart) ──────────────────────────────────────


def save_yunha_approval_roi(proposals: pd.DataFrame, out: Path) -> None:
    """Bubble chart: cluster volume × approval rate.

    Each bubble is one technology cluster. X = number of proposals in that
    cluster (volume of attention), Y = approval rate (% approved), bubble
    size = number of approved proposals (absolute investment signal).
    Reveals which clusters got many proposals but few greenlights, vs.
    clusters that punched above their weight.
    """
    df = proposals[
        proposals["primary_cluster"].notna()
        & (proposals["primary_cluster"] != "Other/Unclassified")
    ].copy()

    grp = df.groupby("primary_cluster").agg(
        total=("status", "size"),
        approved=("status", lambda s: (s == "Approved").sum()),
    ).reset_index()
    grp["approval_rate"] = grp["approved"] / grp["total"] * 100
    grp = grp.sort_values("total", ascending=False)

    overall_rate = (df["status"] == "Approved").sum() / len(df) * 100

    fig = go.Figure()

    for _, row in grp.iterrows():
        cluster = row["primary_cluster"]
        color = CLUSTER_PALETTE.get(cluster, "#546E7A")
        fig.add_trace(go.Scatter(
            x=[row["total"]], y=[row["approval_rate"]],
            mode="markers+text",
            name=cluster,
            marker=dict(
                size=max(20, row["approved"] * 1.5),
                color=color,
                opacity=0.78,
                line=dict(width=2, color=_PLOT_BG),
            ),
            text=[cluster.replace(" and ", " &<br>")],
            textposition="middle center",
            textfont=dict(family=_SERIF, size=10, color="white"),
            customdata=[[row["total"], row["approved"], row["approval_rate"]]],
            hovertemplate=(
                f"<b>{cluster}</b><br>"
                "Total proposals: %{customdata[0]}<br>"
                "Approved: %{customdata[1]}<br>"
                "Approval rate: %{customdata[2]:.1f}%<extra></extra>"
            ),
            showlegend=False,
        ))

    fig.add_hline(
        y=overall_rate, line_dash="dot", line_color=_TEXT_MID, line_width=1,
        annotation_text=f"overall rate: {overall_rate:.1f}%",
        annotation_position="bottom right",
        annotation_font=dict(family=_SERIF, size=10, color=_TEXT_MID),
    )

    layout = _layout(
        "Cluster ROI · Volume vs. Approval Rate",
        f"1897–1908 subjects considered · X = total proposals (volume), "
        f"Y = approval rate (%), bubble size = # approved.",
        height=560,
    )
    layout["xaxis"] = dict(
        title="Total proposals (volume of attention)",
        gridcolor=_GRID, zerolinecolor=_GRID,
    )
    layout["yaxis"] = dict(
        title="Approval rate (%)", ticksuffix="%",
        gridcolor=_GRID, zerolinecolor=_GRID,
        range=[0, max(grp["approval_rate"].max() + 5, 25)],
    )
    layout["showlegend"] = False
    fig.update_layout(**layout)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(out, include_plotlyjs="cdn", full_html=True)


__all__ = [
    "classify_allotments",
    "save_yunha_dollars_by_cluster",
    "save_yunha_investment_trajectory",
    "save_yunha_approval_roi",
]
