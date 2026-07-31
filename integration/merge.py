from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from schemas.merged_record import MergedRecord


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def flatten_figure_metadata(rows: list[dict]) -> list[dict]:
    """Convert article metadata into the declared ExtractedFigure contract."""
    flat: list[dict] = []
    converted_at = datetime.now(timezone.utc).isoformat()
    for art in rows:
        pid = str(art.get("pubmed_id") or "")
        disease = str(art.get("disease") or "")
        for position, fig in enumerate(art.get("figures") or [], start=1):
            label_match = re.search(r"\d+", str(fig.get("label") or ""))
            item = {
                "pubmed_id": pid,
                "disease": disease,
                "figure_index": int(label_match.group()) if label_match else position,
                "figure_type": fig.get("figure_type") or "other",
                "file_path": fig.get("file_path") or fig.get("img_ref") or "",
                "caption": fig.get("caption") or "",
                "clinical_relevance": fig.get("clinical_relevance") or "unknown",
                "extracted_at": (
                    fig.get("extracted_at")
                    or art.get("extracted_at")
                    or converted_at
                ),
                "source_pdf": fig.get("source_pdf") or art.get("pmc_id") or "",
            }
            flat.append(item)
        # Articles with zero figures still shouldn't create phantom figure rows
    return flat


def merge_records(case_reports: list[dict], figures: list[dict]) -> list[dict]:
    def key(row: dict) -> tuple[str, str]:
        return str(row.get("disease") or "").strip(), str(row["pubmed_id"]).strip()

    case_by_key: dict[tuple[str, str], dict] = {}
    for report in case_reports:
        report_key = key(report)
        if report_key in case_by_key:
            raise ValueError(f"duplicate case report for disease/PMID {report_key}")
        case_by_key[report_key] = report

    figs_by_key = defaultdict(list)
    unscoped_figs_by_id = defaultdict(list)
    for f in figures:
        figure_key = key(f)
        if figure_key[0]:
            figs_by_key[figure_key].append(f)
        else:
            unscoped_figs_by_id[figure_key[1]].append(f)

    case_keys_by_id: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for case_key in case_by_key:
        case_keys_by_id[case_key[1]].append(case_key)
    for pid, unscoped in unscoped_figs_by_id.items():
        matches = case_keys_by_id.get(pid, [])
        if len(matches) == 1:
            figs_by_key[matches[0]].extend(unscoped)
        else:
            # Zero matches remain figure-only; multiple matches are deliberately
            # kept unscoped rather than being duplicated across diseases.
            figs_by_key[("", pid)].extend(unscoped)

    all_keys = set(case_by_key) | set(figs_by_key)
    now = datetime.now(timezone.utc).isoformat()
    merged = []
    for disease, pid in sorted(all_keys):
        attached_figures = figs_by_key.get((disease, pid), [])
        merged.append(
            {
                "pubmed_id": pid,
                "disease": disease,
                "case_report": case_by_key.get((disease, pid)),
                "figures": attached_figures,
                "merged_at": now,
            }
        )
    return merged


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--real",
        action="store_true",
        help="Merge real processed NLP JSONLs + data/cv/figure_metadata.jsonl (default: mocks)",
    )
    ap.add_argument("--out", default="integration/merged_records.jsonl")
    args = ap.parse_args()

    if args.real:
        case_paths = [
            Path("data/nlp/processed/sle_case_reports.jsonl"),
            Path("data/nlp/processed/sjogrens_case_reports.jsonl"),
            Path("data/nlp/processed/mctd_case_reports.jsonl"),
        ]
        case_reports: list[dict] = []
        for p in case_paths:
            if p.exists():
                case_reports.extend(load_jsonl(p))
        fig_path = Path("data/cv/figure_metadata.jsonl")
        figures = flatten_figure_metadata(load_jsonl(fig_path)) if fig_path.exists() else []
    else:
        case_reports = load_jsonl(Path("integration/mock_case_reports.jsonl"))
        figures = load_jsonl(Path("integration/mock_extracted_figures.jsonl"))

    merged = merge_records(case_reports, figures)
    # Fail the e2e build if either NLP or CV data violates the public contract.
    merged = [
        MergedRecord.model_validate(record).model_dump(mode="json")
        for record in merged
    ]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in merged:
            f.write(json.dumps(r, ensure_ascii=True) + "\n")

    print(f"Wrote {out_path} ({len(merged)} rows; real={args.real})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
