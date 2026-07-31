from __future__ import annotations

import json

from nlp.extract_misdiagnosis import (
    _clean_entity,
    _filter_target,
    _gazetteer_match,
    _ground_entity,
    _target_disease_excluded,
    _target_disease_unconfirmed,
    atomic_write_jsonl,
    extract,
    process_records,
)
from nlp.llm_assist import ground_entities


def test_extract_high_confidence_passive_pattern():
    result = extract("She was initially diagnosed with fibromyalgia before SLE was confirmed.", "SLE")
    assert result == (["fibromyalgia"], "high")


def test_extract_high_confidence_masquerade_pattern():
    result = extract("Dermatomyositis masquerading as SLE was later reclassified.", "SLE")
    assert result == (["dermatomyositis"], "high")


def test_extract_gazetteer_fallback():
    abstract = "This case highlights how NMOSD can be misdiagnosed in clinical practice today for this patient."
    result = extract(abstract, "SLE")
    assert result == (["nmosd"], "gazetteer")


def test_extract_signal_only_no_entity():
    abstract = "This case highlights how misdiagnosis occurred in clinical practice today for this individual overall."
    result = extract(abstract, "SLE")
    assert result == ([], "signal_only")


def test_extract_none_no_signal():
    abstract = "A completely normal case report with no relevant clinical signal words present anywhere here."
    result = extract(abstract, "SLE")
    assert result == ([], "none")


def test_extract_none_abstract_too_short():
    assert extract("Short.", "SLE") == ([], "none")


def test_filter_target_does_not_exclude_other_diseases():
    assert _filter_target("polymyositis", "SLE") is False
    assert _filter_target("dermatomyositis", "SLE") is False
    assert _filter_target("myositis", "SLE") is False
    assert _filter_target("Sjögren syndrome", "MCTD") is False


def test_extract_polymyositis_not_excluded_as_target():
    abstract = "She was initially diagnosed with polymyositis before SLE was confirmed."
    result = extract(abstract, "SLE")
    assert result == (["polymyositis"], "high")


def test_clean_entity_noise_start_rejects_bare_article():
    assert _clean_entity("an infection") is None


def test_clean_entity_noise_start_allows_real_word_starting_with_an():
    assert _clean_entity("anorexia nervosa") == "anorexia nervosa"


def test_clean_entity_rejects_person_descriptor():
    assert _clean_entity("the female patient who") is None


def test_extract_trailing_parenthetical_stop_regression():
    # The parenthetical gloss must not be swallowed into the captured entity.
    abstract = "She was misdiagnosed with NMOSD (a demyelinating disorder) before SLE was confirmed."
    entities, level = extract(abstract, "SLE")
    assert entities == ["nmosd"]
    assert level == "high"


def test_gazetteer_match_requires_same_sentence_cooccurrence():
    same_sentence = (
        "Physicians considered lymphoma as the cause after the patient was "
        "misdiagnosed for several months."
    )
    different_sentences = (
        "The patient was misdiagnosed for several months. Physicians later "
        "considered lymphoma as an unrelated finding."
    )
    assert _gazetteer_match(same_sentence, "SLE") == ["lymphoma"]
    assert _gazetteer_match(different_sentences, "SLE") == []


def test_extract_stops_entity_at_common_preposition():
    entities, level = extract(
        "She was initially diagnosed with fibromyalgia in adolescence before lupus.",
        "SLE",
    )
    assert (entities, level) == (["fibromyalgia"], "high")


def test_extract_keeps_known_disease_name_with_preposition():
    entities, level = extract(
        "She was initially diagnosed with pyrexia of unknown origin before lupus.",
        "SLE",
    )
    assert (entities, level) == (["pyrexia of unknown origin"], "high")


def test_delayed_diagnosis_is_signal_only_not_wrong_entity():
    abstract = "There was a delayed diagnosis of SLE despite years of symptoms and repeated specialist review."
    assert extract(abstract, "SLE") == ([], "signal_only")


def test_bare_presumed_does_not_extract_prose():
    abstract = "The presumed reason for fatigue was discussed during a long clinical evaluation of this patient."
    assert extract(abstract, "SLE") == ([], "signal_only")


