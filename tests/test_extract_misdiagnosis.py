from __future__ import annotations

from nlp.extract_misdiagnosis import _clean_entity, _filter_target, _gazetteer_match, extract


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


def test_filter_target_word_boundary_regression():
    # "myositis" must not match inside "polymyositis"/"dermatomyositis" — those
    # are real wrong-diagnosis mimics of SLE, not the (undergrad-scope)
    # Inflammatory Myositis target itself.
    assert _filter_target("polymyositis", "SLE") is False
    assert _filter_target("dermatomyositis", "SLE") is False
    assert _filter_target("myositis", "SLE") is True


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
