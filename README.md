# Fortify the Ordnance | BOF Archive Dashboard

An interactive archive of every weapon proposal and research dollar that passed through the U.S. Board of Ordnance & Fortification — the federal body that decided which 19th-century inventions the Army should adopt. 1,691 proposals, 1,144 allotments, 202 technologies, 33 years (1888–1920).

The source material — Excel spreadsheets, scanned PDFs, hand-transcribed reports — is unreadable as raw files. This is the readable version.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

./bootstrap-data.sh    # clone the private data repo, symlink as Data/ (needs gh auth)
./serve.sh             # boot dashboard at localhost:2104
```

Open http://localhost:2104.

To regenerate charts after data changes:

```bash
python run_bof_analysis.py
python run_budget_analysis.py
python run_combined_analysis.py
python run_master_ledger.py
python run_historical_timeline.py
python run_yunha_charts.py
python run_tanisha_charts.py
python regenerate_paper.py
```

## What It Does

**Proposals** — every weapon idea submitted 1897–1908 with the Board's verdict. Live filters by year, cluster, status, proposer type. Click any chart slice to cross-filter the rest of the dashboard.

**Budget** — the entire U.S. military budget 1865–1920 (Army + Navy), with a nominal/2025-adjusted toggle and era presets (Reconstruction, Gilded Age, pre-WWI, WWI mobilization).

**Timeline** — sticky-column matrix of 251 hand-classified technologies across nine BOF reporting periods. Color-coded by outcome; hover any cell for the original action text.

**Spending** — the money trail. Annual congressional appropriations to the Board overlaid on every individual research allotment, including revocations.

| | |
|---|---|
| ![Sankey](Graphs/proposal-sankey.png) | ![Success Rates](Graphs/proposal-success.png) |
| Proposal flow from cluster to decision | Government vs. private approval rates |
| ![Area Chart](Graphs/budget-area.png) | ![Treemap](Graphs/budget-treemap.png) |
| Army + Navy appropriations over time | Spending by decade and branch |

Shared: theme switcher, URL-hash filter sync, keyboard shortcuts (`/` search · `esc` close · `r` reset), CSV export on every view.

## Tech Stack

| Layer | Tools |
|-------|-------|
| Pipeline | Python, pandas |
| Visualization | Plotly |
| Dashboard | Vanilla HTML/JS, static CSV reads |
| Hosting | GitHub Pages |

## Project Structure

```
fortify-the-ordnance/
├── index.html              # dashboard — served at localhost:2104
├── about.html              # project background, team, data sources
├── app.js                  # filters, charts, table, modal
├── style.css               # dashboard styles
├── serve.sh                # boots http.server on port 2104
├── bootstrap-data.sh       # clones the private data repo + symlinks Data/
├── run_*.py                # per-pipeline entry points
├── regenerate_paper.py     # rebuild paper-themed charts
├── bof_pipeline/           # cleaning, classification, chart generation
├── Data → ~/Github/DATA/   # symlink to private data repo (gitignored)
├── output/                 # generated CSVs + HTML charts (served by dashboard)
├── charts/                 # paper-themed Plotly HTMLs + PNGs
├── Graphs/                 # static screenshots
└── team/                   # researcher-specific source (Tanisha's R script, etc.)
```

## Data

Raw research data lives in a separate private repo: [`Smokeybear10/801-DATA.FORTIFY`](https://github.com/Smokeybear10/801-DATA.FORTIFY). `bootstrap-data.sh` clones it to `~/Github/DATA/FORTIFY/` and symlinks `./Data` to it. The symlink is gitignored — only cleaned `output/*.csv` ship with the dashboard. Idempotent; rerun to refresh.

Classification rules (status keywords, technology clusters, proposer patterns) live in `bof_pipeline/config.py`.

## Team

- **Thomas Ou** — pipeline architecture, dashboard, brand identity, master ledger 1888–1919, historical events timeline
- **Yunha** — financial × technology investment analysis (treemap, trajectory) built off the master 1888–1918 allotment ledger, plus the canonical visual site at [paull0318.github.io/BOF-Visuals-20260511](https://paull0318.github.io/BOF-Visuals-20260511/) extending coverage back to 1888
- **Paul B** — technology review timeline 1888–1916, hand-classified into nine fine-grained categories
- **Tanisha** — technology type prevalence (stacked bars, heatmap, ranking) across 13 categories × 9 reporting periods. Original R/ggplot2 at [`team/tanisha/technology_prevalence.R`](team/tanisha/technology_prevalence.R), Plotly port at [`bof_pipeline/tanisha_charts.py`](bof_pipeline/tanisha_charts.py)

---

Built by Thomas Ou
