"""Tests for scripts/week1_check.py biomedical CSV + validator invocation."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_expected_csv_headers_match_committed_files():
    # Import after path setup so the script's module-level constants load.
    sys.path.insert(0, str(REPO / "scripts"))
    import week1_check  # noqa: E402

    for rel, expected in week1_check.EXPECTED_CSV_HEADERS.items():
        first = (REPO / rel).read_text(encoding="utf-8").splitlines()[0].strip()
        assert first == expected, f"{rel}: {first!r} != {expected!r}"


def test_validate_jsonl_module_form_works_without_preexisting_pythonpath():
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONPATH"] = str(REPO)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "schemas.validate_jsonl",
            "data/nlp/processed/sle_case_reports.jsonl",
            "CaseReport",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK" in proc.stdout
