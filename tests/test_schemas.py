from __future__ import annotations

from datetime import datetime, timezone

import pytest

from schemas.case_report import CaseReport
from schemas.extracted_figure import ExtractedFigure


def test_case_report_valid():
    r = CaseReport(
        pubmed_id="12345678",
        disease="SLE",
        title="t",
        abstract="a",
        misdiagnosis_sequence=[],
        extracted_at=datetime.now(timezone.utc),
    )
    assert r.pubmed_id == "12345678"


def test_case_report_missing_required_fails():
    with pytest.raises(Exception):
        CaseReport(  # type: ignore
            disease="SLE",
            title="t",
            abstract="a",
            extracted_at=datetime.now(timezone.utc),
        )


def test_extracted_figure_valid_minimal():
    f = ExtractedFigure(
        pubmed_id="12345678",
        figure_index=0,
        file_path="data/cv/figures/x.png",
        extracted_at=datetime.now(timezone.utc),
    )
    assert f.figure_type == "other"


def test_biomedical_csv_templates_have_expected_headers():
    # These templates are committed and should not change silently.
    annotations = "data/biomedical/annotated_cases.csv"
    mapping = "data/biomedical/hpo_mapping_table.csv"

    with open(annotations, "r", encoding="utf-8") as f:
        first = f.readline().strip()
    assert first == "pubmed_id,disease,title,abstract,misdiagnosis_sequence,extracted_at,annotation_confidence,annotator_notes"

    with open(mapping, "r", encoding="utf-8") as f:
        first = f.readline().strip()
    assert first == "disease,hpo_id,hpo_term,phenotype_category,clinical_relevance,notes"
