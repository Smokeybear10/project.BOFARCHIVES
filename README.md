# BOF Archive | Military Data Visualization

Historical analysis pipeline and live filterable dashboard for U.S. Board of Ordnance & Fortification records (1897-1908) and military budget appropriations (1865-1920).

**Local dashboard runs at http://localhost:2104** — port is fixed, do not change.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# regenerate raw chart data (only needed if Subject/ or budget xlsx changed)
python run_bof_analysis.py --input-dir Subject --output-dir output
python run_budget_analysis.py --input "Military Budgets, 1865-1920.xlsx" --output-dir output
python run_combined_analysis.py

# rebuild paper-themed dashboard charts
python regenerate_paper.py

# launch the dashboard
./serve.sh
```

Open **http://localhost:2104** in a browser.

## The Dashboard

`./serve.sh` boots a static server on port **2104** and serves the root `index.html`. The dashboard has two views — switch between them with the tabs below the topbar.

**Proposals view** (1897–1908, ~1,901 records):
- Live filters — year range, cluster, status, proposer type, full-text search
- Cross-filter charts — click any chart slice to filter the rest of the dashboard
- Quick presets — Approved / 1901 surge / Private inventors / Communications (0 approved) / Artillery
- Paginated records table with sort + click-row-for-detail modal showing full board action and reasoning text
- CSV export of the current filtered slice

**Budget view** (1865–1920, ~110 appropriations):
- Year range, branch (Army/Navy), inflation toggle (nominal vs 2025-adjusted)
- Era presets — Reconstruction / Gilded Age / Spanish-American / Pre-WWI / WWI mobilization
- KPIs — total spend, peak year, average per year, Army share, years covered
- Charts — appropriations stacked over time, branch mix donut, decade totals, year-over-year change
- Paginated table sorted by year/branch/amount/decade, separate CSV export

**Shared:**
- Theme switcher — Paper (default) / Slate / Terminal / Broadsheet, persisted to localStorage
- URL hash sync — view + filters serialized for shareable links
- Keyboard shortcuts — `/` focus search · `esc` close modal · `r` reset filters

The static archive grid below the live charts links to 9 paper-themed Plotly HTMLs in `charts/`.

## What It Does

**Proposal Analysis (1897-1908)**
- Parses 1,901 weapon proposals submitted to the BOF from Excel source files
- Classifies by technology cluster, board decision, and proposer type
- Generates Sankey diagram, approval rate trends, and per-year breakdowns

| | |
|---|---|
| ![Sankey](Graphs/proposal-sankey.png) | ![Success Rates](Graphs/proposal-success.png) |
| Proposal flow from cluster to decision | Government vs. private approval rates |

**Budget Analysis (1865-1920)**
- Cleans and structures Army + Navy appropriation data across 55 fiscal years
- Supports nominal and 2025 inflation-adjusted values
- Generates stacked area charts, treemaps, and proportional share charts

| | |
|---|---|
| ![Area Chart](Graphs/budget-area.png) | ![Treemap](Graphs/budget-treemap.png) |
| Army + Navy appropriations over time | Spending by decade and branch |

**Combined Analysis (1897-1908)**
- Crosses proposal data with budget data for the BOF period
- Technology investment chart: proposal volume by cluster overlaid on military budget
- Technology timeline: bubble chart showing when each cluster was active
- Technology prevalence: 100% stacked area of shifting priorities over time

## Tech Stack

| Layer | Tools |
|-------|-------|
| Pipeline | Python, pandas |
| Visualization | Plotly |
| Hosting | GitHub Pages |

## Project Structure

```
project.BOFARCHIVE/
├── index.html                        # dashboard (root) — served at localhost:2104
├── style.css                         # dashboard styles, 4 themes
├── app.js                            # dashboard logic — filters, charts, table, modal
├── charts/                           # paper-themed Plotly HTMLs + PNGs
├── serve.sh                          # ./serve.sh → http://localhost:2104
├── regenerate_paper.py               # rebuild paper-themed charts
├── index-gallery.html                # earlier card-grid landing (preserved)
├── run_bof_analysis.py               # proposal pipeline entry point
├── run_budget_analysis.py            # budget pipeline entry point
├── run_combined_analysis.py          # combined subjects + budget charts
├── requirements.txt
├── Subject/                          # input BOF Excel files
├── Military Budgets, 1865-1920.xlsx  # input budget data
├── Graphs/                           # static screenshots for README/site
├── bof_pipeline/
│   ├── config.py                     # classification rules, column aliases
│   ├── transform.py                  # data cleaning and structuring
│   ├── visualize.py                  # proposal chart generation
│   ├── budget_visualize.py           # budget chart generation
│   └── combined_visualize.py         # combined analysis charts
└── output/                           # raw generated HTML charts and CSVs
```

## Dev Server

The local server is **always port 2104**. Start it with:

```bash
./serve.sh
```

`serve.sh` kills any process holding 2104 first, then boots `python3 -m http.server 2104` from the repo root. Always use `./serve.sh` — the port is fixed at 2104 across this project.

## Customization

Classification rules (status keywords, technology clusters, proposer patterns) live in `bof_pipeline/config.py`. Drop additional BOF Excel files into `Subject/` and rerun — the pipeline batches all files automatically.

---

Built by Thomas Ou
