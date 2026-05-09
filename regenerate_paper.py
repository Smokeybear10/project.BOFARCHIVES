"""Regenerate dashboard charts with Paper-theme tokens.

Monkey-patches the bof_pipeline visualize modules to swap parchment palette
for the Paper theme (Stripe-style: white panels, indigo accent, Inter sans).
Writes new HTML wrappers to prototypes/dashboard/charts/.

Usage:  .venv/bin/python prototypes/dashboard/regenerate_paper.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT))

import plotly.graph_objects as go

from bof_pipeline import visualize as v
from bof_pipeline import budget_visualize as bv
from bof_pipeline import combined_visualize as cv

# Capture the last figure built via .to_html() so we can also export a PNG.
_last_fig: go.Figure | None = None
_original_to_html = go.Figure.to_html

def _to_html_capture(self, *args, **kwargs):
    global _last_fig
    _last_fig = self
    return _original_to_html(self, *args, **kwargs)

go.Figure.to_html = _to_html_capture


def _save_png_for_last_fig(out_html: Path, width: int = 1200, height: int = 720) -> Path | None:
    if _last_fig is None:
        return None
    png = out_html.with_suffix(".png")
    try:
        _last_fig.write_image(str(png), width=width, height=height, scale=2)
        return png
    except Exception as e:
        print(f"  PNG export skipped for {out_html.name}: {e}")
        return None

# ── Paper palette ─────────────────────────────────────────────────────
P_BG       = "#FFFFFF"
P_BG_PAGE  = "#F6F6F7"
P_GRID     = "#E1E3E6"
P_TEXT     = "#1A1F36"
P_TEXT_MID = "#5A6075"
P_TEXT_SOFT= "#8C92A4"
P_ACCENT   = "#635BFF"
P_AMBER    = "#B45309"
P_GREEN    = "#0E7C66"
P_RED      = "#B91C1C"
P_BLUE     = "#0570DE"
P_PURPLE   = "#9333EA"

P_SANS = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"

# Cluster palette tuned for white background (deeper, more saturated)
P_CLUSTERS = {
    "Artillery":                      "#0570DE",
    "Explosives":                     "#9333EA",
    "Small Arms":                     "#0E7C66",
    "Armor and Protection":           "#B45309",
    "Fortification and Engineering":  "#15803D",
    "Communications and Observation": "#4F46E5",
    "Logistics and Support":          "#B91C1C",
    "Other/Unclassified":             "#697386",
}

P_STATUS = {
    "Approved":      P_GREEN,
    "Rejected":      P_RED,
    "Investigating": P_AMBER,
}

P_PROPOSER = {
    "Government": P_ACCENT,
    "Private":    "#C2410C",
}

P_BRANCH = {
    "Army": {"fill": "rgba(99,91,255,0.18)",   "line": P_ACCENT},
    "Navy": {"fill": "rgba(14,124,102,0.20)",  "line": P_GREEN},
}


# ── Paper-themed card wrapper ─────────────────────────────────────────
def _paper_card_html(plot_div: str, title: str, subtitle: str, note: str = "") -> str:
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{
    font-family:{P_SANS};
    background:{P_BG_PAGE};
    color:{P_TEXT};
    min-height:100vh;
    display:flex;
    align-items:flex-start;
    justify-content:center;
    padding:48px 20px 64px;
    -webkit-font-smoothing:antialiased;
  }}
  .card{{
    width:100%;
    max-width:1080px;
    background:{P_BG};
    border:1px solid {P_GRID};
    border-radius:8px;
    box-shadow:0 1px 2px rgba(15,23,42,0.04),0 1px 1px rgba(15,23,42,0.03);
    padding:32px 36px 20px;
  }}
  .eyebrow{{
    font-size:11px;font-weight:600;letter-spacing:0.8px;text-transform:uppercase;
    color:{P_ACCENT};margin-bottom:14px;
  }}
  h1{{
    font-family:{P_SANS};font-size:22px;font-weight:600;color:{P_TEXT};
    line-height:1.3;letter-spacing:-0.3px;margin-bottom:8px;
  }}
  .sub{{
    font-size:13.5px;color:{P_TEXT_MID};line-height:1.55;margin-bottom:22px;max-width:760px;
  }}
  .rule{{height:1px;background:{P_GRID};margin:0 0 18px;}}
  .footer{{
    margin-top:14px;padding-top:14px;border-top:1px solid {P_GRID};
    display:flex;justify-content:space-between;align-items:center;gap:12px;
  }}
  .src{{font-size:11px;color:{P_TEXT_SOFT};line-height:1.5}}
  .badge{{
    font-size:10px;font-weight:600;letter-spacing:0.6px;color:{P_BG};
    background:{P_ACCENT};padding:4px 10px;border-radius:4px;
    white-space:nowrap;flex-shrink:0;
  }}
</style>
</head>
<body>
<div class="card">
  <div class="eyebrow">Board of Ordnance &amp; Fortification &nbsp;·&nbsp; Archive</div>
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


# ── Patch modules ─────────────────────────────────────────────────────
def patch_modules():
    """Override the design tokens on each visualize module in-place."""
    for module in (v, bv, cv):
        module._PLOT_BG = P_BG
        module._GRID = P_GRID
        module._TEXT_DARK = P_TEXT
        module._TEXT_MID = P_TEXT_MID
        module._SERIF = P_SANS
        module._SANS = P_SANS
        module._card_html = _paper_card_html

    # Module-specific tables
    v._STATUS_COLORS = P_STATUS
    v._CLUSTER_PALETTE = P_CLUSTERS
    v._PROPOSER_COLORS = P_PROPOSER
    cv._CLUSTER_PALETTE = P_CLUSTERS
    bv._BRANCH_COLORS = P_BRANCH


# ── Generate ──────────────────────────────────────────────────────────
def main():
    patch_modules()

    out_dir = Path(__file__).resolve().parent / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)

    proposals = pd.read_csv(PROJECT / "output" / "all_structured_records.csv")
    budget = pd.read_csv(PROJECT / "output" / "budget_master_ledger.csv")

    targets = []

    def _gen(fn, name, *args, w=1200, h=720, **kwargs):
        p = out_dir / f"{name}.html"
        fn(*args, p, **kwargs)
        targets.append(p)
        png = _save_png_for_last_fig(p, width=w, height=h)
        if png is not None:
            targets.append(png)

    # ── Budget charts ──
    _gen(bv.save_budget_area_chart, "budget_area", budget, w=1200, h=560)
    _gen(bv.save_budget_treemap, "budget_treemap", budget, w=1200, h=620)
    _gen(bv.save_budget_share_chart, "budget_share", budget, w=1200, h=560)

    # ── Proposal charts ──
    _gen(v.save_status_cluster_sankey, "proposal_sankey", proposals, w=1200, h=620)
    _gen(v.save_proposer_success_by_year, "proposal_success", proposals, w=1200, h=720)
    _gen(v.save_ratio_dashboard_1901, "proposal_1901", proposals, w=1200, h=560)

    # ── Combined charts (these support thumbnail_png) ──
    p = out_dir / "investment.html"
    png = out_dir / "investment.png"
    cv.save_investment_by_technology(proposals, budget, p, thumbnail_png=png)
    targets.extend([p, png])

    # ── Decision distribution per cluster (custom) ──
    p = out_dir / "decision_per_cluster.html"
    save_decision_per_cluster(proposals, p)
    targets.append(p)
    if p.with_suffix(".png").exists():
        targets.append(p.with_suffix(".png"))

    print(f"\nWrote {len(targets)} files to {out_dir}:")
    for t in targets:
        print(f"  {t.name}  ({t.stat().st_size // 1024} KB)")


def save_decision_per_cluster(df: pd.DataFrame, out_path: Path) -> None:
    """Stacked horizontal bars: decision-status share within each cluster."""
    work = df.dropna(subset=["primary_cluster"]).copy()

    def bucket(s):
        if not isinstance(s, str): return "Other"
        x = s.lower()
        if "approv" in x or "adopt" in x: return "Approved"
        if "reject" in x or "not recommend" in x: return "Rejected"
        if "investigat" in x or "test" in x or "allotment" in x: return "Investigating"
        return "Other"

    work["bucket"] = work["status"].apply(bucket)
    pivot = work.groupby(["primary_cluster", "bucket"]).size().unstack(fill_value=0)
    statuses = ["Approved", "Investigating", "Rejected", "Other"]
    for s in statuses:
        if s not in pivot.columns:
            pivot[s] = 0
    pivot = pivot[statuses]
    pivot["total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("total", ascending=True)
    pct = pivot[statuses].div(pivot["total"], axis=0) * 100

    bucket_color = {
        "Approved":      P_GREEN,
        "Investigating": P_AMBER,
        "Rejected":      P_RED,
        "Other":         P_TEXT_SOFT,
    }

    fig = go.Figure()
    for s in statuses:
        fig.add_bar(
            y=pct.index,
            x=pct[s],
            name=s,
            orientation="h",
            marker=dict(color=bucket_color[s], line=dict(width=0)),
            customdata=pivot[[s, "total"]].values,
            hovertemplate=f"<b>%{{y}}</b><br>{s}: %{{customdata[0]:,}} of %{{customdata[1]:,}} (%{{x:.1f}}%)<extra></extra>",
        )

    fig.update_layout(
        barmode="stack",
        paper_bgcolor=P_BG,
        plot_bgcolor=P_BG,
        font=dict(family=P_SANS, size=12, color=P_TEXT),
        margin=dict(l=180, r=40, t=20, b=70),
        height=440,
        legend=dict(orientation="h", yanchor="bottom", y=-0.22, xanchor="left", x=0,
                    font=dict(size=11, color=P_TEXT_MID), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(range=[0, 100], ticksuffix="%", showgrid=True, gridcolor=P_GRID,
                   zeroline=False, color=P_TEXT_MID, tickfont=dict(size=11)),
        yaxis=dict(color=P_TEXT, tickfont=dict(size=12), showgrid=False),
    )

    plot_div = fig.to_html(include_plotlyjs="cdn", full_html=False, config={"displayModeBar": False})
    title = "Decision Distribution by Technology Cluster"
    subtitle = ("Stacked share of board decisions within each cluster. The Board overwhelmingly "
                "deferred proposals into <em>Investigating</em>; outright approvals concentrate in "
                "Artillery, Explosives, and the residual <em>Other</em> bucket.")
    out_path.write_text(_paper_card_html(plot_div, title, subtitle))
    try:
        fig.write_image(str(out_path.with_suffix(".png")), width=1200, height=560, scale=2)
    except Exception as e:
        print(f"  PNG export skipped: {e}")


if __name__ == "__main__":
    main()
