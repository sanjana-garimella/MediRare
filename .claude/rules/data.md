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
- **Active (12 diseases, chosen by real PubMed misdiagnosis-focused literature volume):** Sarcoidosis, SLE, IgG4-related disease, Guillain-Barre syndrome, Granulomatosis with polyangiitis, Myasthenia gravis, Behcet's disease, Castleman disease, Neuromyelitis optica, Antiphospholipid Syndrome, Sjogren's, MCTD.
- **Out of scope:** Inflammatory Myositis (too thin, 17 total records, did not make the cut) and any disease not on the list above. Do not fetch, extract, or process data for diseases outside this list without confirming with Sanjana first.
- Strategy: pool data across all 12 for training/fine-tuning a single model, evaluate per-disease. This is aimed at a HuggingFace model release plus a paper, not a per-disease pipeline.
- When adding a new disease, always add: (1) entry in `DISEASE_TERMS` in `nlp/fetch_pubmed_case_reports.py`, (2) rows in `hpo_mapping_table.csv`, (3) section in `label_guide.md`.
