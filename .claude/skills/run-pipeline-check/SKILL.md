---
name: run-pipeline-check
description: Run validation suite across schemas, processed data, and integration output.
when_to_use: Use when someone says "validate", "check the pipeline", "run tests", "is the data ready", or before any PR or handoff.
disable-model-invocation: false
allowed-tools: Read, Bash(python3:*), Bash(find:*)
---
# run-pipeline-check

## Steps

1. **Schema tests**:
   ```bash
   python3 -m pytest tests/test_schemas.py -v
   ```

2. **Validate processed JSONL** (run all three):
   ```bash
   python3 schemas/validate_jsonl.py data/nlp/processed/sle_case_reports.jsonl
   python3 schemas/validate_jsonl.py data/nlp/processed/sjogrens_case_reports.jsonl
   python3 schemas/validate_jsonl.py data/nlp/processed/mctd_case_reports.jsonl
   ```

3. **Misdiagnosis coverage** — report what % of records have non-empty `misdiagnosis_sequence`. Flag if 0% (extraction hasn't run).

4. **Integration output** — if `integration/merged_records.jsonl` exists, validate and report record count.

5. **Week 1 check scripts**:
   ```bash
   python3 scripts/week1_check.py --role nlp
   python3 scripts/week1_check.py --role biomedical
   ```

## Output format
- One line per check: ✓ PASS or ✗ FAIL with detail
- Summary: X/Y checks passed
- If FAIL: exact fix required
