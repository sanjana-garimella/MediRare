# Week 1 Guide: Biomedical (Label Guide + Annotations + HPO Mapping)

Student level: early undergrad. No coding is required for Week 1.

Time budget: 5-7 hours.

## Phase 1: Setup (Git)

### Goal
Get the repo and work only on the correct branch.

### Steps
```bash
git clone https://github.com/sanjana-garimella/MediRare
cd MediRare
git checkout -b week1/biomedical
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

