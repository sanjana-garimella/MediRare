# MediRare

Research prototype for extracting candidate diagnostic-confusion mentions from
rare-disease case reports. It combines NLP, clinical-figure metadata, and
citation-constrained retrieval.

> **Research use only.** This is not medical advice or clinical decision
> support. Current annotations are AI-proposed and not clinician-reviewed.
> Case reports are publication-biased anecdotes; extracted counts do not
> estimate prevalence, risk, causality, or diagnostic performance. Citations
> establish source provenance, not clinical correctness.

---

## Problem

Patients with rare diseases often wait years for a correct diagnosis. The signals that could have caught it earlier already exist in the published literature, inside figures, case reports, and clinical text, but nothing connects them systematically.

MediRare addresses this across 12 rare diseases, selected by real PubMed misdiagnosis-focused literature volume: Sarcoidosis, Systemic Lupus Erythematosus (SLE), IgG4-related disease, Guillain-Barre syndrome, Granulomatosis with polyangiitis, Myasthenia gravis, Behcet's disease, Castleman disease, Neuromyelitis optica, Antiphospholipid Syndrome, Sjogren's Syndrome, and Mixed Connective Tissue Disease (MCTD). The goal is a fine-tuned model released on HuggingFace plus a paper, trained by pooling data across all 12 rather than treating each disease as its own pipeline.

---

## Reproducing the analysis

Committed processed/biomedical fixtures are self-contained. Derived RAG chunks,
indexes, graph outputs, and merged records are intentionally ignored and rebuilt
locally so stale generated artifacts are not mistaken for source evidence.

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

The active disease scope is 12 diseases, but fetching has only been done for 3 (SLE, Sjogren's, MCTD). The remaining 9 are not yet configured: no `DISEASE_TERMS` / `MISDIAGNOSIS_TERMS` entries, HPO rows, or label guide sections.

### NLP: case reports

| Disease | Query focus | Records | Misdiagnosis cases | Extracted |
|---|---|---|---|---|
| SLE | misdiagnosis | 100 | 63 (AI-proposed/internal labels) | 44 candidate sequence-bearing rows |
| Sjogren's | misdiagnosis | 39 | keyword-derived/AI-proposed | 16 candidate sequence-bearing rows |
| MCTD | misdiagnosis | 21 | keyword-derived/AI-proposed | 9 candidate sequence-bearing rows |

`nlp/eval_extractor.py` reports document-level and entity-level exact/normalized
set metrics. Current truth CSVs are AI-proposed or circular keyword-hit labels,
not clinician-reviewed validation. `--llm-assist` remains opt-in: its unfiltered
measured F1 was worse than regex-only, and filtered performance has not yet been
established.

End-to-end for these 3 diseases: `bash scripts/e2e.sh`, then
`python3 agent/ask.py --query "..."` or `streamlit run demo/app.py`. The agent
defaults to clinician-reviewed evidence only and currently abstains because no
record has completed adjudication. `--allow-unreviewed` exists solely for
internal extraction debugging.


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
| Synthetic example cases | 10 | Placeholders (`SYN_001` to `SYN_010`), not evaluation or expert annotation |
| HPO phenotype mappings | 31 | SLE (10), Sjogren's (10), MCTD (11) |
| Label / annotation guide | N/A | Complete for all 3 fetched diseases |

### Exploratory: autoantibody mentions

Regex count of autoantibody / serology terms (ANA, anti-dsDNA, anti-Sm,
anti-Ro/SSA, anti-La/SSB, anti-U1-RNP, antiphospholipid, ANCA/PR3/MPO, AQP4,
AChR/MuSK, complement) in titles + abstracts. Exploratory signal check only,
not an extraction feature.

| Disease | Records | Any mention | Positive-result sentence | Among misdiagnosis records |
|---|---|---|---|---|
| SLE | 100 | 32 (32%) | 27 (27%) | 15 / 44 (34%) |
| Sjogren's | 39 | 12 (31%) | 11 (28%) | 4 / 16 (25%) |
| MCTD | 21 | 9 (43%) | 8 (38%) | 5 / 9 (56%) |

Top markers match each disease (SLE: ANA, complement, anti-dsDNA; Sjogren's:
anti-Ro/SSA, anti-La/SSB; MCTD: anti-U1-RNP). Spot checks show some cases
where serology resolves the misdiagnosis (e.g. SLE initially treated as
tuberculosis, confirmed by ANA/anti-dsDNA/anti-Ro), but counts include
background definitions and negative panels, so true resolving-test cases are
lower. Abstracts likely undercount versus full text. Enzyme/protein targets
(PR3, MPO, AQP4, AChR) become relevant only once GPA, NMO, and myasthenia
gravis are fetched.

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
  Reviewed Relation Graph
  (candidate edges quarantined until adjudication)
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

| Disease | Misdiagnosis-focused records in PubMed | What it is |
|---|---|---|
| Sarcoidosis | 783 | Multisystem inflammatory disease causing granulomas, most often in the lungs and lymph nodes |
| SLE | 564 | Chronic autoimmune disease that can affect skin, joints, kidneys, and other organs |
| IgG4-related disease | 288 | Immune-mediated fibro-inflammatory condition causing tumor-like swelling in various organs |
| Guillain-Barre syndrome | 280 | Acute autoimmune disorder attacking peripheral nerves, causing rapid-onset muscle weakness |
| Granulomatosis with polyangiitis | 194 | Autoimmune vasculitis affecting small blood vessels, often in the lungs, sinuses, and kidneys |
| Myasthenia gravis | 186 | Autoimmune neuromuscular disorder causing fluctuating muscle weakness |
| Behcet's disease | 150 | Rare vasculitis causing recurrent mouth and genital ulcers and eye inflammation |
| Castleman disease | 143 | Rare lymphoproliferative disorder involving abnormal lymph node overgrowth |
| Neuromyelitis optica | 138 | Autoimmune disorder attacking the optic nerves and spinal cord |
| Antiphospholipid Syndrome | 100 | Autoimmune clotting disorder causing blood clots and pregnancy complications |
| Sjogren's Syndrome | 38 | Autoimmune disease attacking moisture-producing glands, causing dry eyes and mouth |
| Mixed Connective Tissue Disease | 21 | Overlap autoimmune disease with features of lupus, scleroderma, and myositis |

Inflammatory Myositis (autoimmune muscle inflammation causing progressive weakness) was considered but is out of scope: only 17 total records, too thin to include.

---

## Tech stack

| Layer | Tools |
|---|---|
| NLP | PubMedBERT, spaCy, paperscraper (PubMed fetch) |
| Computer Vision | PyMuPDF (extraction), ViT (classification) |
| Vector DB / RAG | LanceDB (on-disk), ChromaDB, BM25 hybrid |
| Knowledge Graph | NetworkX |
| LLM Agent | Ollama: `qwen2.5:14b` (primary answerer) + `llama3.1:8b` (backup answerer; also the `--verify` cross-model consistency check, since it's independent of the primary). `meditron:7b` was tried for `--verify` and found non-functional — it never returned a parseable grade — so it is parked, not used by any code path. |
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
