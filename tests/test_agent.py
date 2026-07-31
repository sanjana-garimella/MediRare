"""Tests for agent citation validator (no Ollama required)."""
from __future__ import annotations

from pathlib import Path

import agent.ask as ask_module
from agent.ask import ask, grade_evidence, validate_answer


def test_validate_abstain():
    out = validate_answer("INSUFFICIENT_EVIDENCE", {"a_1_c1"})
    assert out["status"] == "abstained"


def test_validate_strips_invented():
    out = validate_answer(
        "TB was confused with SLE [sle_1_c1]. Extra claim [fake_id].",
        {"sle_1_c1"},
    )
    assert out["status"] == "answered"
    assert "sle_1_c1" in out["citations"]
    assert "fake_id" in out["stripped"]
    assert "[fake_id]" not in out["answer"]
    assert "Extra claim" not in out["answer"]


def test_validate_one_paragraph_drops_every_unsupported_sentence():
    out = validate_answer(
        "TB was the initial diagnosis [sle_1_c1]. "
        "The patient lived in Paris [fake_id]. "
        "Treatment lasted 12.5 months.",
        {"sle_1_c1"},
    )
    assert out["status"] == "answered"
    assert out["answer"] == "TB was the initial diagnosis [sle_1_c1]."
    assert "Paris" not in out["answer"]
    assert "12.5 months" not in out["answer"]


def test_validate_all_invented_becomes_abstain():
    out = validate_answer("Something [totally_fake].", {"sle_1_c1"})
    assert out["status"] == "abstained"


def test_validate_strips_unicode_bullet_variants():
    out = validate_answer("‣ Supported claim [c1]\n● Also supported [c1]", {"c1"})
    assert out["status"] == "answered"
    assert "‣" not in out["answer"]
    assert "●" not in out["answer"]


def test_validate_preserves_line_and_bullet_boundaries():
    out = validate_answer(
        "Supported [c1]\nUnsupported claim\n- Also supported [c1]\n- Unsupported bullet",
        {"c1"},
    )
    assert out["status"] == "answered"
    assert "Supported [c1]" in out["answer"]
    assert "Also supported [c1]" in out["answer"]
    assert "Unsupported" not in out["answer"]


def test_validate_rejects_mixed_and_detached_citations():
    mixed = validate_answer("Supported [c1]; fabricated [fake].", {"c1"})
    assert mixed["status"] == "answered"
    assert mixed["answer"] == "Supported [c1]"
    assert "fabricated" not in mixed["answer"]

    detached = validate_answer("Fabricated claim. [c1]", {"c1"})
    assert detached["status"] == "abstained"


def test_grade_evidence_overlap():
    chunks = [{"body": "tuberculosis pleural effusion in lupus patient"}]
    g = grade_evidence("TB pleural SLE", chunks)
    assert g > 0.5


def test_grade_evidence_ignores_context_boilerplate_and_uses_best_chunk():
    chunks = [
        {
            "context": "This chunk from SLE case report 1 describes tuberculosis.",
            "body": "An unrelated dermatology finding.",
            "text": "An unrelated dermatology finding.",
        },
        {"body": "Pleural tuberculosis was considered."},
    ]
    assert grade_evidence("tuberculosis pleural", chunks) == 1.0
    assert grade_evidence("docstring example query", chunks) == 0.0


def test_canonical_tokens_handles_typographic_apostrophe():
    from agent.ask import _canonical_tokens

    straight = _canonical_tokens("Sjögren's syndrome")
    curly = _canonical_tokens("Sjögren\u2019s syndrome")
    assert straight == curly == {"sjogren"}


def test_grade_evidence_handles_short_and_multiword_aliases_and_all_chunks():
    chunks = [{"body": "irrelevant"} for _ in range(10)]
    chunks.append({"body": "Mixed connective tissue disease with rheumatoid arthritis and TB."})
    assert grade_evidence("MCTD", chunks) == 1.0
    assert grade_evidence("RA", chunks) == 1.0
    assert grade_evidence("tuberculosis", chunks) == 1.0


