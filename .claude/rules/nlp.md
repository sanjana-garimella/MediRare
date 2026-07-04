---
name: nlp-rules
description: Rules for the NLP pipeline. Loaded when editing nlp/ or data/nlp/.
globs:
  - "nlp/**"
  - "data/nlp/**"
---
# NLP pipeline rules

## PubMed fetching
- Always fetch via `nlp/fetch_pubmed_case_reports.py`. Do not add a second fetcher.
- As of 2026-07-03, this script queries PubMed through `paperscraper.pubmed.get_pubmed_papers` (pymed under the hood) rather than calling NCBI E-utilities directly. Raw PubMed query syntax (see `DISEASE_TERMS` / `MISDIAGNOSIS_TERMS`) is passed straight through, so query semantics are unchanged — benchmarked against the old direct-E-utilities implementation with no meaningful speed or noise-rate difference; switched per explicit request, not for measured benefit.
- Requires `paperscraper` (see `nlp/requirements.txt`). It pulls ~50 transitive packages (arxiv, scholarly, selenium, etc.) — only the PubMed path is used here.
- Raw XML goes to `data/nlp/raw/`. Processed JSONL goes to `data/nlp/processed/`.
- Filenames: raw = `{DISEASE}_{YYYYMMDD_HHMMSS}.xml`, processed = `{disease_lower}_case_reports.jsonl`.
- Do not add bioRxiv/medRxiv/arXiv as sources: sampled and found near-zero case-report-format content (cohort studies, trials, and ML papers instead), and none of those APIs support keyword search (category+date filtering only).

## Data quality
- Sjögren's must be fetched with `--focus misdiagnosis` (the default), which uses `MISDIAGNOSIS_TERMS["Sjogrens"]` (`"primary Sjogren's syndrome"[tiab] AND ...`) — not `--focus general`/`DISEASE_TERMS["Sjogrens"]` (`"Sjogren syndrome" AND "case report"`), which returns real off-topic noise (e.g. matches "Marinesco-Sjögren syndrome," a genetically unrelated disease, purely on substring).
- After any fetch, run the keyword signal check to confirm >5% of records contain misdiagnosis keywords.
- The `misdiagnosis_sequence` field must never be silently left as `[]` in final output — always note if extraction hasn't run yet.

## Disease scope (current)
- 12 active diseases, chosen by real PubMed misdiagnosis-focused literature volume: Sarcoidosis, SLE, IgG4-related disease, Guillain-Barre syndrome, Granulomatosis with polyangiitis, Myasthenia gravis, Behcet's disease, Castleman disease, Neuromyelitis optica, Antiphospholipid Syndrome, Sjogren's, MCTD. See `.claude/rules/data.md`.
- Inflammatory Myositis is out of scope (too thin at 17 total records). Do not add diseases outside the active list without confirming with Sanjana first.
- Fetched record counts vary hugely by disease (Sarcoidosis has 783 misdiagnosis-focused records in all of PubMed, Sjogren's has 38, MCTD has 21). This is a hard ceiling from the literature itself, not a fetch-tuning problem. Do not try to pad thin diseases with noisy general-query results without explicit confirmation.

## Misdiagnosis extraction
- Keyword triggers: "initially diagnosed with", "misdiagnosed as", "previously diagnosed", "presenting diagnosis", "referred after", "prior diagnosis", "delayed diagnosis", "wrongly diagnosed".
- Do not include differential diagnoses (things a doctor considered but didn't diagnose).
- Extraction output must conform to `schemas/case_report.py` — run `schemas/validate_jsonl.py` after any bulk write.
