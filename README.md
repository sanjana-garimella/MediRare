# MediRare

Multimodal AI system for detecting misdiagnosis patterns in rare diseases, combining NLP on case reports, computer vision on clinical figures, and LLM-based reasoning over the extracted knowledge.

---

## Problem

Patients with rare diseases often wait years for a correct diagnosis. The signals that could have caught it earlier already exist in the published literature, inside figures, case reports, and clinical text, but nothing connects them systematically.

MediRare addresses this across 12 rare diseases, selected by real PubMed misdiagnosis-focused literature volume: Sarcoidosis, Systemic Lupus Erythematosus (SLE), IgG4-related disease, Guillain-Barre syndrome, Granulomatosis with polyangiitis, Myasthenia gravis, Behcet's disease, Castleman disease, Neuromyelitis optica, Antiphospholipid Syndrome, Sjogren's Syndrome, and Mixed Connective Tissue Disease (MCTD). The goal is a fine-tuned model released on HuggingFace plus a paper, trained by pooling data across all 12 rather than treating each disease as its own pipeline.

---

## Reproducing the analysis

The repository is self-contained: all data behind the analysis is committed, not referenced externally.

```bash
git clone <repo> && cd MediRare
pip install -r nlp/requirements.txt -r cv/requirements.txt
python3 nlp/eval_extractor.py \
    --pred data/nlp/processed/sle_case_reports.jsonl \
    --truth data/biomedical/sle_misdiagnosis_groundtruth.csv
```

The committed files under `data/nlp/processed/`, `data/cv/figure_metadata.jsonl`, and `data/biomedical/` are the exact inputs used, so no fetch is required to reproduce results.

To regenerate from PubMed instead, run `bash scripts/reproduce.sh`. This re-fetches live data and will not return identical records, since new case reports are published and relevance ranking shifts over time. The ground-truth CSV is keyed to the committed PMIDs, so re-label it after any re-fetch.

`scripts/reproduce.sh` runs the full pipeline end-to-end:

| Step | Command | Output |
|---|---|---|
| 1. Fetch case reports | `python3 nlp/fetch_pubmed_case_reports.py --disease SLE --retmax 100 --focus misdiagnosis` | `data/nlp/processed/*.jsonl` |
| 2. Validate | `python3 -m schemas.validate_jsonl <file> CaseReport` | pass/fail |
| 3. Extract misdiagnoses | `python3 nlp/extract_misdiagnosis.py data/nlp/processed/sle_case_reports.jsonl` | populates `misdiagnosis_sequence` |
| 4. Evaluate | `python3 nlp/eval_extractor.py --pred <file> --truth data/biomedical/sle_misdiagnosis_groundtruth.csv` | confusion matrix |
| 5. Fetch CV figures | `python3 cv/fetch_pmc_figures.py --jsonl <files> --out data/cv/figure_metadata.jsonl` | `data/cv/figure_metadata.jsonl` |
| 6. Health check | `python3 scripts/week1_check.py --role nlp` | summary |

Query focus matters more than corpus size. The generic `--focus general` query buries misdiagnosis cases (~8% of records contain one). The `--focus misdiagnosis` query (default) targets diagnostic-error and mimic case reports, raising that to ~63%. PubMed holds 564 misdiagnosis-relevant SLE case reports; scale with `--retmax 200` per run (NCBI cap; batch for more).

---

## Current data

