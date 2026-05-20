# Loblaw Bio — Clinical Trial Dashboard

## How to Run

### Setup
```bash
make setup
```

### Run Pipeline
```bash
make pipeline
```

### Start Dashboard
```bash
make dashboard
```
Then open http://127.0.0.1:8050

---

## Database Schema

Three tables in 3NF:

- **subjects** — one row per patient (subject_id, project, condition, age, sex, treatment, response)
- **samples** — one row per biological sample (sample_id, subject_id, sample_type, time_from_treatment_start)
- **cell_counts** — one row per sample with the five population counts (b_cell, cd8_t_cell, cd4_t_cell, nk_cell, monocyte)

**Rationale:** Separating subjects from samples avoids repeating demographic data per sample. cell_counts is split from samples so analytical queries on counts stay clean. This scales well — adding hundreds of projects means only new subject/sample rows, no schema changes. New cell types = new columns or a pivoted long-form table.

---

## Code Structure

- `load_data.py` — initializes SQLite DB and loads cell-count.csv
- `analysis.py` — all analytical functions (frequency table, stats, subset queries)
- `dashboard.py` — Dash interactive dashboard importing from analysis.py
- `requirements.txt` — dependencies

---

## Key Findings

- **cd4_t_cell** is the only population with a statistically significant difference between responders and non-responders (p = 0.013)
- Avg B cells for melanoma male responders at baseline: **10401.28**