def test_unicode_and_alias_self_target_filtering():
    assert _filter_target("Sjögren’s syndrome", "Sjogrens")
    assert _filter_target("neuropsychiatric SLE", "SLE")
    assert _filter_target("NPSLE", "SLE")


def test_target_disease_excluded_detects_own_disease_ruled_out():
    # PMID 42112145 pattern: SLE is the record's disease field, but the
    # abstract's real diagnosis is IgG4-related disease and SLE was one of
    # several differentials explicitly excluded.
    abstract = (
        "Follow-up computed tomography excluded pancreatic mass. After "
        "excluding systemic lupus erythematosus and plasma cell dyscrasia, "
        "IgG4-related disease was confirmed."
    )
    assert _target_disease_excluded(abstract, "SLE") is True


def test_target_disease_excluded_false_for_unrelated_exclusion():
    abstract = (
        "Tuberculosis was excluded on culture. The patient was later "
        "diagnosed with systemic lupus erythematosus."
    )
    assert _target_disease_excluded(abstract, "SLE") is False


def test_target_disease_unconfirmed_detects_generic_list_only_mention():
    # PMID 41939103 pattern: a Sjögren's case report that name-drops SLE
    # only inside a textbook differential list, never as this patient's
    # actual diagnosis.
    abstract = (
        "Common causes of pleural effusion in an elderly patient include "
        "heart failure, malignancy, and autoimmune diseases such as "
        "systemic lupus erythematosus or rheumatoid arthritis. Primary "
        "Sjögren's syndrome was ultimately confirmed."
    )
    assert _target_disease_unconfirmed(abstract, "SLE") is True


def test_target_disease_unconfirmed_false_when_affirmed():
    abstract = "The patient was later diagnosed with systemic lupus erythematosus."
    assert _target_disease_unconfirmed(abstract, "SLE") is False


def test_ground_entity_requires_relation_signal_not_just_list_mention():
    abstract = (
        "Common causes of pleural effusion include heart failure, "
        "malignancy, and tuberculosis."
    )
    assert _ground_entity("tuberculosis", abstract) is False


def test_ground_entity_accepts_mimic_relation_without_exclusion():
    abstract = "Respiratory symptoms may mimic community-acquired pneumonia in this population."
    assert _ground_entity("pneumonia", abstract) is True


def test_ground_entity_rejects_entity_excluded_in_next_sentence():
    abstract = (
        "The patient was initially treated for tuberculosis. This was "
        "later excluded and the diagnosis was revised to SLE."
    )
    assert _ground_entity("tuberculosis", abstract) is False


def test_ground_entity_rejects_ungrounded_garbled_entity():
    abstract = "The biopsy was inconsistent with iMCD, favouring a reactive process."
    assert _ground_entity("idmcd", abstract) is False


def test_legacy_sequence_is_preserved_only_when_fresh_extraction_has_no_evidence():
    # Fresh regex patterns don't fire on "thought related to" (only the
    # exact "thought to have/be X" phrasing), so this exercises the
    # preserve-prior path — but the entity must still be literally present
    # with a relation-signal word and no exclusion nearby to survive.
    records = [{
        "pubmed_id": "1",
        "disease": "SLE",
        "abstract": (
            "The patient's presentation was thought related to polymyositis, "
            "and this was clarified only after extensive rheumatology workup."
        ),
        "misdiagnosis_sequence": ["polymyositis"],
    }]
    updated, stats, _, _ = process_records(records)
    assert updated[0]["misdiagnosis_sequence"] == ["polymyositis"]
    assert updated[0]["misdiagnosis_provenance"] == "legacy_unreviewed"
    assert stats["preserved"] == 1


def test_preserved_legacy_entity_dropped_if_not_grounded_in_abstract():
    """A stale/legacy entity that isn't literally supported by the abstract
    (garbled text, or only ever discussed as an excluded differential) must
    not survive forever just because no fresh pattern replaces it — see
    PMID 41996261 in docs/research_references.md."""
    records = [{
        "pubmed_id": "1",
        "disease": "MCTD",
        "abstract": (
            "The lymph node biopsy findings were inconsistent with iMCD, "
            "favouring a reactive process in the context of the patient's "
            "known mixed connective tissue disease."
        ),
        "misdiagnosis_sequence": ["idmcd"],
    }]
    updated, _, _, _ = process_records(records)
    assert updated[0]["misdiagnosis_sequence"] == []


