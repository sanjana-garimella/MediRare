---
name: agent-rules
description: Design rules for the MCP reasoning agent and RAG pipeline. Loaded when editing agent/, rag/, or vector store code.
globs:
  - "agent/**"
  - "rag/**"
  - "vector_store/**"
---
# MediRare RAG + Agent rules

## LLM serving (personal / $0 default)
- **Do not use vLLM.** It is for high-throughput GPU serving; this project is a personal prototype that may never deploy.
- Current implementation calls Ollama's `/api/chat` endpoint directly. An
  OpenAI-compatible client remains a future portability improvement.
- Preferred local runtime: **Ollama** (or LM Studio / llama.cpp server). Prefer free local open-weight models over paid APIs.
- Client stack: LangChain (or plain HTTP) + MCP. Do not hard-code a vendor SDK to one host.

### Locked models (1 primary + 1 backup + 1 medical side tool)
- Optimize for **cite / abstain / structured following**, not memorized medical knowledge. Retrieval is the knowledge.
- Evidence: a 10-item citation/abstention smoke test, not a statistically
  discriminating model benchmark — `experiments/llm_bakeoff/RESULTS.md`.
- **Primary:** `qwen2.5:14b` — final cited answerer (10/10)
- **Backup:** `llama3.1:8b` — light / low-RAM fallback only (10/10). Do not maintain a third active generator.
- **`--verify` consistency check:** `llama3.1:8b` (the backup model, reused because it's independent of the primary answerer). Not medical verification.
- Parked (not active): `meditron:7b` — tried as the `--verify` model (7/10 on the bake-off; failed abstains) and additionally found, via live testing against Ollama, to never return a parseable grade for the verify prompt at all (echoes the prompt / hallucinates unrelated content). Not used by any code path. `qwen3:32b` — if reused, must set `think: false`.
- Never use medical chat models as the final RAG answerer unless they beat the primary on the bake-off.
- Re-run `llm-bakeoff` before changing the locked set.

### Embeddings / rerank (separate from generator)
- Active dense model: `sentence-transformers/all-MiniLM-L6-v2`.
- Active ranking: dense + BM25 reciprocal-rank fusion to top 20.
- `bge-m3` and `bge-reranker-v2-m3` are future candidates requiring a
  retrieval benchmark; no cross-encoder reranker is active.

## Retrieval architecture
- Use **hybrid search**: dense embeddings (ChromaDB/LanceDB) + BM25 sparse index. Never dense-only.
- Fuse rankings with reciprocal rank fusion (RRF) — do not try to normalize scores across retrievers.
- Retrieve up to 150 candidates per retriever, RRF-fuse, and keep 20.
- Every chunk must carry a `chunk_id` traceable to its source PubMed record. Do not hand-roll ids.

## Contextual chunking
- Store body and source context separately; generation may present both, while
  lexical evidence grading must inspect body only.
- Chunk at sentence boundaries, not character count. Target ~256 tokens, 32 overlap.
- Never truncate silently — split instead.

## Generation contract
- The agent must answer **only from retrieved context**. No outside knowledge.
- Every sentence in the answer must carry a citation to its chunk_id: `[chunk_id]`.
- If retrieved context does not support the answer, emit `INSUFFICIENT_EVIDENCE` and abstain.
- Strip any citation the model invented (validate all cited ids against the retrieved set).

## Verification (critical for medical context)
- Active enforcement is sentence-level citation validation against retrieved ids.
- The optional `--verify` step (model: `llama3.1:8b`) returns an answer-level
  support fraction. When enabled it fails closed unless every sentence is
  marked supported, but remains an unevaluated consistency signal—not medical
  or claim-level verification.
- A verifier that returns no parseable grade (`reason: "unparseable"` /
  `"exception"`) must be surfaced as a distinct failure
  (`evidence_status: "verifier_unavailable"`), never silently folded into the
  same abstain path as a genuine low-support grade
  (`evidence_status: "verifier_rejected"`) — callers/UI need to be able to
  tell "the checker broke" from "the checker rejected this answer".
- Atomic claim verification remains a future recommendation and must not be
  described as active until implemented and evaluated.

## CRAG loop
- Grade retrieval evidence before generating. If grade < 0.4, refine query and re-retrieve (max 3 hops).
- Do not generate from evidence graded below 0.4 — abstain instead.
- The reviewed-evidence-only gate (`allow_unreviewed=False`) must be
  evaluated per hop, not short-circuited on hop 1: a hop with zero reviewed
  chunks does not mean a later, rewritten-query hop can't find any. Only
  abstain with `no_clinician_reviewed_evidence` after every hop comes back
  empty.
- Log grade, hop count, and final status (answered/abstained) for every query.

## Vector store
- Use LanceDB for on-disk dense storage (scales to 10M+ vectors without RAM explosion).
- BM25 documents and queries must use the same `bm25s` tokenizer settings.
- Do not rebuild the full index on every run — checkpoint and reload.
