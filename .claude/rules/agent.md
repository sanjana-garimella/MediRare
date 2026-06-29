---
name: agent-rules
description: Design rules for the MCP reasoning agent and RAG pipeline. Loaded when editing agent/, rag/, or vector store code.
globs:
  - "agent/**"
  - "rag/**"
  - "vector_store/**"
---
# MediRare RAG + Agent rules

## Retrieval architecture
- Use **hybrid search**: dense embeddings (ChromaDB/LanceDB) + BM25 sparse index. Never dense-only.
- Fuse rankings with reciprocal rank fusion (RRF) — do not try to normalize scores across retrievers.
- Retrieve 150 candidates, rerank to 20 before generating. Reranker cost is fixed at 150 pairs regardless of corpus size.
- Every chunk must carry a `chunk_id` traceable to its source PubMed record. Do not hand-roll ids.

## Contextual chunking
- Prepend a one-sentence context prefix to each chunk before indexing: "This chunk from [disease] case report [PMID] describes [topic]."
- Chunk at sentence boundaries, not character count. Target ~256 tokens, 32 overlap.
- Never truncate silently — split instead.

## Generation contract
- The agent must answer **only from retrieved context**. No outside knowledge.
- Every sentence in the answer must carry a citation to its chunk_id: `[chunk_id]`.
- If retrieved context does not support the answer, emit `INSUFFICIENT_EVIDENCE` and abstain.
- Strip any citation the model invented (validate all cited ids against the retrieved set).

## Verification (critical for medical context)
- Split every generated answer into atomic claims. Check each claim against its cited chunks.
- Use **claim-level** verification, not answer-level. One unsupported claim fails the whole answer.
- Minimum support threshold: configurable, start at 0.3. Document the threshold in the run config.
- Abstain when min claim support < threshold. "Abstain" is a correct output, not a failure.

## CRAG loop
- Grade retrieval evidence before generating. If grade < 0.4, refine query and re-retrieve (max 3 hops).
- Do not generate from evidence graded below 0.4 — abstain instead.
- Log grade, hop count, and final status (answered/abstained) for every query.

## Vector store
- Use LanceDB for on-disk dense storage (scales to 10M+ vectors without RAM explosion).
- BM25 index must stem tokens the same way it stems documents. Use bm25s.
- Do not rebuild the full index on every run — checkpoint and reload.
