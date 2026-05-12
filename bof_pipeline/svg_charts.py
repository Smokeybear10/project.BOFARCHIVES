"""Hand-rolled SVG chart generators.

Replaces Plotly across the dashboard. Every chart writes a complete HTML page
with the project's brand chrome + an inline <svg viewBox="..."> that scales
perfectly to its container. Zero JS dependency.

Hover behavior: native <title> tooltip plus CSS hover effects.

Public API (one function per chart):
  - save_pareto_svg(allotments, out, top_n=20)
  - save_master_timeline_svg(allotments, appropriations, out)
  - save_historical_events_svg(events, out)
  - save_yunha_treemap_svg(allotments, out)
  - save_yunha_trajectory_svg(allotments, out)
  - save_tanisha_stacked_bars_svg(out)
  - save_tanisha_heatmap_svg(out)
"""
from __future__ import annotations

import re
from pathlib import Path
from html import escape as h
from typing import Sequence

import pandas as pd

from bof_pipeline.config import TECHNOLOGY_CLUSTER_PATTERNS
from bof_pipeline.transform import _match_multiple_categories, _to_lower

# ── Brand tokens ────────────────────────────────────────────────────────────
PAPER       = "#EAE3D8"
PAPER_SOFT  = "#FBF6E6"
BORDER      = "#D6CEBF"
GRID        = "#D6CEBF"
TEXT_DARK   = "#1A1A2E"
TEXT_MID    = "#55556A"
TEXT_SOFT   = "#8C8273"
BRASS       = "#C9A24C"
BRASS_DARK  = "#A8852E"
VERMILLION  = "#C5483D"
STEEL       = "#6B89A8"

# Cluster palette (mirrors yunha_charts.CLUSTER_PALETTE)
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

# ── Page template ──────────────────────────────────────────────────────────

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} · Fortify the Ordnance</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><path fill-rule='evenodd' clip-rule='evenodd' d='M32 3 L42 22 L61 32 L42 42 L32 61 L22 42 L3 32 L22 22 Z M32 26 A6 6 0 1 0 32 38 A6 6 0 1 0 32 26 Z' fill='%23C9A24C'/><circle cx='32' cy='32' r='2.2' fill='%23C9A24C'/></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&display=swap" rel="stylesheet">
<style>
  html, body {{
    margin: 0;
    padding: 0;
    background: {paper};
    font-family: 'Inter', -apple-system, sans-serif;
    color: {text_dark};
  }}
  body {{
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }}
  .bof-bar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 28px;
    background: {paper_soft};
    border-bottom: 1px solid {border};
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 1.2px;
    color: {text_mid};
    flex-shrink: 0;
  }}
  .bof-bar .bof-brand {{
    display: flex; align-items: center; gap: 10px;
    color: inherit; text-decoration: none;
  }}
  .bof-bar .bof-brand svg {{
    width: 18px; height: 18px;
    color: {brass};
    transition: transform .5s cubic-bezier(.2,.8,.2,1);
  }}
  .bof-bar .bof-brand:hover svg {{ transform: rotate(45deg); }}
  .bof-bar .bof-brand strong {{
    color: {text_dark}; font-weight: 700; letter-spacing: 1.4px;
  }}
  .bof-bar a.bof-back {{
    color: {text_mid}; text-decoration: none; letter-spacing: 1.2px;
  }}
  .bof-bar a.bof-back:hover {{ color: {brass}; }}

  .chart-frame {{
    flex: 1;
    width: 100%;
    padding: 18px 32px 28px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }}
  .chart-frame svg {{
    width: 100%;
    height: auto;
    display: block;
    max-height: 100%;
    flex: 1;
  }}

  /* Shared SVG element styling */
  .chart-title {{
    font-family: 'Source Serif 4', Georgia, serif;
    font-weight: 700;
    font-size: 26px;
    fill: {text_dark};
  }}
  .chart-subtitle {{
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    fill: {text_mid};
    line-height: 1.45;
  }}
  .chart-subtitle b {{ font-weight: 700; color: {text_dark}; }}
  .axis-label {{
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    fill: {text_mid};
    letter-spacing: 0.4px;
  }}
  .tick {{
    font-family: 'Inter', sans-serif;
    font-size: 11.5px;
    fill: {text_mid};
  }}
  .grid-line {{
    stroke: {grid};
    stroke-width: 1;
  }}
  .legend-text {{
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    fill: {text_dark};
  }}
  .annot {{
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 11px;
    fill: {text_mid};
  }}
  .y-label-vert {{
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 13px;
    fill: {text_dark};
    text-anchor: end;
  }}
  .bar-value {{
    font-family: 'Inter', sans-serif;
    font-size: 12.5px;
    font-weight: 600;
    fill: {text_dark};
  }}
  .row-bar {{ transition: opacity 0.15s; }}
  .row-bar:hover {{ opacity: 0.78; cursor: pointer; }}

  /* Stacked-bar segment labels — hidden until the year column is hovered.
     Hovering the invisible column hit-rect (or any segment) reveals counts. */
  .seg-label {{
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    font-weight: 600;
    fill: white;
    paint-order: stroke;
    stroke: rgba(0, 0, 0, 0.35);
    stroke-width: 0.5px;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.12s ease-out;
  }}
  .year-total {{
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 13px;
    font-weight: 700;
    fill: {text_dark};
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.12s ease-out;
  }}
  .year-col:hover .seg-label,
  .year-col:hover .year-total {{ opacity: 1; }}
  /* Slight tint on the hovered column for visual feedback */
  .year-col:hover .seg-rect {{ filter: brightness(1.08); }}
  .year-col {{ cursor: pointer; }}

  /* Trajectory year-column hover: vertical guide + cluster value labels */
  .year-col-label,
  .year-col-val {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 600;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.12s ease-out;
  }}
  .year-col-label {{ fill: {text_dark}; font-size: 12px; letter-spacing: 0.4px; }}
  .year-col:hover .year-guide,
  .year-col:hover .year-col-label,
  .year-col:hover .year-col-val,
  .year-col:hover .year-col-bg {{ opacity: 1; }}
  .year-col:hover .year-col-bg {{ opacity: 0.95; }}

  /* Treemap tiles */
  .tm-tile {{ cursor: pointer; }}
  .tm-rect {{ transition: filter 0.12s ease-out; }}
  .tm-tile:hover .tm-rect {{ filter: brightness(0.82); }}
  .tm-tile:hover .tm-label {{ opacity: 0; transition: opacity 0.12s; }}
  .tm-tile .tm-card {{
    opacity: 0;
    transition: opacity 0.15s ease-out;
  }}
  .tm-tile:hover .tm-card {{ opacity: 1; }}

  /* Pareto row hover — rank badge + cumulative pill */
  .pareto-row {{ cursor: pointer; }}
  .pareto-bar {{ transition: filter 0.12s ease-out; }}
  .pareto-row:hover .pareto-bar {{ filter: brightness(0.88); }}
  .pareto-rank,
  .pareto-cum {{
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.12s ease-out;
  }}
  .pareto-rank {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 700;
    fill: {brass};
    letter-spacing: 0.4px;
  }}
  .pareto-row:hover .pareto-rank,
  .pareto-row:hover .pareto-cum {{ opacity: 1; }}

  /* Master timeline year-column hover card */
  .mt-col {{ cursor: pointer; }}
  .mt-card,
  .mt-guide {{
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.12s ease-out;
  }}
  .mt-col:hover .mt-card,
  .mt-col:hover .mt-guide {{ opacity: 1; }}

  /* Heatmap cell hover: highlight row + col, dim the rest, show badge */
  .hm-cell {{ cursor: pointer; }}
  .hm-rect {{ transition: filter 0.1s ease-out, opacity 0.1s ease-out; }}
  .hm-badge {{
    opacity: 0;
    transition: opacity 0.12s ease-out;
  }}
  /* When the SVG has a hovered cell, dim all cells, then re-light the
     hovered row + col. CSS-only: uses :has() (supported in modern browsers). */
  svg:has(.hm-cell:hover) .hm-rect {{ opacity: 0.32; }}
  svg:has(.hm-cell:hover) .hm-num {{ opacity: 0.35; }}
  /* Re-light the hovered cell itself */
  .hm-cell:hover .hm-rect {{ opacity: 1 !important; filter: brightness(1.06); }}
  .hm-cell:hover .hm-num {{ opacity: 1 !important; }}
  .hm-cell:hover .hm-badge {{ opacity: 1; }}
  @media (max-width: 720px) {{
    .bof-bar {{ padding: 10px 14px; font-size: 10px; }}
    .chart-frame {{ padding: 10px 12px 18px; }}
  }}
