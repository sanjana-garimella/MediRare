#!/usr/bin/env python3
"""
Week 1 self-check (beginner-friendly).

This script is designed to answer: "Did I do Week 1 correctly?"

It checks:
- You're not on main
- Expected starter files exist for your role
- Biomedical CSV templates have the right headers
- If local generated outputs exist, they parse and (optionally) validate against schemas

Usage:
  python scripts/week1_check.py --role nlp
  python scripts/week1_check.py --role cv
  python scripts/week1_check.py --role biomedical
  python scripts/week1_check.py --role backend
  python scripts/week1_check.py --role integration
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


ROLE_FILES: dict[str, list[str]] = {
    "nlp": [
        "nlp/fetch_pubmed_case_reports.py",
        "docs/week1/nlp.md",
    ],
    "cv": [
        "cv/extract_figures.py",
        "docs/week1/cv.md",
    ],
    "biomedical": [
        "data/biomedical/label_guide.md",
        "data/biomedical/annotations.csv",
        "data/biomedical/hpo_mapping.csv",
        "docs/week1/biomedical.md",
    ],
    "backend": [
        "schemas/case_report.py",
        "schemas/extracted_figure.py",
        "schemas/merged_record.py",
        "schemas/validate_jsonl.py",
        "tests/test_schemas.py",
        "docs/week1/backend.md",
    ],
    "integration": [
        "integration/merge.py",
        "integration/mock_case_reports.jsonl",
        "integration/mock_extracted_figures.jsonl",
        "demo/app.py",
        "docs/week1/integration.md",
    ],
}


EXPECTED_CSV_HEADERS: dict[str, str] = {
    "data/biomedical/annotations.csv": "pubmed_id,final_diagnosis,misdiagnoses_before_correct,key_symptoms,notes",
    "data/biomedical/hpo_mapping.csv": "symptom_phrase,hpo_id,hpo_label,disease,notes",
}


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out.strip()


def fail(msg: str) -> int:
    print(f"[FAIL] {msg}")
    return 1


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def check_not_on_main() -> int:
    code, out = run(["git", "branch", "--show-current"])
    if code != 0:
        return fail("Could not detect git branch (are you in the repo?)")
    branch = out.strip()
    if branch in ("main", "master", ""):
        return fail(f"You are on branch '{branch or '(unknown)'}'. Switch to your Week 1 role branch.")
    ok(f"On branch '{branch}' (not main).")
    return 0


def check_files(role: str) -> int:
    missing = []
    for rel in ROLE_FILES[role]:
        if not (REPO_ROOT / rel).exists():
            missing.append(rel)
    if missing:
        return fail(f"Missing required files for role '{role}': {', '.join(missing)}")
    ok(f"All required starter files exist for role '{role}'.")
    return 0


def check_csv_headers() -> int:
    for rel, header in EXPECTED_CSV_HEADERS.items():
        p = REPO_ROOT / rel
        if not p.exists():
            return fail(f"Missing CSV template: {rel}")
        first = p.read_text(encoding="utf-8").splitlines()[0].strip()
        if first != header:
            return fail(f"CSV header mismatch in {rel}. Expected: {header} | Got: {first}")
    ok("Biomedical CSV template headers look correct.")
    return 0


def check_jsonl_parses(path: Path) -> int:
    # Quick parse check only.
    bad = 0
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                json.loads(line)
            except Exception:
                bad += 1
                if bad <= 3:
                    print(f"[FAIL] JSON parse error in {path} at line {i}")
    if bad:
        return 1
    ok(f"JSONL parses: {path}")
    return 0


def maybe_validate_outputs(role: str) -> int:
    """
    If local generated outputs exist, validate them.
    This is optional because outputs are not committed to git.
    """
    checks: list[tuple[str, str]] = []
    if role == "nlp":
        checks.append(("data/nlp/processed/sle_case_reports.jsonl", "CaseReport"))
    if role == "cv":
        checks.append(("data/cv/metadata/extracted_figures.jsonl", "ExtractedFigure"))
    if role == "integration":
        checks.append(("integration/merged_records.jsonl", "MergedRecord"))

    validator = REPO_ROOT / "schemas/validate_jsonl.py"
    for rel, model in checks:
        p = REPO_ROOT / rel
        if not p.exists():
            print(f"[SKIP] Optional output not found (this is OK): {rel}")
            continue
        if check_jsonl_parses(p) != 0:
            return fail(f"JSONL is not valid JSONL: {rel}")
        if validator.exists():
            code, out = run([sys.executable, "schemas/validate_jsonl.py", rel, model])
            if code != 0:
                print(out)
                return fail(f"Schema validation failed for {rel} as {model}")
            ok(f"Schema validates: {rel} as {model}")
        else:
            print("[SKIP] Validator not found; cannot schema-validate outputs.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", required=True, choices=sorted(ROLE_FILES.keys()))
    args = ap.parse_args()

    rc = 0
    rc |= check_not_on_main()
    rc |= check_files(args.role)
    rc |= check_csv_headers()
    rc |= maybe_validate_outputs(args.role)

    if rc == 0:
        ok("Week 1 checks passed.")
    else:
        print("Some checks failed. Fix the FAIL items and rerun this command.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

