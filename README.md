# MediRare

Multimodal AI system for detecting misdiagnosis patterns in rare autoimmune diseases using NLP, computer vision, and LLM-based reasoning.
---

## What This Is

Patients with diseases like Lupus, Sjögren's Syndrome, and MCTD wait an average of 6+ years for a correct diagnosis. The signals that could have caught it earlier already exist in the literature, inside figures, case reports, and clinical text but nothing connects them systematically.

MediRare builds that connection. It extracts figures from PubMed papers using computer vision, mines case reports for misdiagnosis patterns using NLP, and uses an LLM agent to synthesize findings into structured research reports.

---

## Components

**1. Literature Figure Miner (CV)**
Extracts and classifies embedded figures (rash images, histology slides, lab charts) from open-access PubMed PDFs using a fine-tuned ViT/ResNet model. Outputs a tagged figure database.

**2. Misdiagnosis Pattern Analyzer (NLP)**
Processes PubMed case reports to extract the sequence of wrong diagnoses a patient received before the correct one. Builds a knowledge graph of disease confusion patterns using BioBERT/PubMedBERT.

**3. MCP Reasoning Agent (LLM + RAG)**
An LLM agent that queries the misdiagnosis graph, retrieves similar cases from a vector database, cross-references Orphanet/OMIM, and produces a per-disease research report covering misdiagnosis pathways and research gaps.

---

## Architecture

```
PubMed / Orphanet / OMIM / HPO
              │
      ┌───────┴───────┐
      │               │
 CV Pipeline      NLP Pipeline
 (figures)       (case reports)
      │               │
      └───────┬───────┘
              │
     MCP Reasoning Agent
     (vLLM + RAG + Tools)
              │
    ┌─────────┴──────────┐
    │                    │
Misdiagnosis         Research
  Report             Gap Map
```

---

## Data Sources

| Source | Use |
|---|---|
| [PubMed API](https://pubmed.ncbi.nlm.nih.gov/) | Case reports and open-access paper figures |
| [Orphanet](https://www.orphadata.com/) | 6,500+ rare diseases with symptoms and prevalence |
| [OMIM API](https://www.omim.org/) | Genetic annotations and phenotype descriptions |
| [HPO](https://hpo.jax.org/) | Standardized symptom vocabulary |

---

## Tech Stack

| Layer | Tools |
|---|---|
| Computer Vision | PyTorch, HuggingFace, ViT / ResNet |
| NLP | BioBERT, PubMedBERT, spaCy |
| LLM Agent | vLLM, LangChain, MCP |
| Vector DB | FAISS / ChromaDB |
| Knowledge Graph | NetworkX |
| Data Pipeline | Python, PubMed API, Orphanet XML parser |
| Demo | Streamlit |

---

## Target Diseases

| Disease | Note |
|---|---|
| Systemic Lupus Erythematosus (SLE) | Avg. 6-year diagnosis delay |
| Sjögren's Syndrome | Often misdiagnosed as fibromyalgia or depression |
| Mixed Connective Tissue Disease (MCTD) | Overlaps with 4+ other autoimmune diseases |
| Inflammatory Myositis | Visually diagnosable, limited literature |
| Antiphospholipid Syndrome | Frequently missed until a clotting event |

---

## Project Status

🚧 **Active Development** — currently recruiting team members via [AISC San Diego](https://aiscsandiego.netlify.app/)

