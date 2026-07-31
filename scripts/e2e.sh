#!/usr/bin/env bash
# End-to-end rebuild for SLE + Sjögren's + MCTD (assumes fetches already done).
# Usage: bash scripts/e2e.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.

# Plain extraction is preservation-safe: stronger/reviewed prior sequences survive.
# LLM assist remains opt-in until grounded-filtered entity F1 is demonstrated.
echo "== 1. Extract misdiagnosis sequences (preserving stronger existing evidence) =="
python3 nlp/extract_misdiagnosis.py data/nlp/processed/sle_case_reports.jsonl
python3 nlp/extract_misdiagnosis.py data/nlp/processed/sjogrens_case_reports.jsonl
python3 nlp/extract_misdiagnosis.py data/nlp/processed/mctd_case_reports.jsonl

echo "== 2. Validate =="
python3 -m schemas.validate_jsonl data/nlp/processed/sle_case_reports.jsonl CaseReport
python3 -m schemas.validate_jsonl data/nlp/processed/sjogrens_case_reports.jsonl CaseReport
python3 -m schemas.validate_jsonl data/nlp/processed/mctd_case_reports.jsonl CaseReport

echo "== 3. Chunk =="
python3 rag/chunk.py \
  --jsonl data/nlp/processed/sle_case_reports.jsonl \
          data/nlp/processed/sjogrens_case_reports.jsonl \
          data/nlp/processed/mctd_case_reports.jsonl \
  --out data/rag/chunks.jsonl

echo "== 4. Index (LanceDB + BM25) =="
python3 rag/index.py --chunks data/rag/chunks.jsonl --out data/rag/index

echo "== 5. Reviewed graph (fail-closed) + unreviewed annotation queue =="
python3 graph/build_graph.py \
  --jsonl data/nlp/processed/sle_case_reports.jsonl \
          data/nlp/processed/sjogrens_case_reports.jsonl \
          data/nlp/processed/mctd_case_reports.jsonl \
  --out data/graph/misdiagnosis_graph.json
python3 graph/build_graph.py \
  --jsonl data/nlp/processed/sle_case_reports.jsonl \
          data/nlp/processed/sjogrens_case_reports.jsonl \
          data/nlp/processed/mctd_case_reports.jsonl \
  --include-unreviewed \
  --out data/graph/candidate_misdiagnosis_graph.json

echo "== 6. Merge real NLP + CV =="
python3 integration/merge.py --real
python3 -m schemas.validate_jsonl integration/merged_records.jsonl MergedRecord

echo "== Done =="
echo "Ask (reviewed evidence only): PYTHONPATH=. python3 agent/ask.py --query 'TB mimic pleural SLE'"
echo "Internal unreviewed mode: add --allow-unreviewed"
echo "Demo:  streamlit run demo/app.py"
