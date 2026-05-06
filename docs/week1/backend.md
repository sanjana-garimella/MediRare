# Week 1 Guide: Backend (Schemas + Simple Validator)

Student level: early undergrad. Week 1 is about clean data contracts, not ML.

Time budget: 5-7 hours.

## Phase 1: Setup (Git + Python)

```bash
git clone https://github.com/sanjana-garimella/MediRare
cd MediRare
git checkout -b week1/backend

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install pydantic pytest
```

## Phase 2: Create Starter Schemas

### Goal
Define “what fields must exist” so other scripts can rely on consistent data.

### Steps
Starter files are provided:
- `schemas/case_report.py`
- `schemas/extracted_figure.py`
- `schemas/merged_record.py`
- `schemas/validate_jsonl.py`

Run tests:
```bash
pytest -q
```

## Phase 3: Validate Example Files (Sanity Check)

### Goal
Be sure the validator works end-to-end.

### Steps
If NLP/CV files exist, validate them like:
```bash
python schemas/validate_jsonl.py data/nlp/processed/sle_case_reports.jsonl CaseReport
python schemas/validate_jsonl.py data/cv/metadata/extracted_figures.jsonl ExtractedFigure
```

## Phase 4: Commit Only On Your Branch

```bash
git status
git add schemas/ tests/
git commit -m \"week1(backend): add schemas + JSONL validator + tests\"
git push -u origin week1/backend
```

## Submission Checklist
- You are on `week1/backend`
- `pytest` passes
- `schemas/validate_jsonl.py` can validate a JSONL file (exits 0 on valid, non-zero on invalid)
- You pushed your branch

