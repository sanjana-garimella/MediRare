"""Tests for LLM-assist entity grounding (no Ollama required)."""
from __future__ import annotations

from nlp.llm_assist import ground_entities, parse_entity_list


def test_grounds_same_sentence_relation():
    abstract = "The patient was initially treated for tuberculosis before SLE was confirmed."
    assert ground_entities(["tuberculosis"], abstract) == ["tuberculosis"]


def test_suppresses_same_sentence_negation():
    abstract = (
        "The patient was treated for tuberculosis, but this was excluded "
        "and lupus was confirmed."
    )
    assert ground_entities(["tuberculosis"], abstract) == []


def test_suppresses_cross_sentence_negation_in_next_sentence():
    abstract = (
        "The patient was initially treated for tuberculosis. "
        "This was later excluded and the diagnosis was revised to SLE."
    )
    assert ground_entities(["tuberculosis"], abstract) == []


def test_does_not_suppress_negation_two_sentences_later():
    # Negation outside the mention+next-sentence window should not suppress;
    # this documents the deliberate scope of the fix, not a total fix.
    abstract = (
        "The patient was initially treated for tuberculosis. "
        "A chest CT was performed and pulmonology was consulted. "
        "This was later excluded and the diagnosis was revised to SLE."
    )
    assert ground_entities(["tuberculosis"], abstract) == ["tuberculosis"]


def test_acronym_only_grounds_when_present_as_uppercase_in_source():
    # "ten" (lowercase, common English word) must not match via a
    # coincidental acronym derived from "toxic epidermal necrolysis" unless
    # the abstract actually uses the acronym TEN.
    abstract = (
        "Ten patients were treated for a rash before the diagnosis of SLE "
        "was made."
    )
    assert ground_entities(["toxic epidermal necrolysis"], abstract) == []


def test_acronym_grounds_when_actually_used_in_source():
    abstract = (
        "The patient was initially diagnosed with TEN before SLE serologies "
        "returned positive."
    )
    assert ground_entities(["toxic epidermal necrolysis"], abstract) == [
        "toxic epidermal necrolysis"
    ]


def test_vague_entity_filtered():
    abstract = "The patient was treated for an infection before SLE was confirmed."
    assert ground_entities(["infection"], abstract) == []


def test_parse_entity_list_rejects_non_json():
    assert parse_entity_list("I cannot help with that.") == []


def test_parse_entity_list_dedupes_and_filters_vague():
    out = parse_entity_list('["tuberculosis", "infection", "tuberculosis", "lymphoma"]')
    assert out == ["tuberculosis", "lymphoma"]
