"""Decision-status distribution per technology cluster — editorial inline figure."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


SRC = Path(__file__).resolve().parents[2] / "output" / "all_structured_records.csv"
OUT_DIR = Path(__file__).resolve().parent / "charts"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PAPER = "#F4EFE5"
INK = "#1A1A1A"
INK_MID = "#5A554C"
RULE = "#C9C0B0"
SERIF = "Georgia, 'Times New Roman', serif"

STATUS_COLOR = {
    "Approved":      "#2E5E3E",
    "Investigating": "#B8860B",
    "Rejected":      "#8B2E2E",
    "Other":         "#8A8074",
}

STATUS_ORDER = ["Approved", "Investigating", "Rejected", "Other"]


def load() -> pd.DataFrame:
    df = pd.read_csv(SRC)
    df = df.dropna(subset=["primary_cluster"])
    df["status_bucket"] = df["status"].apply(_bucket)
    return df


def _bucket(s: object) -> str:
    if not isinstance(s, str):
        return "Other"
    s_lower = s.lower()
    if "approv" in s_lower or "adopt" in s_lower:
        return "Approved"
    if "reject" in s_lower or "not recommend" in s_lower:
        return "Rejected"
    if "investigat" in s_lower or "test" in s_lower or "allotment" in s_lower:
        return "Investigating"
    return "Other"


def build():
    df = load()
    pivot = (
        df.groupby(["primary_cluster", "status_bucket"])
        .size()
        .unstack(fill_value=0)
    )
    for col in STATUS_ORDER:
        if col not in pivot.columns:
            pivot[col] = 0
    pivot = pivot[STATUS_ORDER]
    pivot["total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("total", ascending=True)

    pct = pivot[STATUS_ORDER].div(pivot["total"], axis=0) * 100

    fig = go.Figure()
    for status in STATUS_ORDER:
        fig.add_bar(
            y=pct.index,
            x=pct[status],
            name=status,
            orientation="h",
            marker=dict(color=STATUS_COLOR[status], line=dict(width=0)),
            customdata=pivot[[status, "total"]].values,
            hovertemplate=(
                "<b>%{y}</b><br>"
                f"{status}: "
                "%{customdata[0]:,} of %{customdata[1]:,} (%{x:.1f}%)<extra></extra>"
            ),
        )

    fig.update_layout(
        barmode="stack",
        paper_bgcolor=PAPER,
        plot_bgcolor=PAPER,
        font=dict(family=SERIF, size=13, color=INK),
        margin=dict(l=180, r=40, t=20, b=60),
        height=440,
        legend=dict(
            orientation="h",
            yanchor="bottom", y=-0.22,
            xanchor="left", x=0,
            font=dict(size=11, color=INK_MID),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            range=[0, 100],
            ticksuffix="%",
            showgrid=True,
            gridcolor=RULE,
            zeroline=False,
            color=INK_MID,
            tickfont=dict(size=11),
        ),
        yaxis=dict(
            color=INK,
            tickfont=dict(size=12),
            showgrid=False,
        ),
    )

    html_out = OUT_DIR / "decision_per_cluster.html"
    png_out = OUT_DIR / "decision_per_cluster.png"

    fig.write_html(
        html_out,
        include_plotlyjs="cdn",
        full_html=True,
        config={"displayModeBar": False},
    )
    try:
        fig.write_image(png_out, width=1200, height=560, scale=2)
    except Exception as e:
        print(f"PNG export skipped: {e}")

    print(f"wrote {html_out}")
    print(f"wrote {png_out}")
    print()
    print("Cluster totals:")
    print(pivot[["Approved", "Investigating", "Rejected", "Other", "total"]].to_string())


if __name__ == "__main__":
    build()
