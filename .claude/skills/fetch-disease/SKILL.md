---
name: fetch-disease
description: Fetch PubMed case reports for a disease, run quality review, and report results.
when_to_use: Use when someone says "fetch data for X", "get PubMed records for X", or "add X to the pipeline" — for SLE or Sjögren's only. Do NOT use for MCTD, Inflammatory Myositis, or APS at all — they are out of scope until SLE + Sjögren's are complete (see .claude/rules/data.md).
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash(python3:*), Bash(grep:*), Bash(wc:*)
---
# fetch-disease

## Steps

1. **Check scope** — only SLE and Sjögren's are in scope right now. MCTD/Inflammatory Myositis/APS are out of scope entirely until both are complete — do not fetch for them even with confirmation; stop and tell Sanjana instead.

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
