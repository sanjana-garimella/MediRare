---
name: nlp-rules
description: Rules for the NLP pipeline. Loaded when editing nlp/ or data/nlp/.
globs:
  - "nlp/**"
  - "data/nlp/**"
---
# NLP pipeline rules

## PubMed fetching
- Always use NCBI E-utilities via `nlp/fetch_pubmed_case_reports.py`. Do not add a second fetcher.
- Respect the 0.34s sleep between requests. NCBI rate limit is 3 req/sec without an API key.
- Raw XML goes to `data/nlp/raw/`. Processed JSONL goes to `data/nlp/processed/`.
- Filenames: raw = `{DISEASE}_{YYYYMMDD_HHMMSS}.xml`, processed = `{disease_lower}_case_reports.jsonl`.

## Data quality
- Sjögren's search term must be `"primary Sjögren's syndrome" AND "case report"` — the plain `"Sjogren syndrome"` query returns 13/50 noise records.
- After any fetch, run the keyword signal check to confirm >5% of records contain misdiagnosis keywords.
- The `misdiagnosis_sequence` field must never be silently left as `[]` in final output — always note if extraction hasn't run yet.

## Misdiagnosis extraction
- Keyword triggers: "initially diagnosed with", "misdiagnosed as", "previously diagnosed", "presenting diagnosis", "referred after", "prior diagnosis", "delayed diagnosis", "wrongly diagnosed".
- Do not include differential diagnoses (things a doctor considered but didn't diagnose).
- Extraction output must conform to `schemas/case_report.py` — run `schemas/validate_jsonl.py` after any bulk write.
