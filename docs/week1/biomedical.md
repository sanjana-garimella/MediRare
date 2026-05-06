# Week 1 Guide: Biomedical (Label Guide + Annotations + HPO Mapping)

Time budget: 5-7 hours.

## Minimum success target

You are done for Week 1 biomedical if:
- You are on `week1/biomedical` (not `main`).
- `annotations.csv` has 10 real PubMed-based rows.
- `hpo_mapping.csv` has 15-30 rows with valid `HP:...` IDs.
- You committed and pushed branch changes.

## What you will learn

- How structured annotation supports biomedical research.
- Why standardized terms like HPO IDs improve data quality.
- How clear labels help downstream ML and analysis.

## What you will do this week

- Create a branch for biomedical annotation.
- Fill in the annotation template with 10 case reports.
- Map symptoms to HPO codes.
- Keep the shared files clean and consistent.

## Phase 1: Setup (Git)

### Goal
Get the repo and work only on the correct branch.

### Steps
```bash
git clone https://github.com/sanjana-garimella/MediRare
cd MediRare
git fetch --all
git switch week1/biomedical
```

### Common mistakes
- Committing on `main` instead of `week1/biomedical`.

## Phase 2: Create Templates (So Everyone Uses The Same Format)

### Goal
Create starter files in `data/biomedical/` that are easy for the team to read.

### Steps
```bash
mkdir -p data/biomedical
```

Use these files (already provided in the repo) as your templates:
- `data/biomedical/label_guide.md`
- `data/biomedical/annotations.csv`
- `data/biomedical/hpo_mapping.csv`

## Phase 3: Find 10 Case Reports (Real Data)

### Goal
Pick 10 PubMed case reports relevant to SLE / Sjogrens / MCTD.

### Steps
- Go to PubMed: `https://pubmed.ncbi.nlm.nih.gov/`
- Search:
  - `"systemic lupus erythematosus" case report`
  - `"Sjogren syndrome" case report`
  - `"mixed connective tissue disease" case report`
- Pick papers with readable abstracts.
- Copy each `pubmed_id` (the number in the URL).

### Common mistakes
- Using papers without abstracts (hard to annotate quickly).

## Phase 4: Fill In `annotations.csv` (10 Rows)

### Goal
For each case report, capture the misdiagnosis trail and key symptoms.

### Steps
- Open `data/biomedical/annotations.csv` and fill 10 rows.
- Keep `misdiagnoses_before_correct` short and clear (comma-separated).

### Common mistakes
- Confusing “differential diagnosis” with “misdiagnosis.” Only record diagnoses that clearly happened before the correct one.

## Phase 5: Fill In `hpo_mapping.csv` (15-30 Rows)

### Goal
Map symptom phrases to standardized terms (HPO IDs + labels).

### Steps
- Browse HPO terms: https://bioportal.bioontology.org/ontologies/HP
- For symptom phrases from your cases (e.g., fatigue, malar rash, dry eyes), find:
  - HPO ID (like `HP:0000978`)
  - official label
- Add 15-30 mappings.

### Common mistakes
- Missing the HPO ID (we need IDs, not just labels).

## Phase 6: Commit Only On Your Branch

```bash
git status
git add data/biomedical/
git commit -m \"week1(biomedical): add label guide + annotations + HPO mapping\"
git push -u origin week1/biomedical
```

## Submission Checklist
- You are on branch `week1/biomedical`
- `data/biomedical/annotations.csv` has 10 rows with real `pubmed_id`s
- `data/biomedical/hpo_mapping.csv` has 15-30 rows with valid `HP:...` IDs
- You committed and pushed your branch

## Troubleshooting quick fixes

- Cannot find HPO term: use a close clinical phrase first, then refine.
- Unsure if it is misdiagnosis vs differential: only include diagnoses that clearly happened before final diagnosis.
- Branch issue: run `git branch --show-current` and confirm `week1/biomedical`.
