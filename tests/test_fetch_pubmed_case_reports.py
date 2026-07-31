"""Tests for PubMed fetch helpers (no network / paperscraper required)."""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import patch

import pandas as pd

# paperscraper is an optional runtime dep for live PubMed fetches; stub it
# so unit tests can import the module without installing it.
if "paperscraper" not in sys.modules:
    paperscraper = ModuleType("paperscraper")
    pubmed = ModuleType("paperscraper.pubmed")
    pubmed.get_pubmed_papers = lambda *a, **k: None  # type: ignore[attr-defined]
    paperscraper.pubmed = pubmed  # type: ignore[attr-defined]
    sys.modules["paperscraper"] = paperscraper
    sys.modules["paperscraper.pubmed"] = pubmed

from nlp.fetch_pubmed_case_reports import _clean_str, fetch_case_reports  # noqa: E402


def test_clean_str_treats_none_and_nan_as_empty():
    assert _clean_str(None) == ""
    assert _clean_str(float("nan")) == ""
    assert _clean_str("  hello  ") == "hello"


def test_clean_str_preserves_zero_like_values():
    # Must not collapse ordinary non-NaN values the way `value or ""` would.
    assert _clean_str(0) == "0"
    assert _clean_str(False) == "False"


def test_fetch_case_reports_skips_nan_pubmed_id_and_dedupes():
    df = pd.DataFrame(
        [
            {"pubmed_id": "111", "title": "A", "abstract": "abs A", "xml": "<a/>"},
            {"pubmed_id": float("nan"), "title": "B", "abstract": "abs B", "xml": "<b/>"},
            {"pubmed_id": "111", "title": "A-dup", "abstract": "dup", "xml": "<a2/>"},
            {"pubmed_id": "222", "title": float("nan"), "abstract": None, "xml": "<c/>"},
        ]
    )
    with patch("nlp.fetch_pubmed_case_reports.get_pubmed_papers", return_value=df):
        rows, xmls = fetch_case_reports("unused", retmax=10, disease="SLE")
    assert [r.pubmed_id for r in rows] == ["111", "222"]
    assert rows[0].title == "A"
    assert rows[1].title == ""
    assert rows[1].abstract == ""
    # xml field here is a string, not ET.Element, so nothing is archived
    assert xmls == []
