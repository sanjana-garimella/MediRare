from __future__ import annotations

from pathlib import Path

from integration.merge import flatten_figure_metadata, load_jsonl, merge_records
from schemas.extracted_figure import ExtractedFigure


def test_load_jsonl_reads_mock_case_reports():
    rows = load_jsonl(Path("integration/mock_case_reports.jsonl"))
    assert len(rows) == 5
    assert {r["pubmed_id"] for r in rows} == {
        "11111111",
        "22222222",
        "33333333",
        "44444444",
        "55555555",
    }


def test_load_jsonl_skips_blank_lines(tmp_path):
    path = tmp_path / "sample.jsonl"
    path.write_text('{"a": 1}\n\n{"a": 2}\n', encoding="utf-8")
    assert load_jsonl(path) == [{"a": 1}, {"a": 2}]


def _load_mocks() -> tuple[list[dict], list[dict]]:
    case_reports = load_jsonl(Path("integration/mock_case_reports.jsonl"))
    figures = load_jsonl(Path("integration/mock_extracted_figures.jsonl"))
    return case_reports, figures


def test_merge_records_outer_join_union_of_ids():
    case_reports, figures = _load_mocks()
    merged = merge_records(case_reports, figures)
    assert {r["pubmed_id"] for r in merged} == {
        "11111111",
        "22222222",
        "33333333",
        "44444444",
        "55555555",
        "66666666",
    }


def test_merge_records_case_only_gets_empty_figures():
    case_reports, figures = _load_mocks()
    merged = {r["pubmed_id"]: r for r in merge_records(case_reports, figures)}
    record = merged["33333333"]
    assert record["case_report"] is not None
    assert record["figures"] == []


def test_merge_records_figure_only_gets_none_case_report_and_disease_fallback():
    case_reports, figures = _load_mocks()
    merged = {r["pubmed_id"]: r for r in merge_records(case_reports, figures)}
    record = merged["66666666"]
    assert record["case_report"] is None
    assert record["disease"] == "SLE"


def test_merge_records_both_present_merges_correctly():
    case_reports, figures = _load_mocks()
    merged = {r["pubmed_id"]: r for r in merge_records(case_reports, figures)}
    record = merged["11111111"]
    assert record["case_report"] is not None
    assert len(record["figures"]) == 2


def test_merge_preserves_same_pmid_for_multiple_diseases():
    reports = [
        {"pubmed_id": 123, "disease": "SLE", "title": "A"},
        {"pubmed_id": "123", "disease": "Sjogrens", "title": "B"},
    ]
    figures = [{"pubmed_id": "123", "disease": "SLE", "figure_id": "f1"}]
    merged = merge_records(reports, figures)
    assert {(row["disease"], row["pubmed_id"]) for row in merged} == {
        ("SLE", "123"),
        ("Sjogrens", "123"),
    }
    by_disease = {row["disease"]: row for row in merged}
    assert len(by_disease["SLE"]["figures"]) == 1
    assert by_disease["Sjogrens"]["figures"] == []


def test_unscoped_figure_is_not_duplicated_across_ambiguous_diseases():
    reports = [
        {"pubmed_id": "123", "disease": "SLE"},
        {"pubmed_id": "123", "disease": "MCTD"},
    ]
    figure = {"pubmed_id": "123", "disease": "", "figure_index": 1}
    merged = merge_records(reports, [figure])
    scoped = [row for row in merged if row["disease"]]
    unscoped = [row for row in merged if not row["disease"]]
    assert all(row["figures"] == [] for row in scoped)
    assert len(unscoped) == 1
    assert unscoped[0]["figures"] == [figure]


def test_real_figure_metadata_maps_to_schema():
    flat = flatten_figure_metadata([{
        "pubmed_id": "42",
        "disease": "SLE",
        "pmc_id": "PMC42",
        "figures": [{
            "label": "Figure 3",
            "img_ref": "image-3.jpg",
            "caption": "A scan",
            "figure_type": "imaging",
        }],
    }])
    validated = ExtractedFigure.model_validate(flat[0])
    assert validated.figure_index == 3
    assert validated.file_path == "image-3.jpg"
    assert validated.source_pdf == "PMC42"
