#!/usr/bin/env bash
# reproduce.sh — regenerate the analysis corpus from scratch
#
# Test: can a stranger clone this repo and reproduce the analysis?
#   git clone <repo> && cd MediRare && bash scripts/reproduce.sh
#
# Prerequisites: Python 3.10+, pip install -r requirements.txt
# NCBI rate limit: 3 req/sec without API key.
# All outputs go to data/nlp/processed/ and data/cv/

set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== MediRare — full pipeline reproduction ==="
echo ""

# ── 1. Fetch PubMed case reports ─────────────────────────────────────────────
# SLE is misdiagnosis-focused (the active disease); the others stay general.
echo "[1/6] Fetching PubMed case reports ..."
python3 nlp/fetch_pubmed_case_reports.py --disease SLE      --retmax 100 --focus misdiagnosis
python3 nlp/fetch_pubmed_case_reports.py --disease Sjogrens --retmax 50  --focus general
python3 nlp/fetch_pubmed_case_reports.py --disease MCTD     --retmax 50  --focus general

echo ""
echo "[2/6] Validating fetched records ..."
python3 -m schemas.validate_jsonl data/nlp/processed/sle_case_reports.jsonl      CaseReport
python3 -m schemas.validate_jsonl data/nlp/processed/sjogrens_case_reports.jsonl CaseReport
python3 -m schemas.validate_jsonl data/nlp/processed/mctd_case_reports.jsonl     CaseReport

# ── 3. Run misdiagnosis extractor (SLE — first pass) ─────────────────────────
echo ""
echo "[3/6] Running misdiagnosis extractor on SLE records ..."
python3 nlp/extract_misdiagnosis.py data/nlp/processed/sle_case_reports.jsonl
python3 -m schemas.validate_jsonl data/nlp/processed/sle_case_reports.jsonl CaseReport

# ── 4. Evaluate extractor against ground truth ───────────────────────────────
# NOTE: ground truth is keyed to specific PMIDs. Re-running step 1 fetches a
# fresh PMID set, so the labels only line up if the corpus is unchanged. After a
# re-fetch, re-label data/biomedical/sle_misdiagnosis_groundtruth.csv before
# trusting these numbers.
echo ""
echo "[4/6] Evaluating extractor (confusion matrix) ..."
python3 nlp/eval_extractor.py \
    --pred data/nlp/processed/sle_case_reports.jsonl \
    --truth data/biomedical/sle_misdiagnosis_groundtruth.csv || true

# ── 5. Fetch CV figure metadata from PMC open-access articles ────────────────
echo ""
echo "[5/6] Fetching clinical figure metadata from PMC open-access articles ..."
python3 cv/fetch_pmc_figures.py \
    --jsonl data/nlp/processed/sle_case_reports.jsonl \
            data/nlp/processed/sjogrens_case_reports.jsonl \
            data/nlp/processed/mctd_case_reports.jsonl \
    --out data/cv/figure_metadata.jsonl

# ── 6. Pipeline health check ─────────────────────────────────────────────────
echo ""
echo "[6/6] Running pipeline health checks ..."
python3 scripts/week1_check.py --role nlp
python3 scripts/week1_check.py --role biomedical

echo ""
echo "=== Done. ==="
echo "  NLP: data/nlp/processed/        (SLE=100 misdiagnosis-focused, others=50)"
echo "  CV:  data/cv/figure_metadata.jsonl  (figure metadata from PMC open-access)"
echo "  Gold: data/biomedical/annotated_cases.csv  (10 hand-crafted cases — DO NOT OVERWRITE)"
echo ""
echo "NOTE: SLE extractor recall is ~0.22 (keyword/regex). Full extraction needs"
echo "      PubMedBERT on PMC full text — see roadmap."
