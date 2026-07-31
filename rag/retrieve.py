#!/usr/bin/env python3
"""
Hybrid retrieve: dense (LanceDB) + BM25 → RRF fuse → top-k.

Usage:
    python3 rag/retrieve.py --query "TB mimic pleural SLE" --index data/rag/index --top 20
"""
from __future__ import annotations

import argparse
import json
import pickle
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import bm25s
import lancedb
import numpy as np


def rrf_fuse(rank_lists: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = defaultdict(float)
    for ranks in rank_lists:
        seen: set[str] = set()
        for rank, cid in enumerate(ranks, start=1):
            if cid in seen:
                continue
            seen.add(cid)
            scores[cid] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def _body_and_context(hit: dict) -> tuple[str, str]:
    if hit.get("body"):
        return hit["body"], hit.get("context", "")
    text = hit.get("text", "")
    match = re.match(
        r"^(This chunk from .*? case report \S+ describes .*?\.)\s*(.*)$",
        text,
        flags=re.I | re.S,
    )
    if match:
        return match.group(2), match.group(1)
    return text, hit.get("context", "")


def _require(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"retrieval index artifact missing: {path}")
    return path


def _resolve_generation(index_dir: Path) -> tuple[Path, str]:
    index_dir = index_dir.resolve()
    pointer = index_dir / "CURRENT"
    if pointer.exists():
        generation_id = pointer.read_text(encoding="utf-8").strip()
        if not re.fullmatch(r"[a-f0-9]{32}", generation_id):
            raise ValueError(f"invalid retrieval generation id in {pointer}")
        generation = index_dir / "generations" / generation_id
        _require(generation)
        return generation, generation_id
    # Backward-compatible legacy index. The manifest fingerprint invalidates
    # the cache when an old-style rebuild replaces meta.json.
    meta_path = _require(index_dir / "meta.json")
    stat = meta_path.stat()
    return index_dir, f"legacy:{stat.st_mtime_ns}:{stat.st_size}"


@lru_cache(maxsize=8)
def _load_index_generation(index_dir: Path, generation_token: str):
    del generation_token  # cache-key only
    _require(index_dir / "meta.json")
    _require(index_dir / "lancedb")
    _require(index_dir / "bm25" / "index")
    _require(index_dir / "bm25" / "chunk_ids.pkl")
    _require(index_dir / "bm25" / "texts.pkl")
    meta = json.loads((index_dir / "meta.json").read_text())
    db = lancedb.connect(str(index_dir / "lancedb"))
    table = db.open_table("chunks")
    bm25 = bm25s.BM25.load(str(index_dir / "bm25" / "index"), load_corpus=False)
    with (index_dir / "bm25" / "chunk_ids.pkl").open("rb") as f:
        chunk_ids = pickle.load(f)
    with (index_dir / "bm25" / "texts.pkl").open("rb") as f:
        texts = pickle.load(f)
    metadata_path = index_dir / "bm25" / "metadata.pkl"
    if metadata_path.exists():
        with metadata_path.open("rb") as f:
            metadata = pickle.load(f)
    else:
        # Backward-compatible fallback for old indexes: recover metadata from LanceDB.
        metadata = {
            row["chunk_id"]: row
            for row in table.to_arrow().to_pylist()
        }
    return meta, table, bm25, chunk_ids, texts, metadata


def load_index(index_dir: Path):
    generation, token = _resolve_generation(index_dir)
    return _load_index_generation(generation, token)


@lru_cache(maxsize=4)
def load_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def retrieve(
    query: str,
    index_dir: Path,
    *,
    candidates: int = 150,
    top: int = 20,
) -> list[dict]:
    meta, table, bm25, chunk_ids, texts, metadata = load_index(index_dir)
    model = load_model(meta["embed_model"])
    qvec = model.encode([query], normalize_embeddings=True)[0].astype(np.float32)

    # Dense
    dense_hits = table.search(qvec.tolist()).limit(candidates).to_list()
    dense_ids = [h["chunk_id"] for h in dense_hits]
    by_id = {h["chunk_id"]: h for h in dense_hits}

    # BM25
    tokens = bm25s.tokenize([query], stopwords="en")
    n = min(candidates, len(chunk_ids))
    docs, scores = bm25.retrieve(tokens, k=n)
    # docs shape: (1, k) indices into corpus
    bm25_ids = []
    for idx, raw_score in zip(docs[0], scores[0]):
        if float(raw_score) <= 0:
            continue
        cid = chunk_ids[int(idx)]
        bm25_ids.append(cid)
        if cid not in by_id:
            by_id[cid] = {
                "chunk_id": cid,
                "text": texts[int(idx)],
                **metadata.get(cid, {}),
            }

    fused = rrf_fuse([dense_ids, bm25_ids])[:top]
    out = []
    for cid, score in fused:
        h = by_id[cid]
        body, context = _body_and_context(h)
        out.append(
            {
                "chunk_id": cid,
                "score": round(float(score), 6),
                "pubmed_id": h.get("pubmed_id", ""),
                "disease": h.get("disease", ""),
                "text": h.get("text", ""),
                "body": body,
                "context": context,
                "review_status": h.get("review_status") or "unreviewed",
                "misdiagnosis_sequence": json.loads(h.get("misdiagnosis_sequence") or "[]")
                if isinstance(h.get("misdiagnosis_sequence"), str)
                else (h.get("misdiagnosis_sequence") or []),
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--index", default="data/rag/index")
    ap.add_argument("--candidates", type=int, default=150)
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    hits = retrieve(args.query, Path(args.index), candidates=args.candidates, top=args.top)
    for i, h in enumerate(hits, 1):
        print(f"{i:2d}. {h['chunk_id']}  rrf={h['score']:.4f}  {h['text'][:120]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
