# MediRare

Multimodal AI system for detecting misdiagnosis patterns in rare autoimmune diseases — combining NLP on case reports, computer vision on clinical figures, and LLM-based reasoning over the extracted knowledge.

---

## Problem

Patients with Lupus, Sjögren's Syndrome, and MCTD wait an average of **6+ years** for a correct diagnosis. The signals that could have caught it earlier already exist in the published literature — inside figures, case reports, and clinical text — but nothing connects them systematically.

MediRare builds that connection.

---

## Reproducing the analysis

The repository is **self-contained**: all data behind the 150-case analysis is
committed (not referenced externally). A fresh clone can regenerate everything:

```bash
git clone <repo> && cd MediRare
pip install -r requirements.txt
bash scripts/reproduce.sh          # fetch → validate → extract → CV → health check
```

`scripts/reproduce.sh` runs the full pipeline (NLP **and** CV) end-to-end:

| Step | Command | Output |
|---|---|---|
| 1. Fetch case reports | `python3 nlp/fetch_pubmed_case_reports.py --disease SLE --retmax 50` | `data/nlp/processed/*.jsonl` |
| 2. Validate | `python3 -m schemas.validate_jsonl <file> CaseReport` | pass/fail |
| 3. Extract misdiagnoses | `python3 nlp/extract_misdiagnosis.py data/nlp/processed/sle_case_reports.jsonl` | populates `misdiagnosis_sequence` |
| 4. Fetch CV figures | `python3 cv/fetch_pmc_figures.py --jsonl <files> --out data/cv/figure_metadata.jsonl` | `data/cv/figure_metadata.jsonl` |
| 5. Health check | `python3 scripts/week1_check.py --role nlp` | summary |

**Scaling the corpus:** PubMed holds ~3,000 SLE case reports (1,471 in the last
5 years). The committed 50/disease is a **development sample** — enough to build
and eyeball the extractor against the 10 gold cases, but *not* the final research
corpus. The misdiagnosis graph will need 200–500+ records per disease. To scale,
re-run step 1 with `--retmax 200` (the NCBI per-run cap; batch for more).

---

## Current Data (as of June 2026)

### NLP — Case Reports

| Disease | PubMed Records | With Abstract | Misdiagnosis Extracted |
|---|---|---|---|
| Systemic Lupus Erythematosus (SLE) | 50 | 48 | 1 (keyword pass) |
| Sjögren's Syndrome | 50 | 47 | not run yet |
| Mixed Connective Tissue Disease (MCTD) | 50 | 48 | not run yet |
| **Total** | **150** | **143** | **1** |

> **50 is a dev sample, not the target corpus** (see *Scaling the corpus* above).

**Extractor results (SLE, keyword/regex first pass — `nlp/extract_misdiagnosis.py`):**
- **1/50** populated with high confidence: `[42160240]` jSLE → `["pyrexia of unknown origin"]`
- **4/50** flagged `KEYWORD_NO_ENTITY` — keyword present but entity needs NLP/LLM
- **43/50** no keyword signal — *the real gap*: misdiagnosis lives in the full case
  narrative (PMC full text), not the abstract. Keyword matching tops out near 2%
  on abstracts; PubMedBERT on full text is the next step.

> The populated `misdiagnosis_sequence` values in `docs/analysis_150_cases.md` and
> the 10 gold `SYN_*` cases are **synthetic placeholders** for schema design — not
> extracted from real text. Real extraction is the active work.

### CV — Clinical Figures

Regenerated reproducibly from all 150 records via `cv/fetch_pmc_figures.py`
(PubMed → PMC open-access → figure XML). **103 of 150 are open-access**, yielding
**296 figures** with captions and type labels:

| Disease | Open-Access Articles | Figures | Type breakdown |
|---|---|---|---|
| SLE | 30 | 87 | imaging 23, histology 11, rash 8, lab_chart 6, other 39 |
| Sjögren's | 40 | 106 | imaging 31, histology 16, lab_chart 11, rash 4, other 44 |
| MCTD | 33 | 103 | imaging 28, lab_chart 8, rash 7, histology 4, other 56 |
| **Total** | **103** | **296** | imaging 82, other 139, histology 31, lab_chart 25, rash 19 |

Figure type is assigned by caption keyword matching (imaging / histology /
lab_chart / rash_image) as a first pass, before any model-based classification.
The script captures figure metadata (caption, label, image filename); downloading
the image binaries requires the PMC OA bulk service (see roadmap).

### Biomedical Annotations

| Asset | Records | Status |
|---|---|---|
| Gold annotated cases | 10 | Hand-crafted with expert misdiagnosis trails |
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
- [x] 150 real PubMed case reports fetched (50 × 3 diseases)
- [x] 17 clinical figures identified from 8 open-access articles
- [x] HPO phenotype mappings for all 3 diseases
- [x] Gold annotation set (10 hand-crafted cases)
- [ ] Misdiagnosis sequence extraction — regex pass first, then PubMedBERT
- [ ] Fix Sjögren's search query (narrow to primary Sjögren's)
- [ ] Scale to 200 records/disease

### Phase 2 — NLP Pipeline (Weeks 2–4)
- [ ] Regex extractor: populate `misdiagnosis_sequence` from all 150 records
- [ ] PubMedBERT fine-tuning on gold-annotated cases
- [ ] Build misdiagnosis knowledge graph (NetworkX)
- [ ] Validate against 10 gold cases — target 9/10 match

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

| Disease | Owner | Status |
|---|---|---|
| Systemic Lupus Erythematosus | Core team | Active — end-to-end pipeline target |
| Sjögren's Syndrome | Core team | Active — end-to-end pipeline target |
| Mixed Connective Tissue Disease | Undergrads | Data fetched, same pipeline applies |
| Inflammatory Myositis | Undergrads | No data yet |
| Antiphospholipid Syndrome | Undergrads | No data yet |

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
