# BOF Archive | Military Data Visualization

Historical analysis pipeline for U.S. Board of Ordnance & Fortification records (1897-1908) and military budget appropriations (1865-1920).

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# run proposal analysis
python run_bof_analysis.py --input-dir Subject --output-dir output

# run budget analysis
python run_budget_analysis.py --input "Military Budgets, 1865-1920.xlsx" --output-dir output

# run combined analysis (subjects + budget, 1897-1908)
python run_combined_analysis.py
```

All charts are interactive HTML files in `output/`. Open them by double-clicking or:

```bash
open output/*.html
```

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
├── index.html                        # GitHub Pages landing page
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
└── output/                           # all generated HTML charts and CSVs
```

## Customization

Classification rules (status keywords, technology clusters, proposer patterns) live in `bof_pipeline/config.py`. Drop additional BOF Excel files into `Subject/` and rerun — the pipeline batches all files automatically.

---

Built by Thomas Ou