def test_ask_reports_missing_index_as_structured_error(monkeypatch):
    monkeypatch.setattr(
        ask_module,
        "retrieve",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError("meta.json")),
    )
    result = ask("clinical question", index_dir=Path("missing"))
    assert result["status"] == "error"
    assert result["error"]["code"] == "retrieval_index_unavailable"


def test_ask_reports_both_ollama_failures(monkeypatch):
    chunks = [{"chunk_id": "c1", "body": "tuberculosis pleural", "text": "tuberculosis pleural"}]
    monkeypatch.setattr(ask_module, "retrieve", lambda *_args, **_kwargs: chunks)
    monkeypatch.setattr(
        ask_module,
        "ollama_chat",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("offline")),
    )
    result = ask(
        "tuberculosis pleural",
        index_dir=Path("unused"),
        allow_unreviewed=True,
    )
    assert result["status"] == "error"
    assert result["error"]["code"] == "ollama_unavailable"


def test_ask_keeps_best_crag_grade_when_later_hop_is_worse(monkeypatch):
    grades = iter([0.5, 0.1, 0.2])
    monkeypatch.setattr(
        ask_module,
        "retrieve",
        lambda *_args, **_kwargs: [{"chunk_id": "c1", "body": "body", "text": "body"}],
    )
    monkeypatch.setattr(ask_module, "grade_evidence", lambda *_args: next(grades))
    monkeypatch.setattr(ask_module, "rewrite_query", lambda query, _model: query + " refined")
    result = ask(
        "question",
        index_dir=Path("unused"),
        grade_threshold=0.9,
        allow_unreviewed=True,
    )
    assert result["status"] == "abstained"
    assert result["grade"] == 0.5


def test_ask_defaults_to_abstain_when_only_unreviewed_evidence_exists(monkeypatch):
    monkeypatch.setattr(
        ask_module,
        "retrieve",
        lambda *_args, **_kwargs: [{
            "chunk_id": "c1",
            "body": "tuberculosis",
            "text": "tuberculosis",
            "review_status": "unreviewed",
        }],
    )
    # Every hop is unreviewed here, so this must still abstain even though
    # the loop now tries all max_hops before giving up (see the recovery
    # test below for the case where a later hop *does* find evidence).
    monkeypatch.setattr(ask_module, "rewrite_query", lambda query, _model: query)
    result = ask("tuberculosis", index_dir=Path("unused"))
    assert result["status"] == "abstained"
    assert result["evidence_status"] == "no_clinician_reviewed_evidence"


def test_ask_recovers_when_later_hop_finds_reviewed_evidence(monkeypatch):
    """A hop with zero reviewed chunks must not short-circuit the CRAG loop
    before a rewritten query gets a chance to find reviewed evidence."""
    calls = {"n": 0}

    def fake_retrieve(_query, *_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return [{
                "chunk_id": "c1",
                "body": "irrelevant unreviewed chunk",
                "text": "irrelevant unreviewed chunk",
                "review_status": "unreviewed",
            }]
        return [{
            "chunk_id": "c2",
            "body": "tuberculosis pleural effusion",
            "text": "tuberculosis pleural effusion",
            "review_status": "reviewed",
        }]

    monkeypatch.setattr(ask_module, "retrieve", fake_retrieve)
    monkeypatch.setattr(ask_module, "rewrite_query", lambda query, _model: query + " refined")
    monkeypatch.setattr(
        ask_module, "ollama_chat", lambda *_a, **_k: "TB pleural effusion [c2]."
    )
    result = ask(
        "tuberculosis pleural",
        index_dir=Path("unused"),
        grade_threshold=0.1,
    )
    assert calls["n"] >= 2
    assert result["status"] == "answered"
    assert "c2" in result["citations"]
