# project.MilitaryVisualization

Qualitative-to-Quantitative historical analysis pipeline for BOF 1901-1902 records.

## What this does

- Converts non-numerical BOF records into structured fields.
- Classifies `Action` into:
  - `Approved`
  - `Rejected`
  - `Investigating` (pending/deferred/filed)
- Tags `Subject` into technology clusters (Artillery, Explosives, etc.).
- Infers proposer type (`Private` vs `Government`) to evaluate approval bias.
- Produces reproducible outputs and interactive visuals using pure Python.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run (supports 9-file batch)

Place CSV files in a folder like `data/` (for example, 9 yearly or volume files), then:

```bash
python run_bof_analysis.py --input-dir data --output-dir output
```

## Outputs

- `output/all_structured_records.csv`:
  - normalized text fields
  - `status`
  - `primary_cluster`
  - `proposer_type`
  - binary indicators for analysis
- `output/approval_ratio_by_cluster_1901.csv`
- `output/proposer_success_rate_by_year.csv`
- `output/flow_cluster_to_status.html` (Sankey flow)
- `output/network_proposer_cluster.html` (Network map)
- `output/dashboard_1901_ratio.html` (1901 approval ratio dashboard)

## Notes on adaptation

- Historical wording rules are configured in `bof_pipeline/config.py`.
- If your headers differ, the transformer auto-maps common aliases.
- You can extend dictionaries to improve historical terminology coverage.
