"""Wrap every Plotly chart HTML in output/ with centering + paper theming.

Plotly's default export puts the chart in the top-left of a white viewport with
no padding. This script post-processes those files so each chart page:
  - centers in viewport (flex layout)
  - uses the project's paper-background palette
  - adds breathing-room padding
  - sets the page <title> to the chart filename for nicer tab labels

Idempotent — running twice does the same thing as running once.
Run: `python style_charts.py`  (after any chart regen).
"""
from __future__ import annotations

import re
from pathlib import Path

OUTPUT = Path(__file__).parent / "output"

CHART_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&display=swap" rel="stylesheet">
<style id="bof-chart-frame">
  /* ── Base ─────────────────────────────────────────────────────────── */
  html, body {
    margin: 0;
    padding: 0;
    background: #EAE3D8;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #1A1A2E;
    overflow-x: hidden;
  }
  body {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* ── Header strip ─────────────────────────────────────────────────── */
  .bof-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 28px;
    background: #FBF6E6;
    border-bottom: 1px solid #D6CEBF;
    font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace;
    font-size: 11px;
    letter-spacing: 1.2px;
    color: #55556A;
    flex-shrink: 0;
  }
  .bof-bar .bof-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    color: inherit;
    text-decoration: none;
    min-width: 0;
  }
  .bof-bar .bof-brand svg {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
    color: #C9A24C;
    transition: transform .5s cubic-bezier(.2,.8,.2,1);
  }
  .bof-bar .bof-brand:hover svg { transform: rotate(45deg); }
  .bof-bar .bof-brand strong {
    color: #1A1A2E;
    font-weight: 700;
    letter-spacing: 1.4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .bof-bar a.bof-back {
    color: #55556A;
    text-decoration: none;
    letter-spacing: 1.2px;
    white-space: nowrap;
  }
  .bof-bar a.bof-back:hover { color: #C9A24C; }

  /* ── Chart container ──────────────────────────────────────────────── */
  .bof-chart-wrap {
    flex: 1;
    display: flex;
    align-items: stretch;             /* chart fills full height of wrap */
    justify-content: center;
    padding: 16px 24px 20px;
    box-sizing: border-box;
    min-height: 0;
    overflow-x: auto;
    overflow-y: hidden;
    -webkit-overflow-scrolling: touch;
  }
  /* Chart fills BOTH dimensions of the wrap (which is flex:1, so it takes
     all remaining viewport after the header). On narrow screens, min-width
     forces horizontal scroll instead of collapsing the chart. */
  .plotly-graph-div {
    margin: 0 auto !important;
    width: 100% !important;
    height: 100% !important;
    min-width: 720px;
    min-height: 520px;
    flex-shrink: 0;
  }
  .plotly-graph-div .gtitle { font-family: 'Source Serif 4', Georgia, serif !important; }
  .modebar-container, .modebar { display: none !important; }
  .plotly-graph-div .bartext { font-family: 'Inter', sans-serif !important; }

  /* Subtle scroll hint on narrow screens */
  .bof-chart-wrap::-webkit-scrollbar { height: 10px; }
  .bof-chart-wrap::-webkit-scrollbar-track { background: transparent; }
  .bof-chart-wrap::-webkit-scrollbar-thumb {
    background: rgba(201, 162, 76, 0.35);
    border-radius: 5px;
  }
  .bof-chart-wrap::-webkit-scrollbar-thumb:hover {
    background: rgba(201, 162, 76, 0.65);
  }

  /* ── Responsive breakpoints ───────────────────────────────────────── */

  /* Ultra-wide (1920+) */
  @media (min-width: 1920px) {
    .bof-chart-wrap { padding: 20px 40px 28px; }
    .bof-bar { padding: 16px 40px; font-size: 12px; }
  }

  /* Large desktop (1280-1919) */
  @media (min-width: 1280px) and (max-width: 1919px) {
    .bof-chart-wrap { padding: 18px 32px 22px; }
  }

  /* Small laptop / tablet landscape (900-1279) */
  @media (min-width: 900px) and (max-width: 1279px) {
    .bof-chart-wrap { padding: 14px 18px 18px; }
    .bof-bar { padding: 12px 22px; }
  }

  /* Tablet portrait (600-899) */
  @media (min-width: 600px) and (max-width: 899px) {
    .bof-bar { padding: 12px 18px; font-size: 10.5px; }
    .bof-chart-wrap { padding: 10px 12px 14px; }
    .plotly-graph-div { min-height: 440px; }
  }

  /* Mobile (<600): chart keeps 720px min-width and scrolls horizontally.
     Hint banner tells the user the chart is scrollable. */
  @media (max-width: 599px) {
    .bof-bar {
      padding: 10px 12px;
      font-size: 9.5px;
      letter-spacing: 0.9px;
      gap: 8px;
    }
    .bof-bar .bof-brand { gap: 6px; }
    .bof-bar .bof-brand strong { letter-spacing: 1px; font-size: 10px; }
    .bof-bar .bof-brand svg { width: 14px; height: 14px; }
    .bof-chart-wrap {
      padding: 8px 6px 16px;
      align-items: flex-start;
    }
    .plotly-graph-div { min-height: 420px; }
    body::before {
      content: "↔ swipe to scroll chart";
      position: fixed;
      bottom: 8px;
      right: 8px;
      padding: 4px 8px;
      background: rgba(201, 162, 76, 0.92);
      color: #1A1A2E;
      font-family: 'JetBrains Mono', monospace;
      font-size: 9px;
      letter-spacing: 0.8px;
      border-radius: 4px;
      pointer-events: none;
      z-index: 100;
      animation: bof-hint-fade 5s ease-in forwards;
    }
  }
  @keyframes bof-hint-fade {
    0%, 60% { opacity: 1; }
    100% { opacity: 0; }
  }

  /* Very small (<380): hide "back to dashboard" text, keep just back arrow */
  @media (max-width: 379px) {
    .bof-bar a.bof-back { font-size: 16px; }
    .bof-bar a.bof-back .bof-back-text { display: none; }
  }
</style>
<script id="bof-chart-resize">
  // Every Plotly chart hard-codes its own height/width on the div inline.
  // Strip those, set its own layout to autosize, then resize from the
  // CSS-driven container dimensions. This is what makes every chart fill
  // its frame identically regardless of what the Python writer set.
  (function() {
    function fitAllCharts() {
      if (typeof Plotly === 'undefined') return;
      document.querySelectorAll('.plotly-graph-div').forEach(function(div) {
        try {
          // Strip Plotly's inline width/height so the CSS wins
          div.style.removeProperty('height');
          div.style.removeProperty('width');
          // Tell Plotly the chart is autosizing — this disables any
          // Python-side fixed height/width baked into the layout.
          Plotly.relayout(div, {
            autosize: true,
            width: null,
            height: null,
          });
          Plotly.Plots.resize(div);
        } catch (e) { /* ignore */ }
      });
    }
    var t;
    window.addEventListener('resize', function() {
      clearTimeout(t);
      t = setTimeout(fitAllCharts, 80);
    });
    window.addEventListener('orientationchange', function() {
      setTimeout(fitAllCharts, 200);
    });
    // First paint: do it as soon as the document is ready, and again after
    // load to catch lazy-init charts.
    if (document.readyState === 'complete') {
      setTimeout(fitAllCharts, 30);
    } else {
      window.addEventListener('load', function() { setTimeout(fitAllCharts, 30); });
      document.addEventListener('DOMContentLoaded', function() { setTimeout(fitAllCharts, 60); });
    }
  })();
</script>
"""

# Header strip that gets injected at the start of <body>
CHART_HEADER = """
<div class="bof-bar">
  <a class="bof-brand" href="/" title="Back to dashboard">
    <svg viewBox="0 0 64 64" aria-hidden="true">
      <path fill-rule="evenodd" clip-rule="evenodd" d="M32 3 L42 22 L61 32 L42 42 L32 61 L22 42 L3 32 L22 22 Z M32 26 A6 6 0 1 0 32 38 A6 6 0 1 0 32 26 Z" fill="currentColor"/>
      <circle cx="32" cy="32" r="2.2" fill="currentColor"/>
    </svg>
    <strong>FORTIFY THE ORDNANCE</strong>
  </a>
  <a class="bof-back" href="/" aria-label="Back to dashboard">←<span class="bof-back-text">&nbsp;back to dashboard</span></a>
</div>
<div class="bof-chart-wrap">
"""

CHART_FOOTER = """
</div>
"""

SENTINEL_OPEN = "<style id=\"bof-chart-frame\">"
SENTINEL_HDR = "<div class=\"bof-bar\">"


def patch_one(path: Path) -> bool:
    """Inject the chart-frame style + header into a single HTML file.

    Re-runnable: if already patched, strip the prior injection and re-apply so
    iterations on the wrapper actually take effect.
    """
    html = path.read_text(encoding="utf-8")

    # If already patched, strip the old block first so we can re-apply fresh.
    if SENTINEL_OPEN in html:
        html = re.sub(
            r"<link rel=\"preconnect\".*?<style id=\"bof-chart-frame\">.*?</style>",
            "",
            html,
            count=1,
            flags=re.DOTALL,
        )
        html = re.sub(
            r"<div class=\"bof-bar\">.*?<div class=\"bof-chart-wrap\">",
            "",
            html,
            count=1,
            flags=re.DOTALL,
        )
        # Close-wrap div: strip a single trailing </div> that we previously added
        # right before </body>. Plotly's own structure has no orphan </div>, so
        # this is the one we inserted.
        html = re.sub(
            r"\s*</div>\s*(?=</body>)",
            "",
            html,
            count=1,
        )

    # Inject head CSS
    if "</head>" in html:
        html = html.replace("</head>", CHART_CSS + "</head>", 1)
    else:
        return False

    # Inject header strip + chart wrapper opening div right after <body...>
    html = re.sub(r"(<body[^>]*>)", r"\1" + CHART_HEADER, html, count=1)
    # Close the chart wrapper just before </body>
    html = html.replace("</body>", CHART_FOOTER + "</body>", 1)

    path.write_text(html, encoding="utf-8")
    return True


# Files that are hand-coded interactive pages (not Plotly exports) and must
# be left alone — the post-processor's CSS/JS will conflict with their own.
SKIP_FILES = {
    "technology_review_timeline.html",
}


def main() -> None:
    targets = sorted(OUTPUT.glob("*.html"))
    if not targets:
        print(f"No HTML files in {OUTPUT}")
        return

    patched = 0
    skipped = 0
    for path in targets:
        if path.name in SKIP_FILES:
            print(f"  skip     {path.name}  (hand-coded, not a Plotly export)")
            skipped += 1
            continue
        if patch_one(path):
            patched += 1
            print(f"  patched  {path.name}")
        else:
            skipped += 1

    print(f"\n{patched} patched · {skipped} skipped/already-styled · {len(targets)} total")


if __name__ == "__main__":
    main()