def test_fresh_high_confidence_replaces_unreviewed_legacy_sequence():
    records = [{
        "pubmed_id": "1",
        "disease": "SLE",
        "abstract": "She was initially diagnosed with fibromyalgia before systemic lupus erythematosus was confirmed.",
        "misdiagnosis_sequence": ["optic neuritis in the right eye at another hospital"],
    }]
    updated, _, _, _ = process_records(records)
    assert updated[0]["misdiagnosis_sequence"] == ["fibromyalgia"]
    assert updated[0]["misdiagnosis_provenance"] == "high"


def test_unchanged_extraction_preserves_timestamp():
    records = [{
        "pubmed_id": "1",
        "disease": "SLE",
        "abstract": "She was initially diagnosed with fibromyalgia before systemic lupus erythematosus was confirmed.",
        "misdiagnosis_sequence": ["fibromyalgia"],
        "misdiagnosis_provenance": "high",
        "misdiagnosis_extracted_at": "2025-01-01T00:00:00+00:00",
    }]
    updated, _, _, _ = process_records(records)
    assert updated[0]["misdiagnosis_extracted_at"] == "2025-01-01T00:00:00+00:00"


def test_self_target_is_removed_even_from_preserved_sequence():
    records = [{
        "pubmed_id": "2",
        "disease": "Sjogrens",
        "abstract": (
            "Her symptoms were thought related to multiple sclerosis and "
            "primary Sjögren’s syndrome before further workup clarified the "
            "diagnosis."
        ),
        "misdiagnosis_sequence": ["primary Sjögren’s syndrome", "multiple sclerosis"],
    }]
    updated, _, _, _ = process_records(records)
    assert updated[0]["misdiagnosis_sequence"] == ["multiple sclerosis"]


def test_other_target_disease_is_preserved_as_wrong_diagnosis():
    records = [{
        "pubmed_id": "3",
        "disease": "MCTD",
        "abstract": (
            "The patient's overlapping features were thought related to "
            "Sjögren syndrome and systemic sclerosis before further serology "
            "suggested mixed connective tissue disease."
        ),
        "misdiagnosis_sequence": ["Sjögren syndrome", "systemic sclerosis"],
    }]
    updated, stats, _, _ = process_records(records)
    assert updated[0]["misdiagnosis_sequence"] == [
        "Sjögren syndrome",
        "systemic sclerosis",
    ]
    assert stats["preserved"] == 1


def test_atomic_write_replaces_only_after_complete_temp(monkeypatch, tmp_path):
    path = tmp_path / "records.jsonl"
    path.write_text('{"old": true}\n', encoding="utf-8")
    seen = {}
    real_replace = __import__("os").replace

    def capture_replace(source, destination):
        seen["rows"] = [
            json.loads(line)
            for line in source.read_text(encoding="utf-8").splitlines()
        ]
        assert destination == path
        real_replace(source, destination)

    monkeypatch.setattr("nlp.extract_misdiagnosis.os.replace", capture_replace)
    atomic_write_jsonl(path, [{"new": 1}, {"new": 2}])
    assert seen["rows"] == [{"new": 1}, {"new": 2}]
    assert path.read_text(encoding="utf-8") == '{"new": 1}\n{"new": 2}\n'


def test_llm_entities_must_be_named_and_grounded():
    abstract = "The patient was treated for rheumatoid arthritis before MCTD."
    assert ground_entities(
        ["rheumatoid arthritis", "infection", "multiple sclerosis"],
        abstract,
    ) == ["rheumatoid arthritis"]


def test_llm_grounding_accepts_acronym_but_rejects_excluded_mentions():
    assert ground_entities(
        ["rheumatoid arthritis"],
        "The patient was initially treated as RA before the final diagnosis.",
    ) == ["rheumatoid arthritis"]
    assert ground_entities(
        ["multiple sclerosis"],
        "Multiple sclerosis was excluded after imaging; the case was misdiagnosed.",
    ) == []


def test_vague_confused_with_capture_is_rejected():
    entities, level = extract(
        "The syndrome is easily confused with other diseases in routine clinical practice.",
        "SLE",
    )
    assert entities == []
    assert level == "signal_only"
