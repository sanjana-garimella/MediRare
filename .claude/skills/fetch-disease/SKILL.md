---
name: fetch-disease
description: Fetch PubMed case reports for a disease, run quality review, and report results.
when_to_use: Use when someone says "fetch data for X", "get PubMed records for X", or "add X to the pipeline". Do NOT use for undergrad diseases (MCTD, Inflammatory Myositis, APS) without Sanjana's confirmation.
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash(python3:*), Bash(grep:*), Bash(wc:*)
---
# fetch-disease

## Steps

1. **Check scope** — SLE and Sjögren's are Sanjana's. MCTD/Inflammatory Myositis/APS are undergrad scope, confirm before fetching.

2. **Check `DISEASE_TERMS`** in `nlp/fetch_pubmed_case_reports.py`. If the disease is missing, add it using `"primary [disease name]" AND "case report"` to reduce noise.

3. **Fetch**:
   ```bash
   python3 nlp/fetch_pubmed_case_reports.py --disease <DISEASE> --retmax 50
   ```

4. **Invoke the `data-reviewer` subagent** — it checks abstract coverage, noise rate, and misdiagnosis signal density and returns PASS / NEEDS-REVIEW / BLOCK.

5. **Report**: record count, abstract coverage, noise rate, misdiagnosis signal rate, blocker if any, output file location.

## Do not
- Do not commit raw XML (`data/nlp/raw/`)
- Do not overwrite `data/biomedical/annotated_cases.csv`
- Do not fetch > 200 records per run
