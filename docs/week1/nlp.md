# Week 1 Guide: NLP (PubMed Case Reports -> JSONL)

Time budget: 5-7 hours.

## Minimum success target

You are done for Week 1 NLP if:
- You are on `week1/nlp` (not `main`).
- `data/nlp/raw/` contains a downloaded XML file.
- `data/nlp/processed/sle_case_reports.jsonl` exists with valid JSONL lines.
- You committed and pushed branch changes (without generated data files).

## What you will learn

- Why raw data and processed data need to be saved separately.
- How structured datasets help NLP tasks and analysis.
- What makes a case report dataset useful for future modeling.

## What you will do this week

- Create a branch and a Python environment.
- Fetch PubMed case reports.
- Save raw XML and create a JSONL dataset.
- Validate the output.

## Phase 1: Setup (Git + Python)

### Goal
Get the repo, create the correct branch, and set up Python so installs work.

### Steps
- Clone the repo and switch to the Week 1 NLP branch:
```bash
git clone https://github.com/sanjana-garimella/MediRare
cd MediRare
git fetch --all
git switch week1/nlp
```

- Create + activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate   # mac/linux
# .venv\\Scripts\\activate  # windows
python -m pip install --upgrade pip
```

- Install dependencies (Week 1 only):
```bash
pip install requests lxml pandas
```

If `python` fails, try `python3` for all commands.

### Common mistakes
- Forgetting to activate `.venv` before running `pip install`.
- Working on `main` by accident. Run `git branch --show-current` to confirm you are on `week1/nlp`.

## Phase 2: Create the Output Folders

### Goal
Make a place to store raw downloads and a clean dataset file the rest of the team can open.

### Steps
```bash
mkdir -p data/nlp/raw data/nlp/processed
ls -la data/nlp
```

### What you should see
```bash
ls -la data/nlp
```
You should see `raw/` and `processed/`.

## Phase 3: Fetch PubMed Records (Real Data)

### Goal
Download 20-30 PubMed case report records for SLE and save:
1. raw responses (for reproducibility)
2. a processed JSONL file (for pipeline use)

### Steps
- Open and read the starter script:
`nlp/fetch_pubmed_case_reports.py`

- Run it:
```bash
python nlp/fetch_pubmed_case_reports.py --disease SLE --retmax 30
```

### What you should see
- A raw file like `data/nlp/raw/SLE_*.xml`
- A processed file: `data/nlp/processed/sle_case_reports.jsonl`

### Common mistakes
- Creating one big JSON list. JSONL must be **one JSON object per line**.
- Leaving `title` or `abstract` empty for most records. (A few missing abstracts is OK.)

## Phase 4: Quick Self-Checks

### Goal
Make sure your output is usable by other people.

### Steps
- Check number of lines:
```bash
wc -l data/nlp/processed/sle_case_reports.jsonl
```

- Peek at the first 2 lines:
```bash
head -n 2 data/nlp/processed/sle_case_reports.jsonl
```

### Common mistakes
- Duplicate PubMed IDs due to query issues.
- Output saved to the wrong folder.

## Phase 5: Commit Only On Your Branch

### Goal
Push your work so the team can review it.

### Steps
```bash
git status
# Do NOT commit downloaded data files (raw XML / processed outputs). Only commit code + docs.
git add nlp/ docs/week1/
git commit -m "week1(nlp): add/adjust PubMed fetcher and notes"
git push -u origin week1/nlp
```

### Common mistakes
- Committing on `main`.
- Forgetting `git push` (nobody can see your work).

## Submission Checklist
- You are on branch `week1/nlp`
- `data/nlp/processed/sle_case_reports.jsonl` exists and has ~20-30 lines
- Each line is valid JSON and has `pubmed_id`, `disease`, `title`, `abstract`
- Raw XML was saved under `data/nlp/raw/`
- You committed and pushed your branch

Note: The data files are generated locally and are not committed to GitHub.

## Troubleshooting quick fixes

- Empty or tiny output: increase `--retmax` and retry.
- JSONL format issue: each line must be one JSON object (no outer list).
- Branch issue: run `git branch --show-current` and confirm `week1/nlp`.
