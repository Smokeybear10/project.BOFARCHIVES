# Fortify the Ordnance | A working archive, 1897–1908

<picture>
  <img alt="Star Fort mark" align="right" width="80" src="data:image/svg+xml;utf8,&lt;svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'&gt;&lt;path fill-rule='evenodd' clip-rule='evenodd' d='M32 3 L42 22 L61 32 L42 42 L32 61 L22 42 L3 32 L22 22 Z M32 26 A6 6 0 1 0 32 38 A6 6 0 1 0 32 26 Z' fill='%23C9A24C'/&gt;&lt;circle cx='32' cy='32' r='2.2' fill='%23C9A24C'/&gt;&lt;/svg&gt;">
</picture>

Historical analysis pipeline and live filterable dashboard for the U.S. Board of Ordnance & Fortification — 1,901 weapon proposals (1897–1908) crossed with military budget appropriations (1865–1920).

**Local dashboard runs at http://localhost:2104** — port is fixed, do not change. Brand kit at `/brand.html`.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# one-time: clone the private research-data repo + symlink it as Data/
# requires gh auth login with read access to Smokeybear10/801-DATA.FORTIFY
./bootstrap-data.sh

# regenerate chart data + visualizations (only needed if Data/ contents changed)
python run_bof_analysis.py
python run_budget_analysis.py
python run_combined_analysis.py
python run_master_ledger.py      # 1888-1919 master ledger + waterfall + pareto

# rebuild paper-themed dashboard charts
python regenerate_paper.py

# launch the dashboard
./serve.sh
```

Open **http://localhost:2104** in a browser.

## The Dashboard

`./serve.sh` boots a static server on port **2104** and serves the root `index.html`. The dashboard has four views — switch between them with the tabs below the topbar.

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

**Timeline view** (curated · 251 technologies, 1897–1908):
- Hand-classified technology entries grouped into 9 fine-grained categories (rangefinding, artillery, firearms, aerial, torpedo, armor, communication, transport, equipment)
- Sticky-column matrix — first column is the technology, then 9 columns for the BOF report periods. Each cell is a colored bar showing outcome at that period
- Hover any bar for the original action text · multi-period entries get a count badge
- Filter by category, outcome, or text search

**Spending view** (BOF-specific · 1888–1920):
- Annual congressional appropriations to the Board (33 acts) overlaid on individual research allotments (~507 line items)
- Filter by year range, status (active vs revoked), or search project descriptions
- Charts: appropriations vs allotments timeline, active/revoked split donut, top 15 allotments by amount
- Records table — every individual line item with date, amount, status; click row title for full description and notes
- Separate CSV export

**Shared:**
- Theme switcher — Paper (default) / Slate, persisted to localStorage
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
fortify-the-ordnance/
├── index.html                        # dashboard (root) — served at localhost:2104
├── brand.html                        # brand kit page
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
├── Data → ~/Github/DATA/FortifyData  # symlink; raw data lives outside the repo (gitignored)
│   ├── Subjects Considered Data Visualization Assignment/    # subjects-considered xlsx
│   ├── Defense Budget Visualization Assignment/              # Military Budgets xlsx
│   ├── Appropriations/                                       # year-on-year financials
│   ├── Technologies/                                         # tech memos + subjects copies
│   ├── BOF Timeline Assignment/                              # timeline xlsx
│   ├── Crozier and Lewis/                                    # research PDFs
│   └── Misc/
├── Graphs/                           # static screenshots for README/site
├── bof_pipeline/
│   ├── config.py                     # classification rules, column aliases
│   ├── transform.py                  # data cleaning and structuring
│   ├── visualize.py                  # proposal chart generation
│   ├── budget.py / budget_visualize.py
│   └── combined_visualize.py
└── output/                           # generated HTML charts + CSVs (committed; served by dashboard)
```

## Dev Server

The local server is **always port 2104**. Start it with:

```bash
./serve.sh
```

`serve.sh` kills any process holding 2104 first, then boots `python3 -m http.server 2104` from the repo root. Always use `./serve.sh` — the port is fixed at 2104 across this project.

## Customization

Classification rules (status keywords, technology clusters, proposer patterns) live in `bof_pipeline/config.py`. Drop additional BOF Excel files into `Data/Subjects Considered Data Visualization Assignment/` and rerun — the pipeline batches all files automatically.

## Data

Raw research data is **not** in this repo. It lives in a separate **private** GitHub repo: [`Smokeybear10/801-DATA.FORTIFY`](https://github.com/Smokeybear10/801-DATA.FORTIFY). This dashboard repo accesses it through the `Data/` symlink (which is gitignored). Only cleaned outputs in `output/*.csv` ship with the public dashboard.

To set it up on a fresh clone:

```bash
./bootstrap-data.sh
```

That script:
1. Verifies you have `gh` authenticated with read access to the private data repo
2. Clones (or updates) `801-DATA.FORTIFY` into `~/Github/DATA/FORTIFY/`
3. Symlinks `./Data → ~/Github/DATA/FORTIFY/`
4. Verifies the three folders the pipelines expect (Subjects, Defense Budget, Appropriations)

It's idempotent — run it any time you want to refresh the data from the private repo.

The pipelines all read from `Data/`. If your raw data lives somewhere else, edit `bootstrap-data.sh` to point at it, or symlink `Data/` manually.

---

Built by Thomas Ou
