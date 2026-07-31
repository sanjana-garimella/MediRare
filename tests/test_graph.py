"""Tests for knowledge graph builder."""
from __future__ import annotations

from graph.build_graph import build_graph, most_common_wrong_dx, top_confusion_partners


def test_build_graph_edges_and_pmids():
    records = [
        {"pubmed_id": "1", "disease": "SLE", "misdiagnosis_sequence": ["tuberculosis", "lymphoma"]},
        {"pubmed_id": "2", "disease": "SLE", "misdiagnosis_sequence": ["tuberculosis"]},
        {"pubmed_id": "3", "disease": "MCTD", "misdiagnosis_sequence": ["rheumatoid arthritis"]},
    ]
    g = build_graph(records, include_unreviewed=True)
    assert g.number_of_edges() >= 3
    partners = top_confusion_partners(g, "SLE")
    assert partners[0][0] == "tuberculosis"
    assert partners[0][1] == 2
    common = most_common_wrong_dx(g)
    assert common[0][0] == "tuberculosis"


def test_default_graph_quarantines_unreviewed_candidates():
    record = {
        "pubmed_id": "1",
        "disease": "SLE",
        "misdiagnosis_sequence": ["tuberculosis"],
        "misdiagnosis_provenance": "high",
    }
    assert build_graph([record]).number_of_edges() == 0
    candidate = build_graph([record], include_unreviewed=True)
    assert candidate.has_edge("sle", "tuberculosis")
    assert candidate["sle"]["tuberculosis"]["review_status"] == "unreviewed_candidate"


def test_reviewed_graph_requires_explicit_direction_and_canonicalizes_self_edges():
    base = {
        "pubmed_id": "2",
        "disease": "SLE",
        "misdiagnosis_sequence": ["systemic lupus erythematosus", "KFD"],
        "misdiagnosis_provenance": "reviewed",
        "misdiagnosis_review_status": "reviewed",
    }
    assert build_graph([base]).number_of_edges() == 0
    base["misdiagnosis_relation"] = "target_was_misdiagnosed_as_entity"
    g = build_graph([base])
    assert not g.has_edge("sle", "sle")
    assert g.has_edge("sle", "kikuchi-fujimoto disease")
