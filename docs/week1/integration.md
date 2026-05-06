# Week 1 Guide: Integration (Mock Merge + Tiny Streamlit Demo)

Time budget: 5-7 hours.

## Minimum success target

You are done for Week 1 integration if:
- You are on `week1/integration` (not `main`).
- `integration/merged_records.jsonl` is generated from `integration/merge.py`.
- Streamlit launches and displays merged rows.
- You committed and pushed branch changes.

## What you will learn

- How simple file formats can be combined into a unified dataset.
- Why mock data is useful for building and testing integration logic.
- What a basic demo UI can teach about data usability.

## What you will do this week

- Create a branch and install minimal Python tools.
- Use mock files to build the merge pipeline.
- Generate a merged JSONL output.
- Run a simple Streamlit demo.

## Phase 1: Setup (Git + Python)

```bash
git clone https://github.com/sanjana-garimella/MediRare
cd MediRare
git fetch --all
git switch week1/integration

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install pandas streamlit
```

If `python` fails, try `python3` for all commands.

## Phase 2: Generate Mock Inputs

### Goal
Create small fake inputs so you can build the pipeline without waiting on anyone.

### Steps
Use the provided files:
- `integration/mock_case_reports.jsonl`
- `integration/mock_extracted_figures.jsonl`

These are intentionally fake (not real PubMed IDs).

## Phase 3: Merge -> `merged_records.jsonl`

### Goal
Join on `pubmed_id` and produce a merged JSONL file.

### Steps
Run:
```bash
python integration/merge.py
```

### What you should see
- `integration/merged_records.jsonl` exists
- Some rows have `case_report = null`
- Some rows have `figures = []`

## Phase 4: Streamlit Demo (Table Only)

### Goal
Show the merged output in a simple UI.

### Steps
```bash
streamlit run demo/app.py
```

Streamlit should open a browser window or give you a local URL to visit.

## Phase 5: Commit Only On Your Branch

```bash
git status
git add integration/ demo/ docs/week1/
git commit -m "week1(integration): mock merge + demo + notes"
git push -u origin week1/integration
```

## Submission Checklist
- You are on `week1/integration`
- `integration/merged_records.jsonl` exists after running the merge script
- Streamlit app runs and shows a table
- You pushed your branch

Note: `integration/merged_records.jsonl` is generated locally and is not committed to GitHub.

## Troubleshooting quick fixes

- `merge.py` fails: confirm both mock input JSONL files exist.
- Streamlit does not open automatically: use the printed local URL in browser.
- Branch issue: run `git branch --show-current` and confirm `week1/integration`.
