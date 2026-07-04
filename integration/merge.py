from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def merge_records(case_reports: list[dict], figures: list[dict]) -> list[dict]:
    case_by_id = {r["pubmed_id"]: r for r in case_reports}
    figs_by_id = defaultdict(list)
    for f in figures:
        figs_by_id[f["pubmed_id"]].append(f)

    all_ids = sorted(set(case_by_id.keys()) | set(figs_by_id.keys()))
    now = datetime.now(timezone.utc).isoformat()
    merged = []
    for pid in all_ids:
        disease = None
        if pid in case_by_id:
            disease = case_by_id[pid].get("disease")
        elif figs_by_id[pid]:
            disease = figs_by_id[pid][0].get("disease")
        merged.append(
            {
                "pubmed_id": pid,
                "disease": disease or "",
                "case_report": case_by_id.get(pid),
                "figures": figs_by_id.get(pid, []),
                "merged_at": now,
            }
        )
    return merged


def main() -> int:
    case_reports = load_jsonl(Path("integration/mock_case_reports.jsonl"))
    figures = load_jsonl(Path("integration/mock_extracted_figures.jsonl"))
    merged = merge_records(case_reports, figures)

    out_path = Path("integration/merged_records.jsonl")
    with out_path.open("w", encoding="utf-8") as f:
        for r in merged:
            f.write(json.dumps(r, ensure_ascii=True) + "\n")

    print(f"Wrote {out_path} ({len(merged)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

