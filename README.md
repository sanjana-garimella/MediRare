# MediRare

Multimodal AI system for detecting misdiagnosis patterns in rare diseases, combining NLP on case reports, computer vision on clinical figures, and LLM-based reasoning over the extracted knowledge.

---

## Problem

Patients with rare diseases often wait years for a correct diagnosis. The signals that could have caught it earlier already exist in the published literature, inside figures, case reports, and clinical text, but nothing connects them systematically.

MediRare builds that connection across 12 rare diseases, chosen by real PubMed misdiagnosis-focused literature volume: Sarcoidosis, Systemic Lupus Erythematosus (SLE), IgG4-related disease, Guillain-Barre syndrome, Granulomatosis with polyangiitis, Myasthenia gravis, Behcet's disease, Castleman disease, Neuromyelitis optica, Antiphospholipid Syndrome, Sjogren's Syndrome, and Mixed Connective Tissue Disease (MCTD).

---

## Reproducing the analysis

The repository is **self-contained**: all data behind the analysis is committed
(not referenced externally).

**To work with the exact data we ran on — just clone.** The committed files under
`data/nlp/processed/`, `data/cv/figure_metadata.jsonl`, and
`data/biomedical/` *are* the exact inputs; no fetch needed:

```bash
git clone <repo> && cd MediRare
pip install -r requirements.txt
python3 nlp/eval_extractor.py \
    --pred data/nlp/processed/sle_case_reports.jsonl \
    --truth data/biomedical/sle_misdiagnosis_groundtruth.csv   # reproduces the confusion matrix
```

**To regenerate from PubMed** (optional), run `bash scripts/reproduce.sh`.
⚠️ This re-fetches live from PubMed and will **not** return byte-identical
records — new case reports get published and relevance ranking shifts over time,
so PMIDs drift. The ground-truth CSV is keyed to the committed PMIDs; re-label it
after any re-fetch. For exact reproduction, use the committed files, not a fresh fetch.

`scripts/reproduce.sh` runs the full pipeline (NLP **and** CV) end-to-end:

| Step | Command | Output |
|---|---|---|
| 1. Fetch case reports | `python3 nlp/fetch_pubmed_case_reports.py --disease SLE --retmax 100 --focus misdiagnosis` | `data/nlp/processed/*.jsonl` |
| 2. Validate | `python3 -m schemas.validate_jsonl <file> CaseReport` | pass/fail |
| 3. Extract misdiagnoses | `python3 nlp/extract_misdiagnosis.py data/nlp/processed/sle_case_reports.jsonl` | populates `misdiagnosis_sequence` |
| 4. Evaluate | `python3 nlp/eval_extractor.py --pred <file> --truth data/biomedical/sle_misdiagnosis_groundtruth.csv` | confusion matrix |
| 5. Fetch CV figures | `python3 cv/fetch_pmc_figures.py --jsonl <files> --out data/cv/figure_metadata.jsonl` | `data/cv/figure_metadata.jsonl` |
| 6. Health check | `python3 scripts/week1_check.py --role nlp` | summary |

**Query focus matters more than size.** The generic `--focus general` query
("SLE case report") buries misdiagnosis cases — only ~8% of records contain one.
The `--focus misdiagnosis` query (default) targets diagnostic-error / mimic case
reports and raises that to ~63%. PubMed holds ~560 misdiagnosis-relevant SLE
case reports; scale with `--retmax 200` (NCBI per-run cap; batch for more).

---

## Current Data (as of June 2026)

### NLP — Case Reports

| Disease | Query focus | Records | Misdiagnosis cases | Extracted |
|---|---|---|---|---|
| Systemic Lupus Erythematosus (SLE) | misdiagnosis | 100 | 63 (labeled) | 14 |
| Sjögren's Syndrome | general | 50 | not labeled | not run |
| Mixed Connective Tissue Disease (MCTD) | general | 50 | not labeled | not run |

**SLE extractor evaluation** (keyword/regex first pass vs. 100 hand labels,
`nlp/eval_extractor.py`):

| Metric | Value | Reading |
|---|---|---|
| Precision | 0.88 | of 16 flagged, 14 correct |
| Recall | 0.22 | catches 14 of 63 real cases |
| F1 | 0.35 | |
| Accuracy | 0.49 | vs 0.63 majority baseline |

- Switching to the misdiagnosis query took the corpus from **4 → 63 real cases**
  and extractions from **1 → 14**.
- Recall is still low — keyword/regex misses 49 of 63. Full-text PubMedBERT next.
- 2 false positives (`Evans syndrome`, `retinal vasculitis`) are SLE
  *manifestations* named via "initially diagnosed with…", not competing diseases —
  a definitional gray zone flagged for clinician review.

> Ground-truth labels in `data/biomedical/sle_misdiagnosis_groundtruth.csv` are
> AI-proposed (`review_status` column) and need clinician sign-off. The `SYN_*`
> rows in the gold set / analysis doc remain **synthetic placeholders**.

### CV — Clinical Figures

