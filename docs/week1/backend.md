# Week 1 Guide: Backend (Schemas + Simple Validator)

Time budget: 5-7 hours.

## Minimum success target

You are done for Week 1 backend if:
- You are on `week1/backend` (not `main`).
- `pytest -q` runs successfully.
- You can run `schemas/validate_jsonl.py` on at least one JSONL file.
- You committed and pushed branch changes.

## What you will learn

- Why data schemas matter for reliable pipelines.
- How JSONL makes data easier to validate and share.
- Why tests and validators are important for reproducible research.

## What you will do this week

- Create a branch and a Python environment.
- Use starter schema files.
- Validate JSONL data.
- Run tests and commit your branch.

## Phase 1: Setup (Git + Python)

```bash
git clone https://github.com/sanjana-garimella/MediRare
cd MediRare
git fetch --all
git switch week1/backend

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install pydantic pytest
```

If `python` fails, try `python3` for all commands.

## Phase 2: Create Starter Schemas

### Goal
Define “what fields must exist” so other scripts can rely on consistent data.

### Steps
Starter files are provided:
- `schemas/case_report.py`
- `schemas/extracted_figure.py`
- `schemas/merged_record.py`
- `schemas/validate_jsonl.py`

This repository uses JSONL files, which means one JSON object per line.
Use the validator to catch formatting or schema errors early.

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
git commit -m "week1(backend): schemas + validator + tests"
git push -u origin week1/backend
```

## Submission Checklist
- You are on `week1/backend`
- `pytest` passes
- `schemas/validate_jsonl.py` can validate a JSONL file (exits 0 on valid, non-zero on invalid)
- You pushed your branch

## Troubleshooting quick fixes

- `ModuleNotFoundError`: activate `.venv` first (`source .venv/bin/activate`).
- `pytest` fails from import errors: run tests from repo root (`MediRare/`).
- Branch issue: run `git branch --show-current` and confirm `week1/backend`.
