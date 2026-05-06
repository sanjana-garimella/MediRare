# Week 1 Guide: Computer Vision (PDF -> Extract Figures + Metadata)

Time budget: 5-7 hours.

## Minimum success target

You are done for Week 1 CV if:
- You are on `week1/cv` (not `main`).
- You extracted figures from at least one open-access PDF.
- `data/cv/metadata/extracted_figures.jsonl` is created and readable.
- You committed and pushed branch changes (without large generated data).

## What you will learn

- How data extraction is the first step in a computer vision research pipeline.
- Why open-access PDFs and metadata matter for reproducibility.
- What makes a good dataset for figure extraction and later model development.

## What you will do this week

- Create a branch for CV work.
- Install minimal Python tools.
- Download open-access PDFs.
- Extract figures and write metadata.

## Phase 1: Setup (Git + Python)

### Goal
Get the repo, create the correct branch, and install dependencies.

### Steps
```bash
git clone https://github.com/sanjana-garimella/MediRare
cd MediRare
git fetch --all
git switch week1/cv

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install pymupdf pillow
```

If `python` fails, try `python3` for all commands.

## Phase 2: Create Data Folders

```bash
mkdir -p data/cv/pdfs data/cv/figures data/cv/metadata
```

## Phase 3: Collect 5-10 Open-Access PDFs (Real Data)

### Goal
Download PDFs from PubMed Central (PMC) so extraction works reliably.

### Steps
- Go to https://pmc.ncbi.nlm.nih.gov/
- Search for SLE / Sjogrens / MCTD papers with free full text.
- Download PDFs and place them in `data/cv/pdfs/`.

Tip: Name files like `PMID_<pubmed_id>.pdf` if you can (helps later).

## Phase 4: Extract Images + Write Metadata JSONL

### Goal
Run the starter script to extract images and produce a metadata file the team can open.

### Steps
- Open the starter script: `cv/extract_figures.py`
- Run it:
```bash
python cv/extract_figures.py --pdf_dir data/cv/pdfs --out_dir data/cv/figures --meta_out data/cv/metadata/extracted_figures.jsonl
```

### What you should see
- Many PNGs in `data/cv/figures/`
- A JSONL file in `data/cv/metadata/`

### Common mistakes
- Extracting “too many” tiny images. That is normal in Week 1. We will filter later.
- Metadata paths that do not match the saved PNG files.

## Phase 5: Commit Only On Your Branch

```bash
git status
# Do NOT commit PDFs or extracted PNGs (too large). Only commit code + docs.
git add cv/ docs/week1/
git commit -m "week1(cv): add/adjust PDF image extraction script and notes"
git push -u origin week1/cv
```

## Submission Checklist
- You are on branch `week1/cv`
- `data/cv/figures/` contains extracted PNGs
- `data/cv/metadata/extracted_figures.jsonl` exists and references real file paths
- You committed and pushed your branch

Note: PDFs and extracted images are generated locally and are not committed to GitHub.

## Troubleshooting quick fixes

- No extracted images: verify PDF files are in `data/cv/pdfs/`.
- Metadata file empty: test with a different open-access PMC PDF.
- Branch issue: run `git branch --show-current` and confirm `week1/cv`.
