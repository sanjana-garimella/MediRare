from __future__ import annotations

import numpy as np

import rag.retrieve as retrieval


class _Search:
    def limit(self, _count):
        return self

    def to_list(self):
        return [{"chunk_id": "dense", "text": "dense body", "vector": [0.0]}]


class _Table:
    def search(self, _vector):
        return _Search()


class _BM25:
    def retrieve(self, _tokens, k):
        assert k == 2
        return np.array([[0, 1]]), np.array([[2.0, 0.0]])


class _Model:
    def encode(self, _queries, normalize_embeddings):
        assert normalize_embeddings
        return np.array([[0.0]], dtype=np.float32)


def test_bm25_only_hit_keeps_metadata_and_zero_padding_is_filtered(monkeypatch):
    metadata = {
        "sparse": {
            "pubmed_id": "42",
            "disease": "SLE",
            "body": "sparse body",
            "context": "source context",
            "misdiagnosis_sequence": ["tuberculosis"],
        }
    }
    monkeypatch.setattr(
        retrieval,
        "load_index",
        lambda _path: (
            {"embed_model": "test"}, _Table(), _BM25(),
            ["sparse", "zero"], ["sparse body", "zero body"], metadata,
        ),
    )
    monkeypatch.setattr(retrieval, "load_model", lambda _name: _Model())
    monkeypatch.setattr(retrieval.bm25s, "tokenize", lambda *_args, **_kwargs: [[]])

    hits = retrieval.retrieve("query", retrieval.Path("unused"), candidates=2, top=10)
    by_id = {hit["chunk_id"]: hit for hit in hits}
    assert by_id["sparse"]["pubmed_id"] == "42"
    assert by_id["sparse"]["disease"] == "SLE"
    assert "zero" not in by_id


def test_legacy_prefixed_text_is_separated_for_grading():
    body, context = retrieval._body_and_context({
        "text": "This chunk from SLE case report 42 describes tuberculosis. Unrelated body."
    })
    assert body == "Unrelated body."
    assert context.endswith("describes tuberculosis.")


def test_rrf_counts_each_id_once_per_ranker():
    fused = dict(retrieval.rrf_fuse([["a", "a", "b"]]))
    assert fused["a"] == 1 / 61
    assert fused["b"] == 1 / 63


def test_generation_pointer_changes_cache_token(tmp_path):
    index = tmp_path / "index"
    first = index / "generations" / ("a" * 32)
    second = index / "generations" / ("b" * 32)
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (index / "CURRENT").write_text("a" * 32)
    assert retrieval._resolve_generation(index) == (first.resolve(), "a" * 32)
    (index / "CURRENT").write_text("b" * 32)
    assert retrieval._resolve_generation(index) == (second.resolve(), "b" * 32)