The active disease scope is 12 diseases, but fetching has only been done for 3 (SLE, Sjogren's, MCTD). The remaining 9 have `DISEASE_TERMS` entries but no fetched data yet.

### NLP: case reports

| Disease | Query focus | Records | Misdiagnosis cases | Extracted |
|---|---|---|---|---|
| SLE | misdiagnosis | 100 | 63 (labeled) | 30 |
| Sjogren's | general | 50 | not labeled | not run |
| MCTD | general | 50 | not labeled | not run |

SLE extractor evaluation (keyword/regex first pass vs. 100 hand labels, `nlp/eval_extractor.py`):

| Metric | Value |
|---|---|
| Precision | 0.83 |
| Recall | 0.40 |
| F1 | 0.54 |
| Accuracy | 0.57 (vs 0.63 majority baseline) |

Ground-truth labels in `data/biomedical/sle_misdiagnosis_groundtruth.csv` are AI-proposed (`review_status` column) and need clinician sign-off. The `SYN_*` rows in the gold set remain synthetic placeholders.

### CV: clinical figures

Generated from all 200 fetched records via `cv/fetch_pmc_figures.py` (PubMed to PMC open-access to figure XML). 147 of 200 are open-access, yielding 437 figures with captions and type labels:

| Disease | Open-access articles | Figures |
|---|---|---|
| SLE | 75 | 231 |
| Sjogren's | 40 | 106 |
| MCTD | 32 | 100 |
| Total | 147 | 437 |

Figure type is assigned by caption keyword matching (imaging / histology / lab_chart / rash_image) as a first pass, before any model-based classification.

### Biomedical annotations

| Asset | Records | Status |
|---|---|---|
| Gold annotated cases | 10 | Synthetic placeholders (`SYN_001` to `SYN_010`), not expert-annotated |
| HPO phenotype mappings | 31 | SLE (10), Sjogren's (10), MCTD (11) |
| Label / annotation guide | N/A | Complete for all 3 fetched diseases |

---

## Architecture

```
PubMed API (case reports + open-access PDFs)
         │
   ┌─────┴──────┐
   │            │
NLP Pipeline  CV Pipeline
(abstracts)   (figures)
   │            │
   └─────┬──────┘
         │
  Misdiagnosis Knowledge Graph
  (NetworkX, disease confusion patterns)
         │
  Vector Store (ChromaDB/LanceDB)
  + Hybrid Search (dense + BM25)
         │
  MCP Reasoning Agent (LLM + RAG)
         │
   ┌─────┴──────┐
   │            │
Misdiagnosis  Research
  Report      Gap Map
```

---

## Disease scope

The active disease list is chosen by real PubMed misdiagnosis-focused literature volume, not by arbitrary selection. Pooled across all 12, that is roughly 2,885 misdiagnosis-focused case reports, versus 350 to 550 for any single disease alone, which is what makes fine-tuning a single general model on this data feasible.

| Disease | Misdiagnosis-focused records in PubMed | Status |
|---|---|---|
| Sarcoidosis | 783 | Active |
| SLE | 564 | Active |
| IgG4-related disease | 288 | Active |
| Guillain-Barre syndrome | 280 | Active |
| Granulomatosis with polyangiitis | 194 | Active |
| Myasthenia gravis | 186 | Active |
| Behcet's disease | 150 | Active |
| Castleman disease | 143 | Active |
| Neuromyelitis optica | 138 | Active |
| Antiphospholipid Syndrome | 100 | Active |
| Sjogren's Syndrome | 38 | Active (thin, kept for continuity with the project's original scope) |
| Mixed Connective Tissue Disease | 21 | Active (thin, kept for continuity with the project's original scope) |
| Inflammatory Myositis | 17 | Out of scope, too thin to include |

---

## Tech stack

| Layer | Tools |
|---|---|
| NLP | PubMedBERT, spaCy, paperscraper (PubMed fetch) |
| Computer Vision | PyMuPDF (extraction), ViT (classification) |
| Vector DB / RAG | LanceDB (on-disk), ChromaDB, BM25 hybrid |
| Knowledge Graph | NetworkX |
| LLM Agent | vLLM + LangChain + MCP |
| Demo | Streamlit |

---

## Data sources

| Source | Use |
|---|---|
| [PubMed API](https://pubmed.ncbi.nlm.nih.gov/) | Case reports + open-access figures |
| [PubMed Central](https://pmc.ncbi.nlm.nih.gov/) | Full-text XML + figure extraction |
| [Orphanet](https://www.orphadata.com/) | 6,500+ rare diseases, symptoms, prevalence |
| [HPO](https://hpo.jax.org/) | Standardized phenotype vocabulary |
| [OMIM](https://www.omim.org/) | Genetic annotations |
