# Week 1 Guide: Integration (Mock Merge + Tiny Streamlit Demo)

Student level: early undergrad. Week 1 is mostly Python + file formats.

Time budget: 5-7 hours.

## Phase 1: Setup (Git + Python)

```bash
git clone https://github.com/sanjana-garimella/MediRare
cd MediRare
git checkout -b week1/integration

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install pandas streamlit
```

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

## Phase 5: Commit Only On Your Branch

```bash
git status
git add integration/ demo/
git commit -m \"week1(integration): add mock merge + demo\"
git push -u origin week1/integration
```

## Submission Checklist
- You are on `week1/integration`
- `integration/merged_records.jsonl` exists after running the merge script
- Streamlit app runs and shows a table
- You pushed your branch

