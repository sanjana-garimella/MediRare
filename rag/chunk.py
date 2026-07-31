#!/usr/bin/env python3
"""
Chunk case-report abstracts for hybrid RAG indexing.

Usage:
    python3 rag/chunk.py \
        --jsonl data/nlp/processed/sle_case_reports.jsonl \
                data/nlp/processed/sjogrens_case_reports.jsonl \
                data/nlp/processed/mctd_case_reports.jsonl \
        --out data/rag/chunks.jsonl

Rules (see .agents/rules/agent.md):
- Sentence-boundary splits, ~256 tokens target, 32-token overlap
- Context prefix: "This chunk from [disease] case report [PMID] describes [topic]."
- chunk_id = {disease}_{pmid}_c{n} (traceable to PubMed)
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path


def approx_tokens(text: str) -> int:
    return max(1, len(text.split()))


def sentence_split(text: str) -> list[str]:
    """Split prose without breaking common abbreviations or decimal numbers."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    protected = text
    dot = "\u2024"
    for abbreviation in (
        "e.g.", "i.e.", "Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "Fig.",
        "vs.", "et al.", "No.",
    ):
        protected = re.sub(
            re.escape(abbreviation),
            abbreviation.replace(".", dot),
            protected,
            flags=re.I,
        )
    protected = re.sub(r"(?<=\d)\.(?=\d)", dot, protected)
    parts = re.split(r"(?<=[.!?])(?:[\"')\]]*)\s+", protected)
    return [p.replace(dot, ".").strip() for p in parts if p.strip()]


def topic_hint(abstract: str) -> str:
    # First ~8 words of abstract as weak topic
    words = abstract.split()[:8]
    return " ".join(words).rstrip(".,;:") if words else "clinical case details"


def _normalized(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return re.sub(r"[^a-z0-9]+", " ", text.encode("ascii", "ignore").decode().lower()).strip()


def _sequence_hints(body: str, sequences: list[str]) -> list[str]:
    """Attach document annotations only where their entity is literally present."""
    normalized_body = f" {_normalized(body)} "
    return [
        entity
        for entity in sequences
        if (needle := _normalized(entity)) and f" {needle} " in normalized_body
    ]


def chunk_abstract(
    *,
    disease: str,
    pubmed_id: str,
    abstract: str,
    sequences: list[str] | None = None,
    review_status: str = "unreviewed",
    target_tokens: int = 256,
    overlap_tokens: int = 32,
) -> list[dict]:
    sequences = sequences or []
    sents = sentence_split(abstract)
    if not sents:
        return []

    disease_slug = re.sub(r"[^a-z0-9]+", "", disease.lower()) or "disease"
    topic = topic_hint(abstract)
    prefix = (
        f"This chunk from {disease} case report {pubmed_id} describes {topic}."
    )

    # Build windows by sentence accumulation
    windows: list[str] = []
    i = 0
    while i < len(sents):
        buf: list[str] = []
        tok = 0
        j = i
        while j < len(sents) and tok < target_tokens:
            buf.append(sents[j])
            tok += approx_tokens(sents[j])
            j += 1
        if not buf:
            break
        windows.append(" ".join(buf))
        if j >= len(sents):
            break
        # Overlap: step back by ~overlap_tokens worth of sentences
        back_tok = 0
        k = j - 1
        while k > i and back_tok < overlap_tokens:
            back_tok += approx_tokens(sents[k])
            k -= 1
        next_i = max(i + 1, k + 1)
        if next_i <= i:
            next_i = i + 1
        i = next_i

    chunks = []
    for n, body in enumerate(windows, start=1):
        hints = _sequence_hints(body, sequences)
        chunks.append(
            {
                "chunk_id": f"{disease_slug}_{pubmed_id}_c{n}",
                "pubmed_id": pubmed_id,
                "disease": disease,
                "text": body,
                "body": body,
                "context": prefix,
                "misdiagnosis_sequence": hints,
                "review_status": review_status,
            }
        )
    return chunks


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jsonl", nargs="+", required=True, help="Processed case-report JSONL files")
    ap.add_argument("--out", default="data/rag/chunks.jsonl")
    ap.add_argument("--target-tokens", type=int, default=256)
    ap.add_argument("--overlap-tokens", type=int, default=32)
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    all_chunks: list[dict] = []
    for path_s in args.jsonl:
        path = Path(path_s)
        rows = load_jsonl(path)
        n_docs = 0
        for r in rows:
            abstract = (r.get("abstract") or "").strip()
            if len(abstract) < 30:
                continue
            n_docs += 1
            all_chunks.extend(
                chunk_abstract(
                    disease=r.get("disease") or path.stem,
                    pubmed_id=str(r["pubmed_id"]),
                    abstract=abstract,
                    sequences=r.get("misdiagnosis_sequence") or [],
                    review_status=(
                        "reviewed"
                        if r.get("misdiagnosis_provenance") == "reviewed"
                        and r.get("misdiagnosis_review_status") == "reviewed"
                        else "unreviewed"
                    ),
                    target_tokens=args.target_tokens,
                    overlap_tokens=args.overlap_tokens,
                )
            )
        print(f"{path.name}: {n_docs} abstracts → running total {len(all_chunks)} chunks")

    with out.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=True) + "\n")
    print(f"Wrote {out} ({len(all_chunks)} chunks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
