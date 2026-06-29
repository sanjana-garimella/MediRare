#!/usr/bin/env bash
# reproduce.sh — regenerate the full 150-case analysis from scratch
#
# Test: can a stranger clone this repo and reproduce the analysis?
#   git clone <repo> && cd MediRare && bash scripts/reproduce.sh
#
# Prerequisites: Python 3.10+, pip install -r requirements.txt
# NCBI rate limit: 3 req/sec without API key. Fetches take ~30s per disease.
# All outputs go to data/nlp/processed/ and data/cv/

set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== MediRare — full pipeline reproduction ==="
echo ""

# ── 1. Fetch PubMed case reports ─────────────────────────────────────────────
echo "[1/4] Fetching PubMed case reports (50 per disease) ..."
python3 nlp/fetch_pubmed_case_reports.py --disease SLE      --retmax 50
python3 nlp/fetch_pubmed_case_reports.py --disease Sjogrens  --retmax 50
python3 nlp/fetch_pubmed_case_reports.py --disease MCTD     --retmax 50

echo ""
echo "[2/4] Validating fetched records ..."
python3 -m schemas.validate_jsonl data/nlp/processed/sle_case_reports.jsonl     CaseReport
python3 -m schemas.validate_jsonl data/nlp/processed/sjogrens_case_reports.jsonl CaseReport
python3 -m schemas.validate_jsonl data/nlp/processed/mctd_case_reports.jsonl    CaseReport

# ── 3. Run misdiagnosis extractor (SLE only — first pass) ────────────────────
echo ""
echo "[3/4] Running misdiagnosis extractor on SLE records ..."
python3 nlp/extract_misdiagnosis.py data/nlp/processed/sle_case_reports.jsonl
python3 -m schemas.validate_jsonl data/nlp/processed/sle_case_reports.jsonl CaseReport

# ── 4. Pipeline health check ─────────────────────────────────────────────────
echo ""
echo "[4/4] Running pipeline health checks ..."
python3 scripts/week1_check.py --role nlp
python3 scripts/week1_check.py --role biomedical

echo ""
echo "=== Done. ==="
echo "  NLP: data/nlp/processed/  (3 JSONL files, 50 records each)"
echo "  CV:  data/cv/figure_metadata.jsonl  (17 figures, 8 open-access articles)"
echo "  Gold: data/biomedical/annotated_cases.csv  (10 hand-crafted cases — DO NOT OVERWRITE)"
echo ""
echo "NOTE: misdiagnosis_sequence is populated for 1/50 SLE records via keyword pass."
echo "      Full extraction requires NLP (PubMedBERT) on PMC full text — see roadmap."
