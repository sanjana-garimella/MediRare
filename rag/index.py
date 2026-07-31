#!/usr/bin/env python3
"""
Build hybrid indexes from data/rag/chunks.jsonl.

Usage:
    python3 rag/index.py --chunks data/rag/chunks.jsonl --out data/rag/index

Writes an immutable generation under ``data/rag/index/generations/`` and
atomically publishes its id through ``data/rag/index/CURRENT``. Each generation
contains LanceDB, BM25, metadata, and a manifest.

Default embed model: sentence-transformers/all-MiniLM-L6-v2 (cached locally).
Prefer BAAI/bge-m3 when disk allows: --embed-model BAAI/bge-m3
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import shutil
import uuid
from pathlib import Path

import bm25s
import lancedb
import numpy as np


def load_chunks(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def embed_texts(model_name: str, texts: list[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    return np.asarray(vecs, dtype=np.float32)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chunks", default="data/rag/chunks.jsonl")
    ap.add_argument("--out", default="data/rag/index")
    ap.add_argument(
        "--embed-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="SentenceTransformer model (default MiniLM; use BAAI/bge-m3 when possible)",
    )
    ap.add_argument(
        "--keep",
        type=int,
        default=3,
        help="Retain only the N most recently published generations (default 3; "
        "0 disables pruning). Never deletes the generation just published.",
    )
    args = ap.parse_args()

    chunks = load_chunks(Path(args.chunks))
    if not chunks:
        print("ERROR: no chunks")
        return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    generation_id = uuid.uuid4().hex
    generation = out / "generations" / generation_id
    lance_dir = generation / "lancedb"
    bm25_dir = generation / "bm25"
    lance_dir.mkdir(parents=True, exist_ok=True)
    bm25_dir.mkdir(parents=True, exist_ok=True)

    texts = [c["text"] for c in chunks]
    ids = [c["chunk_id"] for c in chunks]
    print(f"Embedding {len(texts)} chunks with {args.embed_model} ...")
    vectors = embed_texts(args.embed_model, texts)

    # LanceDB dense store
    db = lancedb.connect(str(lance_dir))
    rows = []
    for c, vec in zip(chunks, vectors):
        rows.append(
            {
                "chunk_id": c["chunk_id"],
                "pubmed_id": c["pubmed_id"],
                "disease": c["disease"],
                "text": c["text"],
                "body": c.get("body") or c["text"],
                "context": c.get("context") or "",
                "misdiagnosis_sequence": json.dumps(c.get("misdiagnosis_sequence") or []),
                "review_status": c.get("review_status") or "unreviewed",
                "vector": vec.tolist(),
            }
        )
    table_name = "chunks"
    db.create_table(table_name, data=rows)
    print(f"LanceDB table '{table_name}': {len(rows)} rows → {lance_dir}")

    # BM25 sparse index (tokenized consistently for documents and queries)
    corpus_tokens = bm25s.tokenize(texts, stopwords="en")
    retriever = bm25s.BM25()
    retriever.index(corpus_tokens)
    retriever.save(str(bm25_dir / "index"))
    with (bm25_dir / "chunk_ids.pkl").open("wb") as f:
        pickle.dump(ids, f)
    with (bm25_dir / "texts.pkl").open("wb") as f:
        pickle.dump(texts, f)
    metadata = {
        c["chunk_id"]: {
            "pubmed_id": c.get("pubmed_id", ""),
            "disease": c.get("disease", ""),
            "text": c.get("text", ""),
            "body": c.get("body") or c.get("text", ""),
            "context": c.get("context", ""),
            "misdiagnosis_sequence": c.get("misdiagnosis_sequence") or [],
            "review_status": c.get("review_status") or "unreviewed",
        }
        for c in chunks
    }
    with (bm25_dir / "metadata.pkl").open("wb") as f:
        pickle.dump(metadata, f)
    print(f"BM25 index → {bm25_dir}")

    meta = {
        "generation_id": generation_id,
        "n_chunks": len(chunks),
        "embed_model": args.embed_model,
        "vector_dim": int(vectors.shape[1]),
        "chunks_path": str(Path(args.chunks)),
    }
    (generation / "meta.json").write_text(json.dumps(meta, indent=2))

    # Validate the complete generation before publishing it. Readers resolve
    # CURRENT once and therefore see either the old or the new generation,
    # never a mixed LanceDB/BM25 set.
    check_db = lancedb.connect(str(lance_dir))
    check_table = check_db.open_table("chunks")
    if check_table.count_rows() != len(chunks) or len(ids) != len(chunks):
        raise RuntimeError("index generation validation failed: row counts differ")
    pointer_tmp = out / f".CURRENT.{generation_id}.tmp"
    pointer_tmp.write_text(generation_id + "\n", encoding="utf-8")
    os.replace(pointer_tmp, out / "CURRENT")
    print(f"Published generation {generation_id} via {out / 'CURRENT'}")

    if args.keep > 0:
        _prune_old_generations(out / "generations", keep=args.keep, current=generation_id)
    return 0


def _prune_old_generations(generations_dir: Path, *, keep: int, current: str) -> None:
    """Delete all but the `keep` most recently modified generations.

    Best-effort: a generation directory that fails to delete (e.g. a
    concurrent reader still has it memory-mapped on some platforms) is
    skipped rather than raising, since stale generations are a disk-usage
    concern, not a correctness one — readers always resolve via CURRENT.
    """
    if not generations_dir.exists():
        return
    gens = [p for p in generations_dir.iterdir() if p.is_dir()]
    gens.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    keep_ids = {current} | {p.name for p in gens[:keep]}
    for p in gens:
        if p.name in keep_ids:
            continue
        try:
            shutil.rmtree(p)
            print(f"Pruned old generation {p.name}")
        except OSError as exc:  # noqa: BLE001 - best-effort cleanup
            print(f"WARNING: could not prune generation {p.name}: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