</style>
</head>
<body>
<div class="bof-bar">
  <a class="bof-brand" href="/" title="Back to dashboard">
    <svg viewBox="0 0 64 64" aria-hidden="true">
      <path fill-rule="evenodd" clip-rule="evenodd" d="M32 3 L42 22 L61 32 L42 42 L32 61 L22 42 L3 32 L22 22 Z M32 26 A6 6 0 1 0 32 38 A6 6 0 1 0 32 26 Z" fill="currentColor"/>
      <circle cx="32" cy="32" r="2.2" fill="currentColor"/>
    </svg>
    <strong>FORTIFY THE ORDNANCE</strong>
  </a>
  <a class="bof-back" href="/">← back to dashboard</a>
</div>
<div class="chart-frame">
{svg}
</div>
</body>
</html>"""


def _wrap(title: str, svg_body: str) -> str:
    return _PAGE.format(
        title=h(title), svg=svg_body,
        paper=PAPER, paper_soft=PAPER_SOFT, border=BORDER, grid=GRID,
        text_dark=TEXT_DARK, text_mid=TEXT_MID,
        brass=BRASS,
    )


# ── Helpers ────────────────────────────────────────────────────────────────

_PREFIX_RE = re.compile(
    r"^(For\s+(the\s+)?(purchase|manufacture\s+and\s+test|construction|completing"
    r"|finishing\s+and\s+assembling|carriages\s+for|purchase\s+and\s+delivery)\s+of\s+"
    r"|To\s+apply\s+on\s+purchase\s+of\s+(experimental\s+)?"
    r"|To\s+enable\s+the\s+Chief\s+of\s+Ordnance\s+to\s+"
    r"|For\s+the\s+|For\s+|To\s+|Construction\s+of\s+(a\s+)?"
    r"|Tests?\s+of\s+|Purchase\s+of\s+(a\s+|one\s+)?"
    r"|Experiments?\s+and\s+tests?\s+of\s+)",
    flags=re.IGNORECASE,
)

def _smart_short(desc: str, line_len: int = 38, max_lines: int = 2) -> list[str]:
    body = _PREFIX_RE.sub("", desc, count=1).strip()
    body = re.sub(r",?\s*procured\s+under.+$", "", body, flags=re.IGNORECASE)
    body = re.sub(r",?\s*(in\s+accordance\s+with|approved\s+\w+).+$", "", body, flags=re.IGNORECASE)
    body = body.replace("\n", " ").replace("  ", " ").strip()
    if body and body[0].islower():
        body = body[0].upper() + body[1:]

    words = body.split(" ")
    lines: list[str] = []
    current = ""
    for w in words:
        candidate = (current + " " + w).strip() if current else w
        if len(candidate) <= line_len:
            current = candidate
            continue
        if current:
            lines.append(current)
        if len(lines) == max_lines - 1:
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
    return lines


def _nice_upper(v: float, step: int = 25_000) -> int:
    """Round v up to the next multiple of step."""
    if v <= 0: return step
    return (int(v // step) + 1) * step


def _money_label(v: float) -> str:
    if v >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"${v/1_000:,.0f}k"
    return f"${v:,.0f}"


def _header(title: str, subtitle_html: str, width: int = 1600) -> str:
    """Title + subtitle block, anchored at top-left of the SVG."""
    return (
        f'<text class="chart-title" x="60" y="58">{h(title)}</text>'
        f'<foreignObject x="60" y="78" width="{width - 120}" height="64">'
        f'<div xmlns="http://www.w3.org/1999/xhtml" class="chart-subtitle">{subtitle_html}</div>'
        f'</foreignObject>'
    )


def _classify_clusters(allotments: pd.DataFrame) -> pd.DataFrame:
    """Add primary_cluster column using the cluster classifier."""
    out = allotments.copy()
    out["description"] = out["description"].astype(str)
    out["primary_cluster"] = out["description"].map(
        lambda t: (_match_multiple_categories(_to_lower(t), TECHNOLOGY_CLUSTER_PATTERNS) or ["Other/Unclassified"])[0]
    )
    return out


# ───────────────────────────────────────────────────────────────────────────
# 1. PARETO (horizontal bars + smart labels)
# ───────────────────────────────────────────────────────────────────────────

def save_pareto_svg(allotments: pd.DataFrame, out: Path, top_n: int = 20) -> None:
    by_proj = (
        allotments.groupby("description", as_index=False)
        .agg(total=("allotted", "sum"), count=("allotted", "size"))
        .sort_values("total", ascending=False)
    )
    grand = by_proj["total"].sum()
    by_proj["cum_pct"] = by_proj["total"].cumsum() / grand * 100
    n80 = int((by_proj["cum_pct"] <= 80).sum()) + 1
    top_share_pct = by_proj.head(top_n)["total"].sum() / grand * 100

    top = by_proj.head(top_n).copy().reset_index(drop=True)
    top["lines"] = top["description"].map(_smart_short)

    VB_W, VB_H = 1600, 900
    M_L, M_R, M_T, M_B = 360, 100, 150, 80
    x0, x1, y0, y1 = M_L, VB_W - M_R, M_T, VB_H - M_B
    plot_w, plot_h = x1 - x0, y1 - y0

    upper = _nice_upper(top["total"].max(), 25_000)
    tick_step = 25_000 if upper <= 150_000 else 50_000
    ticks = list(range(0, upper + 1, tick_step))

    n = len(top)
    row_h = plot_h / n
    bar_h = row_h * 0.62

    def x_for(v): return x0 + (v / upper) * plot_w

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB_W} {VB_H}" '
        f'preserveAspectRatio="xMidYMid meet" role="img">'
    ]
    parts.append(_header(
        f"Top {top_n} Projects by Total Allotment",
        f'These {top_n} projects account for <b>{top_share_pct:.0f}%</b> of the '
        f'${grand:,.0f} the Board allotted 1888–1918. '
        f'It takes <b>{n80} of {len(by_proj):,}</b> projects to reach 80% of total spend.',
        VB_W,
    ))

    # Grid + x ticks
    parts.append('<g class="grid">')
    for v in ticks:
        x = x_for(v)
        parts.append(f'<line class="grid-line" x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y1}"/>')
    parts.append('</g>')
    for v in ticks:
        parts.append(
            f'<text class="tick" x="{x_for(v):.1f}" y="{y1 + 22}" text-anchor="middle">{_money_label(v)}</text>'
        )
    parts.append(
        f'<text class="axis-label" x="{(x0 + x1) / 2:.1f}" y="{y1 + 54}" text-anchor="middle">Total allotted ($)</text>'
    )

    # Bars + invisible hit-rect per row to reveal a rank badge + cumulative pill
    for i, row in top.iterrows():
        rank = top_n - i  # row 0 is the lowest-spend bar at the bottom (#20)
        y_center = y0 + (i + 0.5) * row_h
        y_bar_top = y0 + i * row_h + (row_h - bar_h) / 2
        bar_w = (row["total"] / upper) * plot_w
        parts.append(f'<g class="pareto-row" data-rank="{rank}">')
        # Wider hit-rect so hovering the label area counts
        parts.append(
            f'<rect class="pareto-hit" x="0" y="{y0 + i * row_h:.1f}" '
            f'width="{VB_W}" height="{row_h:.1f}" fill="transparent"/>'
        )
        parts.append(
            f'<title>{h(row["description"])}\n'
            f'Total: ${row["total"]:,.0f}\n'
            f'Cumulative: {row["cum_pct"]:.1f}%</title>'
        )
        lines = row["lines"]
        label_y = y_center - ((len(lines) - 1) * 16) / 2 + 5
        tspans = "".join(
            f'<tspan x="{x0 - 14}" dy="{0 if j == 0 else 16}">{h(line)}</tspan>'
            for j, line in enumerate(lines)
        )
        parts.append(
            f'<text class="y-label-vert" x="{x0 - 14}" y="{label_y:.1f}">{tspans}</text>'
        )
        parts.append(
            f'<rect class="pareto-bar" fill="{BRASS}" x="{x0}" y="{y_bar_top:.1f}" '
            f'width="{bar_w:.1f}" height="{bar_h:.1f}" rx="1.5"/>'
        )
        parts.append(
            f'<text class="bar-value" x="{x0 + bar_w + 8:.1f}" y="{y_center + 4:.1f}">{_money_label(row["total"])}</text>'
        )
        # Rank badge — appears on hover to the left of the label
        parts.append(
            f'<text class="pareto-rank" x="{40}" y="{y_center + 5:.1f}" '
            f'text-anchor="start">#{rank}</text>'
        )
        # Cumulative-share pill — appears on hover, right of the $ value
        cum_x = x0 + bar_w + 90
        parts.append(
            f'<g class="pareto-cum">'
            f'<rect x="{cum_x - 4:.1f}" y="{y_center - 12:.1f}" width="92" height="22" '
            f'rx="11" fill="{PAPER_SOFT}" stroke="{BRASS}" stroke-width="1"/>'
            f'<text x="{cum_x + 42:.1f}" y="{y_center + 3:.1f}" text-anchor="middle" '
            f'font-family="JetBrains Mono, monospace" font-size="11" font-weight="700" '
            f'fill="{TEXT_DARK}">{row["cum_pct"]:.1f}% cum</text>'
            f'</g>'
        )
        parts.append('</g>')

    parts.append(f'<line class="grid-line" x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke-width="1.2"/>')
    parts.append('</svg>')

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_wrap(f"Top {top_n} Projects by Allotment", "\n".join(parts)), encoding="utf-8")


# ───────────────────────────────────────────────────────────────────────────
# 2. MASTER TIMELINE (stacked annual bars + appropriation line)
# ───────────────────────────────────────────────────────────────────────────

def save_master_timeline_svg(
    allotments: pd.DataFrame,
    appropriations: pd.DataFrame,
    out: Path,
) -> None:
    al = allotments.copy()
    al["revoked"] = al["revoked"].fillna(False)
    grp = al.groupby(["year", "revoked"])["allotted"].sum().unstack(fill_value=0)
    if False not in grp.columns: grp[False] = 0
    if True  not in grp.columns: grp[True] = 0
    grp = grp.rename(columns={False: "active", True: "revoked"})
    appr = appropriations.groupby("year")["amount"].sum()

    years = sorted(set(grp.index) | set(appr.index))
    years = [y for y in years if 1888 <= y <= 1920]
    active   = [float(grp["active"].get(y, 0)) for y in years]
    revoked  = [float(grp["revoked"].get(y, 0)) for y in years]
    appropv  = [float(appr.get(y, 0)) for y in years]

    VB_W, VB_H = 1600, 900
    M_L, M_R, M_T, M_B = 100, 60, 150, 110
    x0, x1, y0, y1 = M_L, VB_W - M_R, M_T, VB_H - M_B
    plot_w, plot_h = x1 - x0, y1 - y0

    max_val = max(max(a + r for a, r in zip(active, revoked)), max(appropv) if appropv else 0)
    upper = _nice_upper(max_val, 100_000)
    tick_step = 100_000 if upper <= 700_000 else 200_000
    y_ticks = list(range(0, upper + 1, tick_step))

    def x_for(year): return x0 + ((year - years[0]) / (years[-1] - years[0])) * plot_w
    def y_for(v): return y1 - (v / upper) * plot_h

    bar_w = (plot_w / len(years)) * 0.62

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB_W} {VB_H}" preserveAspectRatio="xMidYMid meet">']
    parts.append(_header(
        "Master Ledger · 1888–1918",
        f"Annual congressional appropriation vs. line-item allotments. "
        f"Bars = allotments (gold active, vermilion revoked); line = appropriation. "
        f"<b>{len(allotments):,}</b> line items · <b>${al['allotted'].sum():,.0f}</b> total allotted.",
        VB_W,
    ))

    # Horizontal grid
    parts.append('<g class="grid">')
    for v in y_ticks:
        y = y_for(v)
        parts.append(f'<line class="grid-line" x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}"/>')
    parts.append('</g>')
    # Y tick labels
    for v in y_ticks:
        parts.append(f'<text class="tick" x="{x0 - 12}" y="{y_for(v) + 4:.1f}" text-anchor="end">{_money_label(v)}</text>')
    parts.append(f'<text class="axis-label" x="{x0 - 70}" y="{(y0 + y1) / 2:.1f}" '
                 f'transform="rotate(-90 {x0 - 70} {(y0 + y1) / 2:.1f})" text-anchor="middle">USD (nominal)</text>')

    # Era markers
    for era_year, label in [(1898, "Spanish-American War"), (1917, "U.S. enters WWI")]:
        if years[0] <= era_year <= years[-1]:
            ex = x_for(era_year)
            parts.append(f'<line stroke="{TEXT_MID}" stroke-width="1" stroke-dasharray="3,3" opacity="0.45" '
                         f'x1="{ex:.1f}" y1="{y0 - 14}" x2="{ex:.1f}" y2="{y1}"/>')
            parts.append(f'<text class="annot" x="{ex:.1f}" y="{y0 - 18}" text-anchor="middle">{h(label)}</text>')

    # Bars (stacked: active on bottom, revoked on top)
    for i, y in enumerate(years):
        cx = x_for(y)
        bx = cx - bar_w / 2
        ay = active[i]
        rv = revoked[i]
        if ay > 0:
            top = y_for(ay)
            parts.append(
                f'<rect class="mt-active" fill="{BRASS}" x="{bx:.1f}" y="{top:.1f}" '
                f'width="{bar_w:.1f}" height="{y1 - top:.1f}"/>'
            )
        if rv > 0:
            top_rev = y_for(ay + rv)
            base_rev = y_for(ay)
            parts.append(
                f'<rect class="mt-revoked" fill="{VERMILLION}" opacity="0.88" '
                f'x="{bx:.1f}" y="{top_rev:.1f}" width="{bar_w:.1f}" '
                f'height="{base_rev - top_rev:.1f}"/>'
            )

    # Line + markers (congressional appropriation)
    pts = [f"{x_for(years[i]):.1f},{y_for(appropv[i]):.1f}" for i in range(len(years))]
    parts.append(f'<polyline fill="none" stroke="{TEXT_DARK}" stroke-width="2.5" points="{" ".join(pts)}"/>')
    for i, y in enumerate(years):
        cx = x_for(y); cy = y_for(appropv[i])
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{PAPER}" '
            f'stroke="{TEXT_DARK}" stroke-width="2"/>'
        )

    # Year-column hover layer: shows a value card with active/revoked/appropriation
    col_w = (plot_w / max(1, len(years) - 1))
    for i, y in enumerate(years):
        cx = x_for(y)
        ay = active[i]; rv = revoked[i]; ap = appropv[i]
        # Position card above the tallest element of this year
        max_pt = max(ay + rv, ap)
        card_y_anchor = y_for(max_pt) - 12
        card_w = 168
        card_h = 96
        # Keep card on-screen — flip below if it would go above the title area
        card_y = max(y0 - 4, card_y_anchor - card_h)
        # Try to keep card horizontally inside the plot
        card_x = max(x0, min(cx - card_w / 2, x1 - card_w))

        parts.append(f'<g class="mt-col" data-year="{y}">')
        parts.append(
            f'<rect class="mt-hit" x="{cx - col_w/2:.1f}" y="{y0}" '
            f'width="{col_w:.1f}" height="{plot_h:.1f}" fill="transparent"/>'
        )
        # Vertical guide line
        parts.append(
            f'<line class="mt-guide" x1="{cx:.1f}" y1="{y0}" x2="{cx:.1f}" '
            f'y2="{y1}" stroke="{TEXT_MID}" stroke-width="1" '
            f'stroke-dasharray="2,3" opacity="0"/>'
        )
        # Value card (hidden until column hover)
        parts.append(
            f'<g class="mt-card" pointer-events="none">'
            f'<rect x="{card_x:.1f}" y="{card_y:.1f}" width="{card_w}" height="{card_h}" '
            f'rx="4" fill="{PAPER_SOFT}" stroke="{BORDER}"/>'
            f'<text x="{card_x + 12}" y="{card_y + 22}" '
            f'font-family="Source Serif 4, Georgia, serif" font-weight="700" '
            f'font-size="14" fill="{TEXT_DARK}">{y}</text>'
            f'<circle cx="{card_x + 14}" cy="{card_y + 42}" r="4" fill="{BRASS}"/>'
            f'<text x="{card_x + 26}" y="{card_y + 46}" '
            f'font-family="Inter, sans-serif" font-size="11" fill="{TEXT_MID}">Active</text>'
            f'<text x="{card_x + card_w - 12}" y="{card_y + 46}" text-anchor="end" '
            f'font-family="JetBrains Mono, monospace" font-size="11.5" font-weight="700" '
            f'fill="{TEXT_DARK}">{_money_label(ay) if ay else "—"}</text>'
            f'<circle cx="{card_x + 14}" cy="{card_y + 62}" r="4" fill="{VERMILLION}"/>'
            f'<text x="{card_x + 26}" y="{card_y + 66}" '
            f'font-family="Inter, sans-serif" font-size="11" fill="{TEXT_MID}">Revoked</text>'
            f'<text x="{card_x + card_w - 12}" y="{card_y + 66}" text-anchor="end" '
            f'font-family="JetBrains Mono, monospace" font-size="11.5" font-weight="700" '
            f'fill="{TEXT_DARK}">{_money_label(rv) if rv else "—"}</text>'
            f'<circle cx="{card_x + 14}" cy="{card_y + 82}" r="4" fill="{TEXT_DARK}"/>'
            f'<text x="{card_x + 26}" y="{card_y + 86}" '
            f'font-family="Inter, sans-serif" font-size="11" fill="{TEXT_MID}">Appropriated</text>'
            f'<text x="{card_x + card_w - 12}" y="{card_y + 86}" text-anchor="end" '
            f'font-family="JetBrains Mono, monospace" font-size="11.5" font-weight="700" '
            f'fill="{TEXT_DARK}">{_money_label(ap) if ap else "—"}</text>'
            f'</g>'
        )
        parts.append('</g>')

    # X-axis ticks (every 2 years)
    parts.append(f'<line class="grid-line" x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke-width="1.2"/>')
    for y in years:
        if y % 2 == 0:
            parts.append(f'<text class="tick" x="{x_for(y):.1f}" y="{y1 + 22}" text-anchor="middle">{y}</text>')
    parts.append(f'<text class="axis-label" x="{(x0 + x1) / 2:.1f}" y="{y1 + 54}" text-anchor="middle">Fiscal year</text>')

    # Legend at bottom
    legend = [
        (BRASS,      "Allotted (active)"),
        (VERMILLION, "Allotted (revoked)"),
        (TEXT_DARK,  "Congressional appropriation"),
    ]
    lx = x0
    ly = VB_H - 38
    for color, label in legend:
        parts.append(f'<rect fill="{color}" x="{lx}" y="{ly}" width="16" height="12" rx="1"/>')
        parts.append(f'<text class="legend-text" x="{lx + 22}" y="{ly + 10}">{h(label)}</text>')
        lx += 22 + 8 * len(label) + 30

    parts.append('</svg>')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_wrap("Master Ledger 1888–1918", "\n".join(parts)), encoding="utf-8")


# ───────────────────────────────────────────────────────────────────────────
# 3. HISTORICAL EVENTS (stacked annual bars + milestone annotations)
# ───────────────────────────────────────────────────────────────────────────

_HIST_PALETTE = {
    "Legislation":    "#1F3A5F",
    "Organizational": "#6B89A8",
    "Personnel":      "#9F8B6B",
    "Technology":     "#C9A24C",
    "Machine Gun":    "#A8852E",
    "Airplane":       "#5B7B95",
    "Other":          "#8C8273",
}
_HIST_ORDER = list(_HIST_PALETTE.keys())


def save_historical_events_svg(events: pd.DataFrame, out: Path) -> None:
    df = events[events["year"].between(1888, 1920)]
    years = list(range(1888, 1921))
    pivot = df.groupby(["year", "category"]).size().unstack("category", fill_value=0).reindex(years, fill_value=0)
    # Ensure all categories exist as columns
    for cat in _HIST_ORDER:
        if cat not in pivot.columns:
            pivot[cat] = 0

    totals_per_year = pivot[_HIST_ORDER].sum(axis=1).tolist()
    max_total = max(totals_per_year)

    VB_W, VB_H = 1600, 900
    M_L, M_R, M_T, M_B = 90, 50, 160, 130
    x0, x1, y0, y1 = M_L, VB_W - M_R, M_T, VB_H - M_B
    plot_w, plot_h = x1 - x0, y1 - y0

    upper = ((max_total // 10) + 1) * 10
    y_ticks = list(range(0, upper + 1, 10 if upper <= 50 else 20))

    def x_for(yr): return x0 + ((yr - years[0]) / (years[-1] - years[0])) * plot_w
    def y_for(v): return y1 - (v / upper) * plot_h
    bar_w = (plot_w / len(years)) * 0.74

    total_events = int(pivot[_HIST_ORDER].sum().sum())
    top3 = pivot[_HIST_ORDER].sum().sort_values(ascending=False).head(3)
    subtitle = (
        f"<b>{total_events:,}</b> events recorded across the Board's lifespan. "
        + " · ".join(f"<b>{cat}</b> ({n})" for cat, n in top3.items()) + "."
    )

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB_W} {VB_H}" preserveAspectRatio="xMidYMid meet">']
    parts.append(_header("Historical Events · 1888–1920", subtitle, VB_W))

    # Grid
    parts.append('<g class="grid">')
    for v in y_ticks:
        y = y_for(v)
        parts.append(f'<line class="grid-line" x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}"/>')
    parts.append('</g>')
    for v in y_ticks:
        parts.append(f'<text class="tick" x="{x0 - 12}" y="{y_for(v) + 4:.1f}" text-anchor="end">{v}</text>')
    parts.append(f'<text class="axis-label" x="{x0 - 68}" y="{(y0 + y1) / 2:.1f}" '
                 f'transform="rotate(-90 {x0 - 68} {(y0 + y1) / 2:.1f})" text-anchor="middle">Events recorded</text>')

    # Milestones
    milestones = [
        (1888, "BOF established"),
        (1898, "Spanish-American War"),
        (1917, "U.S. enters WWI"),
        (1920, "BOF dissolved"),
    ]
    for ms_year, label in milestones:
        if years[0] <= ms_year <= years[-1]:
            mx = x_for(ms_year)
            parts.append(f'<line stroke="{TEXT_MID}" stroke-width="1" stroke-dasharray="3,3" opacity="0.45" '
                         f'x1="{mx:.1f}" y1="{y0 - 14}" x2="{mx:.1f}" y2="{y1}"/>')
            parts.append(f'<text class="annot" x="{mx:.1f}" y="{y0 - 18}" text-anchor="middle">{h(label)}</text>')

    # Stacked bars. Each year column is one <g class="year-col"> so hovering
     # anywhere in the column reveals the count labels for every segment.
    for i, yr in enumerate(years):
        cx = x_for(yr)
        bx = cx - bar_w / 2
        year_total = int(pivot.loc[yr][_HIST_ORDER].sum()) if yr in pivot.index else 0
        parts.append(f'<g class="year-col" data-year="{yr}">')
        # Invisible hit-rect spanning the full column so hover works on tiny segments
        parts.append(
            f'<rect class="year-hit" x="{bx - 2:.1f}" y="{y0:.1f}" '
            f'width="{bar_w + 4:.1f}" height="{y1 - y0:.1f}" fill="transparent"/>'
        )
        running = 0
        seg_labels = []  # collect label drawings so we can render them on top
        for cat in _HIST_ORDER:
            count = int(pivot.loc[yr, cat]) if yr in pivot.index else 0
            if count == 0: continue
            top = y_for(running + count)
            bottom = y_for(running)
            mid = (top + bottom) / 2
            parts.append('<g class="seg">')
            parts.append(f'<title>{yr}: {cat} — {count} events</title>')
            parts.append(
                f'<rect class="seg-rect" fill="{_HIST_PALETTE[cat]}" '
                f'x="{bx:.1f}" y="{top:.1f}" '
                f'width="{bar_w:.1f}" height="{bottom - top:.1f}"/>'
            )
            seg_labels.append(
                f'<text class="seg-label" x="{cx:.1f}" y="{mid + 4:.1f}" '
                f'text-anchor="middle">{count}</text>'
            )
            parts.append('</g>')
            running += count
        # Render labels on top of all segments so they aren't clipped
        parts.extend(seg_labels)
        # Year total label appears above the bar on column hover
        if year_total > 0:
            parts.append(
                f'<text class="year-total" x="{cx:.1f}" y="{y_for(year_total) - 8:.1f}" '
                f'text-anchor="middle">{year_total}</text>'
            )
        parts.append('</g>')

    # X-axis
    parts.append(f'<line class="grid-line" x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke-width="1.2"/>')
    for yr in years:
        if yr % 2 == 0:
            parts.append(f'<text class="tick" x="{x_for(yr):.1f}" y="{y1 + 22}" text-anchor="middle">{yr}</text>')
    parts.append(f'<text class="axis-label" x="{(x0 + x1) / 2:.1f}" y="{y1 + 54}" text-anchor="middle">Year</text>')

    # Legend
    lx = x0
    ly = VB_H - 38
    for cat in _HIST_ORDER:
        color = _HIST_PALETTE[cat]
        parts.append(f'<rect fill="{color}" x="{lx}" y="{ly}" width="14" height="12" rx="1"/>')
        parts.append(f'<text class="legend-text" x="{lx + 20}" y="{ly + 10}">{h(cat)}</text>')
        lx += 20 + 8 * len(cat) + 24

    parts.append('</svg>')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_wrap("Historical Events 1888–1920", "\n".join(parts)), encoding="utf-8")


# ───────────────────────────────────────────────────────────────────────────
# 4. YUNHA — Dollars by Cluster (treemap, row-based squarified)
# ───────────────────────────────────────────────────────────────────────────

def _squarify(items: list[tuple[str, float]], x: float, y: float, w: float, h_: float) -> list[dict]:
    """Simple greedy row-based treemap. items sorted by value desc."""
    total = sum(v for _, v in items)
    if total <= 0 or not items:
        return []
    rects = []
    remaining = items[:]
    cur_x, cur_y, cur_w, cur_h = x, y, w, h_
    while remaining:
        # Take items into a row until aspect ratio worsens
        if cur_w >= cur_h:
            # Pack vertically into a column
            n = max(1, min(len(remaining), 3))
            col_total = sum(v for _, v in remaining[:n])
            col_w = (col_total / sum(v for _, v in remaining)) * cur_w
            y_cursor = cur_y
            for label, v in remaining[:n]:
                rect_h = (v / col_total) * cur_h
                rects.append({"label": label, "value": v, "x": cur_x, "y": y_cursor, "w": col_w, "h": rect_h})
                y_cursor += rect_h
            cur_x += col_w
            cur_w -= col_w
            remaining = remaining[n:]
        else:
            n = max(1, min(len(remaining), 3))
            row_total = sum(v for _, v in remaining[:n])
            row_h = (row_total / sum(v for _, v in remaining)) * cur_h
            x_cursor = cur_x
            for label, v in remaining[:n]:
                rect_w = (v / row_total) * cur_w
                rects.append({"label": label, "value": v, "x": x_cursor, "y": cur_y, "w": rect_w, "h": row_h})
                x_cursor += rect_w
            cur_y += row_h
            cur_h -= row_h
            remaining = remaining[n:]
    return rects


def save_yunha_treemap_svg(allotments: pd.DataFrame, out: Path) -> None:
    classified = _classify_clusters(allotments)
    classified["allotted"] = pd.to_numeric(classified["allotted"], errors="coerce").fillna(0)
    grp = (
        classified.groupby("primary_cluster")
        .agg(total=("allotted", "sum"), count=("allotted", "size"),
             revoked_n=("revoked", lambda s: int(s.fillna(False).sum())))
        .reset_index()
        .sort_values("total", ascending=False)
    )
    grand = grp["total"].sum()
    items = [(row.primary_cluster, float(row.total)) for row in grp.itertuples()]

    VB_W, VB_H = 1600, 900
    # Reserve bottom strip for legend so every cluster — including thin slivers — is identifiable.
    M_L, M_R, M_T, M_B = 60, 60, 150, 130
    x0, y0 = M_L, M_T
    plot_w, plot_h = VB_W - M_L - M_R, VB_H - M_T - M_B

    rects = _squarify(items, x0, y0, plot_w, plot_h)

    info_by_cluster = {r.primary_cluster: (int(r.count), int(r.revoked_n)) for r in grp.itertuples()}

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB_W} {VB_H}" preserveAspectRatio="xMidYMid meet">']
    parts.append(_header(
        "Investment Dollars by Technology Cluster",
        f"BOF allotments classified by primary technology cluster · 1888–1918 · "
        f"<b>${grand:,.0f}</b> total across <b>{int(grp['count'].sum()):,}</b> line items. "
        f"Hover any tile (including the thin ones) for details.",
        VB_W,
    ))

    for r in rects:
        color = CLUSTER_PALETTE.get(r["label"], "#546E7A")
        share = r["value"] / grand * 100
        cnt, rev = info_by_cluster.get(r["label"], (0, 0))
        cx = r["x"] + r["w"] / 2
        cy = r["y"] + r["h"] / 2

        parts.append('<g class="tm-tile">')
        parts.append(f'<title>{h(r["label"])}\nTotal: ${r["value"]:,.0f}\n{cnt} line items · {rev} revoked\n{share:.1f}% of grand total</title>')
        parts.append(
            f'<rect class="tm-rect" fill="{color}" x="{r["x"]:.1f}" y="{r["y"]:.1f}" '
            f'width="{r["w"]:.1f}" height="{r["h"]:.1f}" '
            f'stroke="{PAPER}" stroke-width="3"/>'
        )
        # Always-visible labels inside — only if rect is big enough
        if r["w"] > 110 and r["h"] > 60:
            label_size = 16 if r["w"] > 220 else 13
            val_size = 13 if r["w"] > 220 else 11
            parts.append(
                f'<text class="tm-label" x="{r["x"] + 14:.1f}" y="{r["y"] + 26:.1f}" '
                f'font-family="Source Serif 4, Georgia, serif" font-weight="700" '
                f'font-size="{label_size}" fill="white">{h(r["label"])}</text>'
            )
            parts.append(
                f'<text class="tm-label" x="{r["x"] + 14:.1f}" y="{r["y"] + 26 + label_size + 6:.1f}" '
                f'font-family="Inter, sans-serif" font-size="{val_size}" '
                f'fill="white" opacity="0.85">${r["value"]/1000:,.0f}k · {share:.1f}%</text>'
            )
        # Hover-only detail card centered on the tile
        card_w = min(r["w"] - 24, 240)
        card_h = 86
        card_x = cx - card_w / 2
        card_y = cy - card_h / 2
        if card_w >= 140:  # only show card on tiles big enough
            parts.append(
                f'<g class="tm-card" pointer-events="none">'
                f'<rect x="{card_x:.1f}" y="{card_y:.1f}" width="{card_w:.1f}" '
                f'height="{card_h}" rx="4" fill="{PAPER_SOFT}" '
                f'stroke="{color}" stroke-width="1.5"/>'
                f'<text x="{cx:.1f}" y="{card_y + 22:.1f}" text-anchor="middle" '
                f'font-family="Source Serif 4, Georgia, serif" font-weight="700" '
                f'font-size="13" fill="{TEXT_DARK}">{h(r["label"])}</text>'
                f'<text x="{cx:.1f}" y="{card_y + 44:.1f}" text-anchor="middle" '
                f'font-family="Inter, sans-serif" font-weight="700" '
                f'font-size="16" fill="{color}">${r["value"]/1000:,.0f}k</text>'
                f'<text x="{cx:.1f}" y="{card_y + 64:.1f}" text-anchor="middle" '
                f'font-family="Inter, sans-serif" font-size="11" '
                f'fill="{TEXT_MID}">{cnt} line items · {rev} revoked · {share:.1f}%</text>'
                f'</g>'
            )
        parts.append('</g>')

    # Legend — 2-row grid below the treemap so the thin slivers on the right
    # (Explosives, Armor, Small Arms, Comms, Logistics) can still be ID'd.
    legend_y = VB_H - 100
    n_cols = 4
    col_w = (VB_W - 120) / n_cols
    sorted_for_legend = grp.sort_values("total", ascending=False).reset_index(drop=True)
    for idx, lrow in sorted_for_legend.iterrows():
        ci = int(idx) % n_cols
        ri = int(idx) // n_cols
        lx = 60 + ci * col_w
        ly = legend_y + ri * 38
        cluster = lrow["primary_cluster"]
        color = CLUSTER_PALETTE.get(cluster, "#546E7A")
        share = lrow["total"] / grand * 100
        parts.append(
            f'<rect fill="{color}" x="{lx}" y="{ly}" width="16" height="16" rx="2"/>'
        )
        parts.append(
            f'<text class="legend-text" x="{lx + 24}" y="{ly + 12}" '
            f'font-weight="600">{h(cluster)}</text>'
        )
        parts.append(
            f'<text x="{lx + 24}" y="{ly + 28}" '
            f'font-family="JetBrains Mono, monospace" font-size="11" '
            f'fill="{TEXT_MID}">${lrow["total"]/1000:,.0f}k · {share:.1f}% · {int(lrow["count"])} items</text>'
        )

    parts.append('</svg>')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_wrap("Dollars by Technology Cluster", "\n".join(parts)), encoding="utf-8")


# ───────────────────────────────────────────────────────────────────────────
# 5. YUNHA — Investment Trajectory (multi-line)
# ───────────────────────────────────────────────────────────────────────────

def save_yunha_trajectory_svg(allotments: pd.DataFrame, out: Path) -> None:
    classified = _classify_clusters(allotments)
    classified["allotted"] = pd.to_numeric(classified["allotted"], errors="coerce").fillna(0)
    classified["year"] = pd.to_numeric(classified["year"], errors="coerce")
    classified = classified.dropna(subset=["year"])
    classified["year"] = classified["year"].astype(int)

    pivot = classified.groupby(["year", "primary_cluster"])["allotted"].sum().unstack("primary_cluster", fill_value=0).sort_index()
    years = pivot.index.tolist()
    cluster_totals = pivot.sum().sort_values(ascending=False)
    clusters = [c for c in cluster_totals.index if c in CLUSTER_PALETTE]

    VB_W, VB_H = 1600, 900
    M_L, M_R, M_T, M_B = 100, 260, 160, 90  # right margin for vertical legend
    x0, x1, y0, y1 = M_L, VB_W - M_R, M_T, VB_H - M_B
    plot_w, plot_h = x1 - x0, y1 - y0

    max_val = pivot[clusters].max().max() if clusters else 0
    upper = _nice_upper(max_val, 50_000)
    tick_step = 50_000 if upper <= 300_000 else 100_000
    y_ticks = list(range(0, upper + 1, tick_step))

    def x_for(yr): return x0 + ((yr - years[0]) / (years[-1] - years[0])) * plot_w
    def y_for(v): return y1 - (v / upper) * plot_h

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB_W} {VB_H}" preserveAspectRatio="xMidYMid meet">']
    parts.append(_header(
        "Investment Trajectory by Technology Cluster",
        "Annual dollar allotments per cluster, 1888–1918. Legend ordered by total spend (most → least).",
        VB_W,
    ))

    # Grid
    for v in y_ticks:
        y = y_for(v)
        parts.append(f'<line class="grid-line" x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}"/>')
    for v in y_ticks:
        parts.append(f'<text class="tick" x="{x0 - 12}" y="{y_for(v) + 4:.1f}" text-anchor="end">{_money_label(v)}</text>')
    parts.append(f'<text class="axis-label" x="{x0 - 70}" y="{(y0 + y1) / 2:.1f}" '
                 f'transform="rotate(-90 {x0 - 70} {(y0 + y1) / 2:.1f})" text-anchor="middle">Allotted ($, nominal)</text>')

    # Era markers
    for era_year, label in [(1898, "Spanish-American War"), (1917, "U.S. enters WWI")]:
        if years[0] <= era_year <= years[-1]:
            ex = x_for(era_year)
            parts.append(f'<line stroke="{TEXT_MID}" stroke-width="1" stroke-dasharray="3,3" opacity="0.45" '
                         f'x1="{ex:.1f}" y1="{y0 - 14}" x2="{ex:.1f}" y2="{y1}"/>')
            parts.append(f'<text class="annot" x="{ex:.1f}" y="{y0 - 18}" text-anchor="middle">{h(label)}</text>')

    # Lines + markers per cluster. Each cluster's line gets a class so
    # we can dim non-hovered clusters via CSS.
    cluster_class = {c: f"cl-{i}" for i, c in enumerate(clusters)}
    for cluster in clusters:
        color = CLUSTER_PALETTE[cluster]
        cls = cluster_class[cluster]
        pts = [f"{x_for(years[i]):.1f},{y_for(pivot.loc[years[i], cluster]):.1f}" for i in range(len(years))]
        parts.append(
            f'<polyline class="traj-line {cls}" fill="none" stroke="{color}" '
            f'stroke-width="2" points="{" ".join(pts)}" opacity="0.92"/>'
        )
        for i, yr in enumerate(years):
            v = pivot.loc[yr, cluster]
            if v <= 0: continue
            parts.append(f'<g class="traj-pt {cls}">')
            parts.append(f'<title>{h(cluster)}\n{yr}: ${v:,.0f}</title>')
            parts.append(
                f'<circle cx="{x_for(yr):.1f}" cy="{y_for(v):.1f}" r="3.5" '
                f'fill="{color}" stroke="{PAPER}" stroke-width="1.5"/>'
            )
            parts.append('</g>')

    # Year-column hover: a transparent hit-rect per year reveals a vertical
    # guide + all cluster values at that year. Drawn LAST so it sits on top.
    parts.append('<g class="traj-year-hits">')
    col_w = plot_w / max(1, len(years) - 1)
    for i, yr in enumerate(years):
        cx = x_for(yr)
        parts.append(f'<g class="year-col" data-year="{yr}">')
        parts.append(
            f'<rect class="year-hit" x="{cx - col_w/2:.1f}" y="{y0}" '
            f'width="{col_w:.1f}" height="{plot_h:.1f}" fill="transparent"/>'
        )
        # Vertical guide line
        parts.append(
            f'<line class="year-guide" x1="{cx:.1f}" y1="{y0}" '
            f'x2="{cx:.1f}" y2="{y1}" stroke="{TEXT_MID}" stroke-width="1" '
            f'stroke-dasharray="2,3" opacity="0"/>'
        )
        # Year label + per-cluster value labels (hidden until hover)
        parts.append(
            f'<text class="year-col-label" x="{cx:.1f}" y="{y0 - 6:.1f}" '
            f'text-anchor="middle">{yr}</text>'
        )
        # Stack value labels in legend order (largest cluster at top)
        for cluster in clusters:
            v = float(pivot.loc[yr, cluster]) if cluster in pivot.columns else 0
            if v <= 0: continue
            color = CLUSTER_PALETTE[cluster]
            ypos = y_for(v)
            # Place label to the right of the marker, with a small dot prefix
            label_x = cx + 8
            parts.append(
                f'<rect class="year-col-bg" x="{label_x - 3:.1f}" '
                f'y="{ypos - 9:.1f}" width="80" height="16" rx="2" '
                f'fill="{PAPER}" stroke="{color}" stroke-width="1" opacity="0"/>'
            )
            parts.append(
                f'<text class="year-col-val" x="{label_x + 4:.1f}" '
                f'y="{ypos + 3:.1f}" fill="{color}">{_money_label(v)}</text>'
            )
        parts.append('</g>')
    parts.append('</g>')

    # X-axis
    parts.append(f'<line class="grid-line" x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke-width="1.2"/>')
    for yr in years:
        if yr % 2 == 0:
            parts.append(f'<text class="tick" x="{x_for(yr):.1f}" y="{y1 + 22}" text-anchor="middle">{yr}</text>')
    parts.append(f'<text class="axis-label" x="{(x0 + x1) / 2:.1f}" y="{y1 + 54}" text-anchor="middle">Year</text>')

    # Vertical legend
    lx = x1 + 30
    ly = y0
    for cluster in clusters:
        color = CLUSTER_PALETTE[cluster]
        total = cluster_totals[cluster]
        parts.append(f'<line stroke="{color}" stroke-width="3" x1="{lx}" y1="{ly + 6}" x2="{lx + 22}" y2="{ly + 6}"/>')
        parts.append(f'<circle cx="{lx + 11}" cy="{ly + 6}" r="3.5" fill="{color}" stroke="{PAPER}" stroke-width="1"/>')
        parts.append(f'<text class="legend-text" x="{lx + 30}" y="{ly + 10}">{h(cluster)}</text>')
        parts.append(f'<text class="tick" x="{lx + 30}" y="{ly + 26}">${total/1000:,.0f}k total</text>')
        ly += 46

    parts.append('</svg>')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_wrap("Investment Trajectory 1888–1918", "\n".join(parts)), encoding="utf-8")


# ───────────────────────────────────────────────────────────────────────────
# 6. TANISHA — Stacked Bars (period × category counts)
# ───────────────────────────────────────────────────────────────────────────

_TANISHA_PERIODS = [
    "1897-98", "1898-99", "1900-01", "1901-02",
    "1903-04", "1904-05", "1905-06", "1906-07", "1907-08",
]
_TANISHA_COUNTS = {
    "Aerial / Aviation":            [29, 51,  1,  5, 18,  4,  7,  8, 13],
    "Artillery & Guns":             [68, 39, 38, 53, 52, 38, 31, 32, 25],
    "Projectiles & Ammunition":     [130, 22, 27, 28, 22, 18, 20, 23, 22],
    "Explosives & Propellants":     [23,  9,  9,  7,  8,  5,  1,  3,  4],
    "Torpedoes & Mines":            [42,  6,  3,  3,  9, 12,  8,  5,  8],
    "Range Finding & Fire Control": [17, 12,  9, 13, 17, 14, 18, 10, 15],
    "Wireless & Electrical":        [ 4,  5,  2,  8,  2,  1,  0,  0,  3],
    "Armor & Fortification":        [23,  4,  3,  9, 17, 11,  6,  9,  7],
    "Searchlights & Optics":        [ 2,  2,  3,  3, 10,  7,  5, 22, 10],
    "Small Arms":                   [ 9,  4,  4, 14,  9,  5,  7,  4,  3],
    "Transportation & Vehicles":    [ 2,  2,  3,  5,  5,  0,  4,  0,  4],
    "Entrenching & Field Equip.":   [ 0,  3, 10, 10,  8,  7,  3,  1,  0],
    "Other":                        [48, 20, 13, 52, 41, 17, 23, 25, 34],
}
_TANISHA_PALETTE = {
    "Aerial / Aviation":            "#378ADD",
    "Artillery & Guns":             "#1D9E75",
    "Projectiles & Ammunition":     "#D85A30",
    "Explosives & Propellants":     "#D4537E",
    "Torpedoes & Mines":            "#888780",
    "Range Finding & Fire Control": "#639922",
    "Wireless & Electrical":        "#BA7517",
    "Armor & Fortification":        "#534AB7",
    "Searchlights & Optics":        "#185FA5",
    "Small Arms":                   "#0F6E56",
    "Transportation & Vehicles":    "#993C1D",
    "Entrenching & Field Equip.":   "#3B6D11",
    "Other":                        "#5F5E5A",
}


def save_tanisha_stacked_bars_svg(out: Path) -> None:
    periods = _TANISHA_PERIODS
    cats = list(_TANISHA_COUNTS.keys())
    totals_per_period = [sum(_TANISHA_COUNTS[c][i] for c in cats) for i in range(len(periods))]
    grand = sum(totals_per_period)

    VB_W, VB_H = 1600, 900
    M_L, M_R, M_T, M_B = 90, 50, 160, 200
    x0, x1, y0, y1 = M_L, VB_W - M_R, M_T, VB_H - M_B
    plot_w, plot_h = x1 - x0, y1 - y0
    upper = ((max(totals_per_period) // 50) + 1) * 50

    def y_for(v): return y1 - (v / upper) * plot_h
    y_ticks = list(range(0, upper + 1, 50))

    col_w = plot_w / len(periods)
    bar_w = col_w * 0.66

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB_W} {VB_H}" preserveAspectRatio="xMidYMid meet">']
    parts.append(_header(
        "Technology Type Prevalence by Period",
        f"BOF Annual Reports, 1897–1908 · 13 categories of subjects considered · "
        f"<b>{grand:,}</b> classified subjects total. Original analysis by <b>Tanisha</b>.",
        VB_W,
    ))

    # Grid
    for v in y_ticks:
        y = y_for(v)
        parts.append(f'<line class="grid-line" x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}"/>')
    for v in y_ticks:
        parts.append(f'<text class="tick" x="{x0 - 12}" y="{y_for(v) + 4:.1f}" text-anchor="end">{v}</text>')
    parts.append(f'<text class="axis-label" x="{x0 - 64}" y="{(y0 + y1) / 2:.1f}" '
                 f'transform="rotate(-90 {x0 - 64} {(y0 + y1) / 2:.1f})" text-anchor="middle">Number of subjects</text>')

    # Stacked bars — same year-column hover pattern as historical_events
    for i, period in enumerate(periods):
        cx = x0 + (i + 0.5) * col_w
        bx = cx - bar_w / 2
        period_total = totals_per_period[i]
        parts.append(f'<g class="year-col" data-period="{period}">')
        parts.append(
            f'<rect class="year-hit" x="{cx - col_w/2:.1f}" y="{y0}" '
            f'width="{col_w:.1f}" height="{plot_h:.1f}" fill="transparent"/>'
        )
        running = 0
        seg_labels = []
        for cat in cats:
            count = _TANISHA_COUNTS[cat][i]
            if count == 0: continue
            top = y_for(running + count); bot = y_for(running)
            mid = (top + bot) / 2
            parts.append('<g class="seg">')
            parts.append(f'<title>{period}: {cat} — {count} subjects</title>')
            parts.append(
                f'<rect class="seg-rect" fill="{_TANISHA_PALETTE[cat]}" '
                f'x="{bx:.1f}" y="{top:.1f}" width="{bar_w:.1f}" '
                f'height="{bot - top:.1f}"/>'
            )
            seg_labels.append(
                f'<text class="seg-label" x="{cx:.1f}" y="{mid + 4:.1f}" '
                f'text-anchor="middle">{count}</text>'
            )
            parts.append('</g>')
            running += count
        parts.extend(seg_labels)
        if period_total > 0:
            parts.append(
                f'<text class="year-total" x="{cx:.1f}" '
                f'y="{y_for(period_total) - 8:.1f}" text-anchor="middle">{period_total}</text>'
            )
        parts.append('</g>')

    # X-axis labels
    parts.append(f'<line class="grid-line" x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke-width="1.2"/>')
    for i, period in enumerate(periods):
        cx = x0 + (i + 0.5) * col_w
        parts.append(f'<text class="tick" x="{cx:.1f}" y="{y1 + 22}" text-anchor="middle">{h(period)}</text>')
    parts.append(f'<text class="axis-label" x="{(x0 + x1) / 2:.1f}" y="{y1 + 50}" text-anchor="middle">BOF reporting period</text>')

    # Legend — 2-column grid below the chart
    legend_y = VB_H - 140
    n_cols = 4
    col_pad = (VB_W - 120) / n_cols
    for idx, cat in enumerate(cats):
        col_i = idx % n_cols
        row_i = idx // n_cols
        lx = 60 + col_i * col_pad
        ly = legend_y + row_i * 28
        parts.append(f'<rect fill="{_TANISHA_PALETTE[cat]}" x="{lx}" y="{ly}" width="14" height="12" rx="1"/>')
        parts.append(f'<text class="legend-text" x="{lx + 20}" y="{ly + 10}">{h(cat)}</text>')

    parts.append('</svg>')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_wrap("Type Prevalence by Period", "\n".join(parts)), encoding="utf-8")


# ───────────────────────────────────────────────────────────────────────────
# 7. TANISHA — Heatmap (category × period)
# ───────────────────────────────────────────────────────────────────────────

_HEATMAP_ORDER = [
    "Projectiles & Ammunition", "Artillery & Guns", "Other",
    "Torpedoes & Mines", "Aerial / Aviation", "Armor & Fortification",
    "Explosives & Propellants", "Range Finding & Fire Control", "Small Arms",
    "Searchlights & Optics", "Entrenching & Field Equip.",
    "Transportation & Vehicles", "Wireless & Electrical",
]
_HEAT_STOPS = [
    (0.00, (230, 241, 251)),  # #E6F1FB
    (0.17, (181, 212, 244)),  # #B5D4F4
    (0.33, (133, 183, 235)),  # #85B7EB
    (0.50, ( 55, 138, 221)),  # #378ADD
    (0.67, ( 24,  95, 165)),  # #185FA5
    (0.83, ( 12,  68, 124)),  # #0C447C
    (1.00, (  4,  44,  83)),  # #042C53
]


def _heat_color(t: float) -> str:
    """Linear interpolation through _HEAT_STOPS."""
    t = max(0.0, min(1.0, t))
    for i in range(len(_HEAT_STOPS) - 1):
        t0, c0 = _HEAT_STOPS[i]
        t1, c1 = _HEAT_STOPS[i + 1]
        if t0 <= t <= t1:
            frac = (t - t0) / (t1 - t0) if t1 > t0 else 0
            rgb = tuple(int(c0[k] + frac * (c1[k] - c0[k])) for k in range(3))
            return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    return "#042C53"


def save_tanisha_heatmap_svg(out: Path) -> None:
    cats = _HEATMAP_ORDER
    periods = _TANISHA_PERIODS
    max_val = max(max(_TANISHA_COUNTS[c]) for c in cats)

    VB_W, VB_H = 1600, 900
    M_L, M_R, M_T, M_B = 280, 60, 160, 110
    x0, x1, y0, y1 = M_L, VB_W - M_R, M_T, VB_H - M_B
    plot_w, plot_h = x1 - x0, y1 - y0

    cell_w = plot_w / len(periods)
    cell_h = plot_h / len(cats)
    cell_gap = 2

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB_W} {VB_H}" preserveAspectRatio="xMidYMid meet">']
    # Per-row + per-column re-light rules. CSS :has() lets a cell hover
    # affect every other cell sharing its row or column.
    inline_css = []
    for yi in range(len(cats)):
        inline_css.append(
            f"svg:has(.hm-r{yi}:hover) .hm-r{yi} .hm-rect "
            f"{{ opacity: 1 !important; filter: brightness(1.06); }}"
        )
        inline_css.append(
            f"svg:has(.hm-r{yi}:hover) .hm-r{yi} .hm-num {{ opacity: 1 !important; }}"
        )
    for xi in range(len(periods)):
        inline_css.append(
            f"svg:has(.hm-c{xi}:hover) .hm-c{xi} .hm-rect "
            f"{{ opacity: 1 !important; filter: brightness(1.06); }}"
        )
        inline_css.append(
            f"svg:has(.hm-c{xi}:hover) .hm-c{xi} .hm-num {{ opacity: 1 !important; }}"
        )
    parts.append(f'<style>{"".join(inline_css)}</style>')

    parts.append(_header(
        "Technology Prevalence Heatmap by Period",
        f"BOF Annual Reports, 1897–1908 · cell shade = subject count (capped at {max_val}). "
        f"<b>Hover a cell to spotlight its row and column.</b> Original analysis by <b>Tanisha</b>.",
        VB_W,
    ))

    # Row + column totals (for the hover summary card)
    row_totals = {cat: sum(_TANISHA_COUNTS[cat]) for cat in cats}
    col_totals = [sum(_TANISHA_COUNTS[c][i] for c in cats) for i in range(len(periods))]

    # Cells. Each cell gets row + col data attributes so CSS can cross-light
    # the entire row and column on hover.
    for yi, cat in enumerate(cats):
        for xi, period in enumerate(periods):
            count = _TANISHA_COUNTS[cat][xi]
            t = count / max_val if max_val else 0
            color = _heat_color(t)
            cx = x0 + xi * cell_w + cell_gap / 2
            cy = y0 + yi * cell_h + cell_gap / 2
            w_ = cell_w - cell_gap
            h_ = cell_h - cell_gap
            text_color = "white" if count > 50 else "#0C447C"
            parts.append(f'<g class="hm-cell hm-r{yi} hm-c{xi}">')
            parts.append(f'<title>{cat} · {period}: {count} subjects</title>')
            parts.append(
                f'<rect class="hm-rect" fill="{color}" x="{cx:.1f}" y="{cy:.1f}" '
                f'width="{w_:.1f}" height="{h_:.1f}"/>'
            )
            parts.append(
                f'<text class="hm-num" x="{cx + w_/2:.1f}" '
                f'y="{cy + h_/2 + 5:.1f}" '
                f'font-family="Source Serif 4, Georgia, serif" font-size="13" '
                f'fill="{text_color}" text-anchor="middle">{count}</text>'
            )
            # Hover detail badge (centered on the cell)
            badge_w = 140
            badge_h = 58
            bx = max(x0, min(cx + w_/2 - badge_w/2, x1 - badge_w))
            by_anchor = cy + h_/2 - badge_h/2
            by = max(y0, min(by_anchor, y1 - badge_h))
            parts.append(
                f'<g class="hm-badge" pointer-events="none">'
                f'<rect x="{bx:.1f}" y="{by:.1f}" width="{badge_w}" height="{badge_h}" '
                f'rx="4" fill="{PAPER_SOFT}" stroke="{color}" stroke-width="1.5"/>'
                f'<text x="{bx + badge_w/2:.1f}" y="{by + 18:.1f}" text-anchor="middle" '
                f'font-family="Source Serif 4, Georgia, serif" font-weight="700" '
                f'font-size="12" fill="{TEXT_DARK}">{h(cat)}</text>'
                f'<text x="{bx + badge_w/2:.1f}" y="{by + 36:.1f}" text-anchor="middle" '
                f'font-family="Inter, sans-serif" font-size="11" fill="{TEXT_MID}">{h(period)}</text>'
                f'<text x="{bx + badge_w/2:.1f}" y="{by + 52:.1f}" text-anchor="middle" '
                f'font-family="Inter, sans-serif" font-weight="700" font-size="13" '
                f'fill="{color}">{count} subjects</text>'
                f'</g>'
            )
            parts.append('</g>')

    # Y labels (categories)
    for yi, cat in enumerate(cats):
        cy = y0 + (yi + 0.5) * cell_h
        parts.append(f'<text class="y-label-vert" x="{x0 - 14}" y="{cy + 5:.1f}">{h(cat)}</text>')

    # X labels (periods)
    for xi, period in enumerate(periods):
        cx = x0 + (xi + 0.5) * cell_w
        parts.append(f'<text class="tick" x="{cx:.1f}" y="{y1 + 22}" text-anchor="middle">{h(period)}</text>')
    parts.append(f'<text class="axis-label" x="{(x0 + x1) / 2:.1f}" y="{y1 + 50}" text-anchor="middle">BOF reporting period</text>')

    # Color scale legend (vertical strip on right side beneath chart)
    bar_x = x1 - 200
    bar_y = y1 + 70
    bar_w = 180
    bar_h = 10
    steps = 60
    for s in range(steps):
        t = s / (steps - 1)
        sx = bar_x + t * bar_w
        sw = bar_w / steps + 0.6
        parts.append(f'<rect fill="{_heat_color(t)}" x="{sx:.1f}" y="{bar_y}" width="{sw:.1f}" height="{bar_h}"/>')
    parts.append(f'<text class="tick" x="{bar_x:.1f}" y="{bar_y + bar_h + 14:.1f}" text-anchor="start">0</text>')
    parts.append(f'<text class="tick" x="{bar_x + bar_w:.1f}" y="{bar_y + bar_h + 14:.1f}" text-anchor="end">{max_val}</text>')
    parts.append(f'<text class="axis-label" x="{bar_x + bar_w / 2:.1f}" y="{bar_y - 6:.1f}" text-anchor="middle">Subjects</text>')

    parts.append('</svg>')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_wrap("Prevalence Heatmap", "\n".join(parts)), encoding="utf-8")


__all__ = [
    "save_pareto_svg",
    "save_master_timeline_svg",
    "save_historical_events_svg",
    "save_yunha_treemap_svg",
    "save_yunha_trajectory_svg",
    "save_tanisha_stacked_bars_svg",
    "save_tanisha_heatmap_svg",
]
