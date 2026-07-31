from __future__ import annotations

from nlp.eval_extractor import entity_metrics, normalize_entity


def test_normalized_entity_metrics_use_truth_entities():
    predictions = {"1": ["TB"], "2": ["rheumatoid arthritis"]}
    truth = {
        "1": {"has_misdiagnosis": 1, "entities": ["tuberculosis"]},
        "2": {"has_misdiagnosis": 1, "entities": ["multiple sclerosis"]},
    }
    exact = entity_metrics(predictions, truth, ["1", "2"], normalized=False)
    normalized = entity_metrics(predictions, truth, ["1", "2"], normalized=True)
    assert exact["tp"] == 0
    assert normalized["tp"] == 1
    assert normalized["fp"] == 1
    assert normalized["fn"] == 1
    assert normalize_entity("Sjögren’s syndrome") == "sjogrens syndrome"