Regenerated reproducibly from all 200 records via `cv/fetch_pmc_figures.py`
(PubMed → PMC open-access → figure XML). **147 of 200 are open-access**, yielding
**437 figures** with captions and type labels:

| Disease | Open-Access Articles | Figures | Type breakdown |
|---|---|---|---|
| SLE | 75 | 231 | imaging 72, histology 28, rash 25, lab_chart 19, other 87 |
| Sjögren's | 40 | 106 | imaging 31, histology 16, lab_chart 11, rash 4, other 44 |
| MCTD | 32 | 100 | imaging 28, lab_chart 8, rash 7, histology 4, other 53 |
| **Total** | **147** | **437** | imaging 131, other 184, histology 48, lab_chart 38, rash 36 |

Figure type is assigned by caption keyword matching (imaging / histology /
lab_chart / rash_image) as a first pass, before any model-based classification.
The script captures figure metadata (caption, label, image filename); downloading
the image binaries requires the PMC OA bulk service (see roadmap).

### Biomedical Annotations

| Asset | Records | Status |
|---|---|---|
| Gold annotated cases | 10 | **Synthetic placeholders** (`SYN_001`–`SYN_010`), not expert-annotated — see note below |
| HPO phenotype mappings | 31 | SLE (10), Sjögren's (10), MCTD (11) |
| Label / annotation guide | — | Complete for all 3 diseases |

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
  (NetworkX — disease confusion patterns)
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

## Roadmap

### Phase 1 — Data & Extraction (Current)
- [x] 200 real PubMed case reports fetched (SLE 100, Sjögren's 50, MCTD 50)
- [x] 437 clinical figures identified from 147 open-access articles
- [x] HPO phenotype mappings for all 3 diseases
- [x] Gold annotation set (10 synthetic placeholder cases — not expert-annotated)
- [ ] Misdiagnosis sequence extraction — regex pass first, then PubMedBERT
- [ ] Fix Sjögren's search query (narrow to primary Sjögren's)
- [ ] Scale to 200 records/disease

### Phase 2 — NLP Pipeline (Weeks 2–4)
- [ ] Regex extractor: populate `misdiagnosis_sequence` from all 150 records
- [ ] PubMedBERT fine-tuning on gold-annotated cases
- [ ] Build misdiagnosis knowledge graph (NetworkX)
- [ ] Replace 10 synthetic gold cases with real expert-annotated cases, then validate — target 9/10 match

### Phase 3 — CV Pipeline (Weeks 3–5)
- [ ] Figure type classifier: ViT zero-shot → fine-tune on labeled figures
- [ ] Expand open-access PDF download (Unpaywall, PMC bulk access)
- [ ] Link figures to misdiagnosis records in merged schema

### Phase 4 — RAG Agent (Weeks 5–7)
- [ ] Load merged records into ChromaDB/LanceDB
- [ ] Hybrid retrieval (dense embedding + BM25, fused with RRF)
- [ ] Claim-level faithfulness verification (abstain when evidence is thin)
- [ ] Per-disease misdiagnosis research report generation

### Phase 5 — Demo (Week 8)
- [ ] Streamlit app: query a disease → see misdiagnosis pathways + supporting figures
- [ ] Export research gap report as PDF

---

## Disease Scope

Active disease list is chosen by real PubMed misdiagnosis-focused literature volume (checked directly against PubMed's own index, not estimated), not by arbitrary selection. Pooled across all 12, that's roughly 2885 misdiagnosis-focused case reports, versus 350 to 550 for any single disease alone, which is what makes fine-tuning a single general model on this data feasible.

| Disease | Misdiagnosis-focused records in PubMed | Status |
|---|---|---|
| Sarcoidosis | 783 | Active |
| Systemic Lupus Erythematosus (SLE) | 564 | Active |
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

## Tech Stack

| Layer | Tools |
|---|---|
| NLP | PubMedBERT, spaCy, NCBI E-utilities |
| Computer Vision | PyMuPDF (extraction), ViT (classification) |
| Vector DB / RAG | LanceDB (on-disk), ChromaDB, BM25 hybrid |
| Knowledge Graph | NetworkX |
| LLM Agent | vLLM + LangChain + MCP |
| Demo | Streamlit |

---

## Data Sources

| Source | Use |
|---|---|
| [PubMed API](https://pubmed.ncbi.nlm.nih.gov/) | Case reports + open-access figures |
| [PubMed Central](https://pmc.ncbi.nlm.nih.gov/) | Full-text XML + figure extraction |
| [Orphanet](https://www.orphadata.com/) | 6,500+ rare diseases, symptoms, prevalence |
| [HPO](https://hpo.jax.org/) | Standardized phenotype vocabulary |
| [OMIM](https://www.omim.org/) | Genetic annotations |

---

## Project Status

**Active development** — currently in Phase 1 (data collection and validation).
Team via [AISC San Diego](https://aiscsandiego.netlify.app/).

Data files:
- `data/nlp/processed/` — real PubMed case reports (JSONL)
- `data/cv/figure_metadata.jsonl` — CV figure metadata from open-access articles
- `data/biomedical/` — gold annotations, HPO mappings, label guide
