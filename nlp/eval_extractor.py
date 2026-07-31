#!/usr/bin/env python3
"""
Evaluate the misdiagnosis extractor against hand-labeled ground truth.

Usage:
    python3 nlp/eval_extractor.py \
        --pred data/nlp/processed/sle_case_reports.jsonl \
        --truth data/biomedical/sle_misdiagnosis_groundtruth.csv

Reports document-level binary classification:
    predicted positive = misdiagnosis_sequence is non-empty
    actual positive    = has_misdiagnosis == 1 in the ground-truth CSV

It also reads `true_wrong_diagnosis` and reports entity-level exact and
normalized micro set precision / recall / F1. Normalization is limited to
case, punctuation, diacritics, and a small explicit abbreviation map.

NOTE: the labels are AI-proposed and need clinician review. The Sjögren's and
MCTD files were partly derived from extractor/keyword output and are circular
internal diagnostics, not independent validation. ``annotated_cases.csv`` is
synthetic placeholder data and is not a gold set.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from pathlib import Path


def load_predictions(path: Path) -> dict[str, list[str]]:
    preds: dict[str, list[str]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            pid = str(r["pubmed_id"])
            if pid in preds:
                raise ValueError(f"duplicate prediction pubmed_id: {pid}")
            preds[pid] = list(r.get("misdiagnosis_sequence") or [])
    return preds


def _split_truth_entities(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s*[;|]\s*", value or "") if part.strip()]


def load_truth(path: Path) -> dict[str, dict]:
    truth: dict[str, dict] = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = str(row["pubmed_id"])
            if pid in truth:
                raise ValueError(f"duplicate truth pubmed_id: {pid}")
            truth[pid] = {
                "has_misdiagnosis": int(row["has_misdiagnosis"]),
                "entities": _split_truth_entities(row.get("true_wrong_diagnosis", "")),
                "review_status": row.get("review_status", ""),
                "rationale": row.get("rationale", ""),
            }
    return truth


_ALIASES = {
    "tb": "tuberculosis",
    "sle": "systemic lupus erythematosus",
    "lupus": "systemic lupus erythematosus",
    "ra": "rheumatoid arthritis",
    "nmosd": "neuromyelitis optica spectrum disorder",
    "mctd": "mixed connective tissue disease",
}


def normalize_entity(entity: str) -> str:
    text = unicodedata.normalize("NFKD", entity or "")
    text = text.encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return _ALIASES.get(text, text)


def entity_metrics(
    predictions: dict[str, list[str]],
    truth: dict[str, dict],
    ids: list[str],
    *,
    normalized: bool,
) -> dict[str, float | int]:
    tp = fp = fn = 0
    for pid in ids:
        pred = set(predictions[pid])
        actual = set(truth[pid]["entities"])
        if normalized:
            pred = {normalize_entity(entity) for entity in pred}
            actual = {normalize_entity(entity) for entity in actual}
        pred.discard("")
        actual.discard("")
        tp += len(pred & actual)
        fp += len(pred - actual)
        fn += len(actual - pred)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pred", required=True, help="Processed JSONL with predictions")
    ap.add_argument("--truth", required=True, help="Ground-truth CSV")
    args = ap.parse_args()

    preds = load_predictions(Path(args.pred))
    truth = load_truth(Path(args.truth))

    pred_only = sorted(set(preds) - set(truth))
    truth_only = sorted(set(truth) - set(preds))
    ids = sorted(set(truth) & set(preds))
    if not ids:
        print("ERROR: no overlapping pubmed_ids between predictions and truth")
        return 1

    tp = fp = fn = tn = 0
    fn_ids: list[str] = []
    fp_ids: list[str] = []
    for pid in ids:
        p = bool(preds[pid])
        t = bool(truth[pid]["has_misdiagnosis"])
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
    print(f"  ID coverage   : {len(ids)} overlap / {len(preds)} predictions / {len(truth)} labels")
    if pred_only:
        print(f"  Excluded predictions without labels ({len(pred_only)}): {', '.join(pred_only)}")
    if truth_only:
        print(f"  Excluded labels without predictions ({len(truth_only)}): {', '.join(truth_only)}")
    print(f"  Precision : {precision:.2f}   (of flagged records, fraction correct)")
    print(f"  Recall    : {recall:.2f}   (of real misdiagnoses, fraction caught)")
    print(f"  F1        : {f1:.2f}")
    print(f"  Accuracy  : {accuracy:.2f}   (vs {baseline:.2f} majority-class baseline)")
    print()
    exact = entity_metrics(preds, truth, ids, normalized=False)
    normalized = entity_metrics(preds, truth, ids, normalized=True)
    print("Entity-level micro set metrics (`true_wrong_diagnosis`; ';' or '|' separates entities):")
    print(
        f"  Exact      P={exact['precision']:.2f} R={exact['recall']:.2f} "
        f"F1={exact['f1']:.2f} (TP={exact['tp']} FP={exact['fp']} FN={exact['fn']})"
    )
    print(
        f"  Normalized P={normalized['precision']:.2f} R={normalized['recall']:.2f} "
        f"F1={normalized['f1']:.2f} "
        f"(TP={normalized['tp']} FP={normalized['fp']} FN={normalized['fn']}; "
        "case/punctuation/diacritics + conservative aliases)"
    )
    positive_without_entities = sum(
        truth[pid]["has_misdiagnosis"] and not truth[pid]["entities"] for pid in ids
    )
    print(
        "  Entity recall is conditional on supplied entity labels; "
        f"{positive_without_entities} positive records have no entity label."
    )
    print()
    if fn_ids:
        print(f"  False negatives (missed real misdiagnoses): {', '.join(fn_ids)}")
    if fp_ids:
        print(f"  False positives (false alarms): {', '.join(fp_ids)}")
    print()
    circular = any(
        "Extractor populated" in truth[pid].get("rationale", "")
        or "keyword present" in truth[pid].get("rationale", "").lower()
        for pid in ids
    )
    print("Limit: all current labels are AI-proposed, not clinician-reviewed.")
    if circular:
        print("CIRCULAR DATASET: these scores measure internal parse/self-consistency only,")
        print("not extractor accuracy or independent clinical validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
