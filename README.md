# MediRare

> Multimodal AI for rare autoimmune disease misdiagnosis detection using NLP, CV, and LLMs.

---

## Overview

Patients with rare autoimmune diseases like Lupus, Sjögren's Syndrome, and Mixed Connective Tissue Disease (MCTD) wait an average of **6+ years** for a correct diagnosis often misdiagnosed with anxiety, depression, fibromyalgia, or more common conditions. During this diagnostic odyssey, critical signals exist scattered across thousands of medical papers, case reports, and clinical figures but no system connects them.

**MediRare** is a multimodal AI research system that bridges this gap. It mines **medical literature figures** using computer vision, extracts **misdiagnosis patterns** from PubMed case reports using NLP, and connects signals across diseases using an **LLM reasoning agent** generating research-ready reports that surface what clinicians and researchers are currently missing.

The goal is to accelerate the path to correct diagnosis for the 300+ million people worldwide living with rare diseases.

---

## The Problem

Rare autoimmune diseases are notoriously hard to diagnose because:
- Their symptoms overlap significantly with common conditions
- Each disease has only a small number of published case reports
- Critical diagnostic signals are buried inside figures and tables in papers, not in searchable text
- Misdiagnosis trails are never systematically mapped across the literature

MediRare attacks all four problems simultaneously using a multimodal AI pipeline.

---

## Key Components

### 1. Literature Figure Miner (Computer Vision)
A CNN-based pipeline that downloads open-access rare autoimmune disease papers from PubMed, extracts embedded figures (rash images, lab result charts, pathway diagrams, histology slides), and classifies them by type and clinical relevance. This unlocks insights that pure text mining completely misses.

- Model: Fine-tuned ResNet / ViT on medical figure datasets
- Input: Open-access PDFs from PubMed
- Output: Classified figure database with disease tags

### 2. Misdiagnosis Pattern Analyzer (NLP)
An NLP pipeline that mines thousands of PubMed case reports for rare autoimmune diseases, identifying the sequence of diagnoses a patient received before the correct one. This builds a structured misdiagnosis graph mapping which diseases get confused with which, and why.

- Model: HuggingFace Transformers (BioBERT / PubMedBERT)
- Input: PubMed case report abstracts + full texts
- Output: Disease misdiagnosis knowledge graph (NetworkX)

### 3. MCP Reasoning Agent (LLM + RAG)
An agentic LLM deployed via vLLM that connects signals from both pipelines. Using the Model Context Protocol (MCP), the agent calls tools to query the misdiagnosis graph, search Orphanet/OMIM databases, retrieve similar cases, and synthesize findings into a structured research report.

- LLM: Open-source biomedical model via vLLM
- Framework: LangChain + MCP tools
- Vector DB: FAISS / ChromaDB for semantic search
- Output: Per-disease research report with misdiagnosis pathways, visual phenotype summary, and research gaps

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

| Source | What We Use It For |
|---|---|
| [PubMed API](https://pubmed.ncbi.nlm.nih.gov/) | Case reports, open-access paper figures, literature search |
| [Orphanet](https://www.orphadata.com/) | 6,500+ rare diseases with symptoms, genes, and prevalence data |
| [OMIM API](https://www.omim.org/) | Genetic disease annotations and phenotype descriptions |
| [HPO](https://hpo.jax.org/) | Human Phenotype Ontology — standardized clinical vocabulary for symptoms |

All datasets are publicly available and free to use for research.

---

## Tech Stack

| Layer | Tools |
|---|---|
| Computer Vision | PyTorch, HuggingFace, ResNet / ViT |
| NLP | HuggingFace Transformers, BioBERT, spaCy |
| LLM Agent | vLLM, LangChain, MCP (Model Context Protocol) |
| Vector DB | FAISS / ChromaDB |
| Knowledge Graph | NetworkX |
| Data Pipeline | Python, PubMed API, Orphanet XML parser |
| Demo App | Streamlit |

---

## Target Diseases

| Disease | Why It's Included |
|---|---|
| Systemic Lupus Erythematosus (SLE) | Most common rare autoimmune disease, avg 6 year diagnosis delay |
| Sjögren's Syndrome | Frequently misdiagnosed as fibromyalgia or depression |
| Mixed Connective Tissue Disease (MCTD) | Overlaps with 4+ other autoimmune diseases |
| Inflammatory Myositis | Rare, visually diagnosable, limited literature |
| Antiphospholipid Syndrome | Often missed until a serious clotting event occurs |

---

## What You'll Learn Working on This

- Training CNNs on real medical image data with PyTorch
- Using HuggingFace Transformers for biomedical NLP
- Building and querying knowledge graphs with NetworkX
- Working with real public health APIs (PubMed, Orphanet, OMIM)
- Understanding how RAG pipelines and LLM agents work end-to-end
- Deploying open-source LLMs with vLLM

---

## Project Status

🚧 **Active Development** — currently recruiting team members via [AISC San Diego](https://aiscsandiego.netlify.app/)

---

# Week 1 (New Undergrads) - Start Here

Go to: `docs/week1/README.md`

Week 1 branch names (work only on your branch, never on `main`):
- `week1/nlp`
- `week1/biomedical`
- `week1/cv`
- `week1/backend`
- `week1/integration`
