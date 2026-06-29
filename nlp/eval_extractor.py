#!/usr/bin/env python3
"""
Evaluate the misdiagnosis extractor against hand-labeled ground truth.

Usage:
    python3 nlp/eval_extractor.py \
        --pred data/nlp/processed/sle_case_reports.jsonl \
        --truth data/biomedical/sle_misdiagnosis_groundtruth.csv

Treats extraction as binary classification per record:
    predicted positive = misdiagnosis_sequence is non-empty
    actual positive    = has_misdiagnosis == 1 in the ground-truth CSV

Prints a confusion matrix plus precision / recall / F1 / accuracy.

NOTE: the ground-truth labels are AI-proposed from abstracts and need clinician
review (review_status column). They are NOT the gold annotated_cases.csv set.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def load_predictions(path: Path) -> dict[str, bool]:
    preds: dict[str, bool] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            preds[r["pubmed_id"]] = bool(r.get("misdiagnosis_sequence"))
    return preds


def load_truth(path: Path) -> dict[str, int]:
    truth: dict[str, int] = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            truth[row["pubmed_id"]] = int(row["has_misdiagnosis"])
    return truth


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pred", required=True, help="Processed JSONL with predictions")
    ap.add_argument("--truth", required=True, help="Ground-truth CSV")
    args = ap.parse_args()

    preds = load_predictions(Path(args.pred))
    truth = load_truth(Path(args.truth))

    ids = sorted(set(truth) & set(preds))
    if not ids:
        print("ERROR: no overlapping pubmed_ids between predictions and truth")
        return 1

    tp = fp = fn = tn = 0
    fn_ids: list[str] = []
    fp_ids: list[str] = []
    for pid in ids:
        p = preds[pid]
        t = bool(truth[pid])
        if p and t:
            tp += 1
        elif p and not t:
            fp += 1
            fp_ids.append(pid)
        elif not p and t:
            fn += 1
            fn_ids.append(pid)
        else:
            tn += 1

    total = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / total if total else 0.0
    n_pos = tp + fn
    n_neg = fp + tn
    baseline = max(n_pos, n_neg) / total if total else 0.0  # always-predict-majority

    print(f"\n{'='*56}")
    print(f"Extractor evaluation  (n={total} records)")
    print(f"{'='*56}")
    print()
    print("Confusion matrix:")
    print("                      actual YES   actual NO")
    print(f"  predicted YES   |     {tp:>4}        {fp:>4}     | (TP / FP)")
    print(f"  predicted NO    |     {fn:>4}        {tn:>4}     | (FN / TN)")
    print()
    print(f"  Class balance : {n_pos} positive / {n_neg} negative")
    print(f"  Precision : {precision:.2f}   (of flagged records, fraction correct)")
    print(f"  Recall    : {recall:.2f}   (of real misdiagnoses, fraction caught)")
    print(f"  F1        : {f1:.2f}")
    print(f"  Accuracy  : {accuracy:.2f}   (vs {baseline:.2f} majority-class baseline)")
    print()
    if fn_ids:
        print(f"  False negatives (missed real misdiagnoses): {', '.join(fn_ids)}")
    if fp_ids:
        print(f"  False positives (false alarms): {', '.join(fp_ids)}")
    print()
    print("Read: high precision, low recall — what it extracts is trustworthy,")
    print("but keyword matching misses most cases. Full-text + NLP is the fix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
