"""
Validate a JSONL file against one of the Pydantic models.

Usage:
  python schemas/validate_jsonl.py path/to/file.jsonl CaseReport
"""

from __future__ import annotations

import json
import sys

from schemas.case_report import CaseReport
from schemas.extracted_figure import ExtractedFigure
from schemas.merged_record import MergedRecord


MODELS = {
    "CaseReport": CaseReport,
    "ExtractedFigure": ExtractedFigure,
    "MergedRecord": MergedRecord,
}


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python schemas/validate_jsonl.py <path> <ModelName>")
        print("ModelName: CaseReport | ExtractedFigure | MergedRecord")
        return 2

    path = sys.argv[1]
    model_name = sys.argv[2]
    Model = MODELS.get(model_name)
    if Model is None:
        print(f"Unknown ModelName: {model_name}")
        return 2

    errors = 0
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                Model.model_validate(obj)
            except Exception as e:
                errors += 1
                print(f"Line {i}: {e}")

    if errors:
        print(f"FAILED: {errors} validation errors")
        return 1
    print("OK: 0 validation errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

