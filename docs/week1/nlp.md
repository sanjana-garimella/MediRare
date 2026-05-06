# Week 1 Guide: NLP (PubMed Case Reports -> JSONL)

Student level: early undergrad. You do NOT need deep NLP to finish Week 1.

Time budget: 5-7 hours.

## Phase 1: Setup (Git + Python)

### Goal
Get the repo, create the correct branch, and set up Python so installs work.

### Steps
- Clone and create your Week 1 branch:
```bash
git clone https://github.com/sanjana-garimella/MediRare
cd MediRare
git checkout -b week1/nlp
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

### Common mistakes
- Forgetting to activate `.venv` before running `pip install`.
- Working on `main` by accident. Run `git branch --show-current` to confirm you are on `week1/nlp`.

## Phase 2: Create the Output Folders

### Goal
Make a place to store raw downloads and a clean dataset file the rest of the team can open.

### Steps
```bash
mkdir -p data/nlp/raw data/nlp/processed
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
git add nlp/ data/nlp/
git commit -m \"week1(nlp): add PubMed fetcher + SLE JSONL dataset\"
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

