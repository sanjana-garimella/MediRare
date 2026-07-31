"""Tests for rag/chunk.py."""
from __future__ import annotations

from rag.chunk import approx_tokens, chunk_abstract, sentence_split


def test_sentence_split_basic():
    sents = sentence_split("First sentence. Second one! Third?")
    assert sents == ["First sentence.", "Second one!", "Third?"]


def test_chunk_id_traceable():
    abstract = (
        "She was initially diagnosed with tuberculosis. "
        "Later SLE was confirmed after antibody testing. "
        "Pleural effusion resolved with immunosuppression. "
    ) * 8
    chunks = chunk_abstract(
        disease="SLE",
        pubmed_id="42367351",
        abstract=abstract,
        sequences=["tuberculosis"],
        target_tokens=40,
        overlap_tokens=8,
    )
    assert chunks
    assert chunks[0]["chunk_id"] == "sle_42367351_c1"
    assert chunks[0]["text"] == chunks[0]["body"]
    assert chunks[0]["context"].startswith(
        "This chunk from SLE case report 42367351 describes"
    )
    assert approx_tokens(chunks[0]["text"]) >= 10
    assert chunks[0]["misdiagnosis_sequence"] == ["tuberculosis"]


def test_empty_abstract():
    assert chunk_abstract(disease="SLE", pubmed_id="1", abstract="") == []


def test_sequence_hint_only_attached_to_mentioning_window():
    abstract = (
        "Tuberculosis was the initial diagnosis. "
        "A later paragraph discusses antibody testing without naming the mimic. "
        "Further follow-up details were clinically uneventful."
    )
    chunks = chunk_abstract(
        disease="SLE",
        pubmed_id="1",
        abstract=abstract,
        sequences=["tuberculosis"],
        target_tokens=5,
        overlap_tokens=0,
    )
    assert chunks[0]["misdiagnosis_sequence"] == ["tuberculosis"]
    assert any(not chunk["misdiagnosis_sequence"] for chunk in chunks[1:])


def test_sentence_split_preserves_abbreviations_and_decimals():
    assert sentence_split("Dr. Lee measured 12.5 mg. It improved.") == [
        "Dr. Lee measured 12.5 mg.",
        "It improved.",
    ]
