"""Plotly visualizations for BOF structured data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ── Design tokens ─────────────────────────────────────────────────────────────

_PLOT_BG    = "#EAE3D8"          # warm parchment for plot area
_GRID       = "#D6CEBF"          # subtle warm grid lines
_TEXT_DARK  = "#1A1A2E"          # near-black
_TEXT_MID   = "#55556A"          # secondary labels
_SERIF      = "Georgia, 'Times New Roman', serif"
_SANS       = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif"

_STATUS_COLORS = {
    "Approved":      "#1B5E20",   # deep forest green
    "Rejected":      "#7F1D1D",   # deep crimson
    "Investigating": "#92400E",   # amber-brown
}

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

_PROPOSER_COLORS = {
    "Government": "#1D3461",   # deep navy
    "Private":    "#B85C38",   # terra cotta
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _card_html(plot_div: str, title: str, subtitle: str, note: str = "") -> str:
    """Wrap a Plotly div in a professional styled HTML document."""
    footer_note = note or (
        "Source: BOF Annual Reports, 1897–1908 &nbsp;·&nbsp; "
        "n&nbsp;=&nbsp;1,901 proposals across 9 reporting years"
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
  <div class="eyebrow">Board of Ordnance &amp; Fortification &nbsp;·&nbsp; Historical Analysis</div>
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


# ── 1. Sankey: cluster → decision status ─────────────────────────────────────

def save_status_cluster_sankey(df: pd.DataFrame, output_html: Path) -> None:
    """Sankey diagram: technology clusters → board decision statuses."""
    edge_df = (
        df.groupby(["primary_cluster", "status"], dropna=False)
        .size()
        .reset_index(name="value")
        .query("value > 0")
    )

    cluster_totals = df["primary_cluster"].value_counts().to_dict()
    status_totals  = df["status"].value_counts().to_dict()
    grand_total    = len(df)

    left_nodes  = sorted(edge_df["primary_cluster"].astype(str).unique())
    right_nodes = sorted(edge_df["status"].astype(str).unique())

    # Labels embed proposal counts for immediate context
    left_labels  = [f"{n}  ({cluster_totals.get(n, 0):,})" for n in left_nodes]
    right_labels = [f"{n}  ({status_totals.get(n, 0):,})" for n in right_nodes]
    labels = left_labels + right_labels

    # Index by raw name so we can look up sources/targets
    raw_index = {name: i for i, name in enumerate(left_nodes + right_nodes)}

    node_colors = (
        [_CLUSTER_PALETTE.get(n, "#546E7A") for n in left_nodes]
        + [_STATUS_COLORS.get(n, "#607D8B") for n in right_nodes]
    )

    link_colors = [
        _rgba(_STATUS_COLORS.get(str(row.status), "#90A4AE"), 0.36)
        for row in edge_df.itertuples()
    ]

    hover_custom = [
        (f"{row.primary_cluster} → {row.status}<br>"
         f"{row.value:,} proposals ({row.value / grand_total * 100:.1f}% of total)")
        for row in edge_df.itertuples()
    ]

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                label=labels,
                color=node_colors,
                pad=26,
                thickness=28,
                line=dict(color="rgba(255,255,255,0.45)", width=0.7),
            ),
            link=dict(
                source=[raw_index[str(v)] for v in edge_df["primary_cluster"]],
                target=[raw_index[str(v)] for v in edge_df["status"]],
                value=edge_df["value"].tolist(),
                color=link_colors,
                customdata=hover_custom,
                hovertemplate="%{customdata}<extra></extra>",
            ),
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=13, family=_SERIF, color=_TEXT_DARK),
        margin=dict(l=8, r=8, t=8, b=8),
        height=500,
    )

    plot_div = fig.to_html(full_html=False, include_plotlyjs="cdn")
    html = _card_html(
        plot_div,
        title="Proposal Flow: Technology Cluster to Board Decision",
        subtitle=(
            "Each stream traces the volume of proposals from a technology domain to its final "
            "board disposition. Stream width is proportional to proposal count. "
            "Node labels show total proposals in each category."
        ),
    )
    output_html.write_text(html, encoding="utf-8")


# ── 2. Multi-year proposer success ───────────────────────────────────────────

def save_proposer_success_by_year(df: pd.DataFrame, output_html: Path) -> None:
    """
    Two-panel chart — top: line+area approval rate by year;
    bottom: grouped bar submission volume by year.
    Government vs. Private proposers compared side by side.
    """
    agg = (
        df[df["year"].notna() & df["proposer_type"].isin(["Government", "Private"])]
        .groupby(["year", "proposer_type"])
        .agg(submissions=("primary_cluster", "count"), approved=("is_approved", "sum"))
        .reset_index()
    )
    agg["rate_pct"] = (agg["approved"] / agg["submissions"] * 100).round(1)
    agg["year"]     = agg["year"].astype(int)
    agg             = agg.sort_values("year")
    years           = sorted(agg["year"].unique())

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.56, 0.44],
        vertical_spacing=0.08,
        subplot_titles=["", ""],   # we'll add axis titles instead
    )

    for proposer in ("Government", "Private"):
        color = _PROPOSER_COLORS[proposer]
        fill  = _rgba(color, 0.15)
        sub   = agg[agg["proposer_type"] == proposer].sort_values("year")

        # ── Top panel: line + filled area for approval rate ───────────────────
        fig.add_trace(
            go.Scatter(
                x=sub["year"],
                y=sub["rate_pct"],
                name=proposer,
                mode="lines+markers",
                line=dict(color=color, width=2.5),
                marker=dict(size=8, color=color,
                            line=dict(color="#FDFBF8", width=1.5)),
                fill="tozeroy",
                fillcolor=fill,
                connectgaps=False,
                hovertemplate=(
                    f"<b>{proposer}</b><br>"
                    "Year: %{x}<br>"
                    "Approval rate: %{y:.1f}%<br>"
                    "<extra></extra>"
                ),
            ),
            row=1, col=1,
        )

        # ── Bottom panel: bars for submission volume ──────────────────────────
        fig.add_trace(
            go.Bar(
                x=sub["year"],
                y=sub["submissions"],
                name=proposer,
                marker=dict(
                    color=_rgba(color, 0.82),
                    line=dict(color=color, width=1),
                ),
                showlegend=False,
                hovertemplate=(
                    f"<b>{proposer}</b><br>"
                    "Year: %{x}<br>"
                    "Submissions: %{y:,}<br>"
                    "<extra></extra>"
                ),
            ),
            row=2, col=1,
        )

    # Annotation: 1901 spike
    gov_1901 = agg[(agg["year"] == 1901) & (agg["proposer_type"] == "Government")]
    prv_1901 = agg[(agg["year"] == 1901) & (agg["proposer_type"] == "Private")]
    if not prv_1901.empty:
        fig.add_annotation(
            x=1901,
            y=float(prv_1901["rate_pct"].iloc[0]) + 1.8,
            text=(
                f"<b>1901 peak</b><br>"
                f"Private: {float(prv_1901['rate_pct'].iloc[0]):.1f}%<br>"
                f"Gov't: {float(gov_1901['rate_pct'].iloc[0]) if not gov_1901.empty else 'n/a'}%"
            ),
            showarrow=True,
            arrowhead=2,
            arrowcolor=_TEXT_MID,
            arrowwidth=1.2,
            ax=52, ay=-46,
            bgcolor="#FDFBF8",
            bordercolor=_TEXT_MID,
            borderwidth=1,
            borderpad=5,
            font=dict(size=11, color=_TEXT_DARK, family=_SANS),
            xref="x", yref="y",
        )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=_PLOT_BG,
        barmode="group",
        bargap=0.20,
        bargroupgap=0.06,
        legend=dict(
            orientation="h",
            y=1.04, x=0,
            xanchor="left", yanchor="bottom",
            font=dict(size=12, family=_SANS),
            bgcolor="rgba(0,0,0,0)",
        ),
        font=dict(size=12, family=_SANS, color=_TEXT_DARK),
        height=560,
        margin=dict(l=68, r=36, t=16, b=56),
        hoverlabel=dict(bgcolor="#FDFBF8", bordercolor=_GRID,
                        font=dict(size=12, family=_SANS)),
    )

    # Axes
    fig.update_xaxes(
        tickvals=years, ticktext=[str(y) for y in years],
        tickangle=0, gridcolor=_GRID, linecolor=_GRID,
        tickfont=dict(size=11),
    )
    fig.update_yaxes(
        title_text="Approval Rate (%)", title_font=dict(size=11),
        gridcolor=_GRID, linecolor=_GRID,
        ticksuffix="%", tickfont=dict(size=11),
        row=1, col=1,
    )
    fig.update_yaxes(
        title_text="Submissions", title_font=dict(size=11),
        gridcolor=_GRID, linecolor=_GRID,
        tickfont=dict(size=11),
        row=2, col=1,
    )
    fig.update_xaxes(title_text="Fiscal Year", title_font=dict(size=11), row=2, col=1)

    plot_div = fig.to_html(full_html=False, include_plotlyjs="cdn")
    html = _card_html(
        plot_div,
        title="Government vs. Private Proposal Success, 1897–1907",
        subtitle=(
            "Top panel: percentage of proposals approved each year, by proposer type. "
            "Bottom panel: total submission volume. "
            "Years 1899, 1902, and 1905 have no data — line breaks indicate genuine gaps."
        ),
    )
    output_html.write_text(html, encoding="utf-8")


# ── 3. 1901 cluster approval rates ───────────────────────────────────────────

def save_ratio_dashboard_1901(df: pd.DataFrame, output_html: Path) -> None:
    """Horizontal bar chart of 1901 approval rates with a reference line and rich labels."""
    df_1901 = df[df["year"] == 1901]
    ratio = (
        df_1901
        .groupby("primary_cluster", dropna=False)
        .agg(submissions=("primary_cluster", "count"), approved=("is_approved", "sum"))
        .reset_index()
    )
    ratio["rate_pct"] = (ratio["approved"] / ratio["submissions"] * 100).round(1)
    ratio = ratio.sort_values("rate_pct", ascending=True)

    overall_rate = (
        df_1901["is_approved"].sum() / len(df_1901) * 100
        if len(df_1901) > 0 else 0
    )
    max_rate  = ratio["rate_pct"].max() or 1.0
    x_ceiling = max_rate * 1.65

    # ── Bar colors: continuous red→amber→green scale mapped to rate ───────────
    def _rate_color(rate: float) -> str:
        t = min(rate / max_rate, 1.0)
        if t < 0.35:
            # red → amber
            s = t / 0.35
            r = int(127 + (180 - 127) * s)
            g = int(29  + (100 - 29 ) * s)
            b = int(29  + (10  - 29 ) * s)
        else:
            # amber → green
            s = (t - 0.35) / 0.65
            r = int(180 + (27  - 180) * s)
            g = int(100 + (94  - 100) * s)
            b = int(10  + (32  - 10 ) * s)
        return f"rgb({r},{g},{b})"

    bar_colors = [_rate_color(v) for v in ratio["rate_pct"]]

    fig = go.Figure()

    # Submission-volume ghost bars (light backdrop showing total volume)
    fig.add_trace(
        go.Bar(
            x=ratio["submissions"] / ratio["submissions"].max() * x_ceiling * 0.90,
            y=ratio["primary_cluster"],
            orientation="h",
            marker=dict(color="rgba(180,170,155,0.18)", line=dict(width=0)),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # Main approval-rate bars
    fig.add_trace(
        go.Bar(
            x=ratio["rate_pct"],
            y=ratio["primary_cluster"],
            orientation="h",
            marker=dict(
                color=bar_colors,
                line=dict(color="rgba(255,255,255,0.5)", width=0.6),
            ),
            text=[
                f"  <b>{row.rate_pct:.1f}%</b>  <span style='color:#55556A'>({int(row.approved)}/{int(row.submissions)})</span>"
                for row in ratio.itertuples()
            ],
            textposition="outside",
            textfont=dict(size=12, family=_SANS),
            cliponaxis=False,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Approval rate: %{x:.1f}%<br>"
                "<extra></extra>"
            ),
            showlegend=False,
        )
    )

    # Overall average reference line
    fig.add_vline(
        x=overall_rate,
        line=dict(color=_rgba(_TEXT_DARK, 0.50), width=1.4, dash="dot"),
    )
    fig.add_annotation(
        x=overall_rate,
        y=len(ratio) - 0.1,
        text=f"  Overall avg: {overall_rate:.1f}%",
        showarrow=False,
        xanchor="left",
        font=dict(size=11, color=_TEXT_MID, family=_SANS),
        bgcolor="rgba(0,0,0,0)",
    )

    # Ghost bar legend (explain the backdrop)
    fig.add_annotation(
        x=x_ceiling * 0.97,
        y=-0.75,
        text="Shaded backdrop = relative submission volume",
        showarrow=False,
        xanchor="right",
        font=dict(size=10.5, color=_TEXT_MID, family=_SANS),
    )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=_PLOT_BG,
        barmode="overlay",
        xaxis=dict(
            title="Approval Rate (%)",
            title_font=dict(size=11, family=_SANS),
            range=[0, x_ceiling],
            gridcolor=_GRID,
            linecolor=_GRID,
            zeroline=True,
            zerolinecolor=_rgba(_TEXT_DARK, 0.25),
            ticksuffix="%",
            tickfont=dict(size=11),
        ),
        yaxis=dict(
            tickfont=dict(size=12, family=_SERIF),
            gridcolor="rgba(0,0,0,0)",
            linecolor=_GRID,
        ),
        font=dict(size=12, family=_SANS, color=_TEXT_DARK),
        height=430,
        margin=dict(l=210, r=50, t=16, b=52),
        hoverlabel=dict(bgcolor="#FDFBF8", bordercolor=_GRID,
                        font=dict(size=12, family=_SANS)),
    )

    total_1901  = len(df_1901)
    total_appr  = int(df_1901["is_approved"].sum())
    plot_div = fig.to_html(full_html=False, include_plotlyjs="cdn")
    html = _card_html(
        plot_div,
        title="1901: Approval Rate by Technology Cluster",
        subtitle=(
            f"Of {total_1901:,} proposals submitted in fiscal year 1901, "
            f"{total_appr} were approved ({overall_rate:.1f}% overall). "
            "Bar length shows approval rate; shaded backdrop reflects each cluster's share of total submissions."
        ),
        note=(
            "Source: BOF Annual Report 1901–1902 &nbsp;·&nbsp; "
            f"n&nbsp;=&nbsp;{total_1901:,} proposals &nbsp;·&nbsp; "
            f"Labels show approved / total submitted"
        ),
    )
    output_html.write_text(html, encoding="utf-8")
