from __future__ import annotations

from pathlib import Path

from integration.merge import load_jsonl, merge_records


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
