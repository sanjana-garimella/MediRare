---
name: data-rules
description: Rules for data files in data/biomedical/ and schemas/. Loaded when editing those paths.
globs:
  - "data/biomedical/**"
  - "schemas/**"
  - "tests/**"
---
# Data and schema rules

## Biomedical data
- `annotated_cases.csv` is the gold-standard hand-annotated set. Do not overwrite it with synthetic or auto-extracted data — append only, with human review.
- `hpo_mapping_table.csv` must include all three columns: `hpo_id`, `hpo_term`, `phenotype_category`. Do not add a disease without HPO entries.
- `label_guide.md` is the annotation specification. Update it when adding a new disease.

## Schemas
- All pipeline outputs must validate against `schemas/case_report.py`, `schemas/extracted_figure.py`, or `schemas/merged_record.py`. No raw dict returns.
- Run `python3 schemas/validate_jsonl.py` after any bulk write to processed data.
- Do not add a new schema file without updating `tests/test_schemas.py`.

## Disease scope
- **Active (you own):** SLE, Sjögren's — build end-to-end pipeline for these.
- **Undergrad scope:** MCTD, Inflammatory Myositis, Antiphospholipid Syndrome — do not block on these.
- When adding a new disease, always add: (1) entry in `DISEASE_TERMS` in `nlp/fetch_pubmed_case_reports.py`, (2) rows in `hpo_mapping_table.csv`, (3) section in `label_guide.md`.
