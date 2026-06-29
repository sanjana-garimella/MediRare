# MediRare

Multimodal AI system for detecting misdiagnosis patterns in rare autoimmune diseases — combining NLP on case reports, computer vision on clinical figures, and LLM-based reasoning over the extracted knowledge.

---

## Problem

Patients with Lupus, Sjögren's Syndrome, and MCTD wait an average of **6+ years** for a correct diagnosis. The signals that could have caught it earlier already exist in the published literature — inside figures, case reports, and clinical text — but nothing connects them systematically.

MediRare builds that connection.

---

## Current Data (as of June 2026)

### NLP — Case Reports

| Disease | PubMed Records | With Abstract | Misdiagnosis Signal |
|---|---|---|---|
| Systemic Lupus Erythematosus (SLE) | 50 | 48 | 5 records |
| Sjögren's Syndrome | 50 | 47 | 0 records* |
| Mixed Connective Tissue Disease (MCTD) | 50 | 48 | 3 records |
| **Total** | **150** | **143** | **8** |

*Sjögren's search query needs tightening — 13/50 records are noise from overlapping conditions.

**Sample misdiagnosis signals found:**
- `[42321940]` Leprosy masquerading as SLE — `misdiagnosed`, `previously diagnosed`
- `[42325589]` Lupus Enteritis with diagnostic delay — `prior diagnosis`, `diagnostic delay`
- `[39415142]` Central retinal artery occlusion as initial MCTD manifestation — `misdiagnosed`
- `[40190945]` Macrophage Activation Syndrome in MCTD — `prior diagnosis`

### CV — Clinical Figures

From the 150 case reports, **8 are open-access via PubMed Central**, yielding **17 extractable figures**:

| Disease | Open-Access Articles | Figures | Types |
|---|---|---|---|
| SLE | 3 | 7 | rash_image (1), imaging (0), other (6) |
| Sjögren's | 2 | 4 | imaging (4) |
| MCTD | 3 | 6 | imaging (2), lab_chart (3), histology (1) |
| **Total** | **8** | **17** | 4 types identified |

Figure type classification (rash image, histology, lab chart, imaging) is being done via caption keyword matching as a first pass, before any model-based classification.

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
