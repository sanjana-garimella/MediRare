# LLM bake-off results (SLE + MCTD + Sjögren's)

Date: 2026-07-25  
Runtime: Ollama (`http://127.0.0.1:11434`)  
Eval: `experiments/llm_bakeoff/eval_items.json` (10 items: 4 answer / 3 abstain / 3 join)  
Runner: `experiments/llm_bakeoff/run_bakeoff.py`

This is a citation/abstention smoke test over ten hand-authored items. It is
useful for catching contract failures, but is too small and tied to these items
to be a statistically discriminating model benchmark.

## Scores

| Model | Role tested | Score | Time | Failure mode |
|---|---|---|---|---|
| **qwen2.5:14b** | generator | **10/10** | ~30s uncontended | — |
| **llama3.1:8b** | generator | **10/10** | ~17s | earlier malformed `[chunk_id: …]` cite; fixed by normalizer |
| qwen3:32b | generator | 10/10 | ~71s | requires `think: false` (else empty answers) — **parked** |
| **meditron:7b** | medical | **7/10** | ~63s | fails all 3 abstain items (echoes query / invents) |

## Locked stack (active)

| Slot | Model | Use |
|---|---|---|
| **Primary** | `qwen2.5:14b` | Final cited RAG answerer |
| **Backup** | `llama3.1:8b` | Light / low-RAM fallback; also the `agent/ask.py --verify` cross-model consistency-check model (chosen because it's independent of the primary) — **not medical verification** |

Parked: `meditron:7b` — scored 7/10 above (fails all 3 abstain items) and was
originally slated as the `--verify` model anyway (since a support-fraction
grading task doesn't need medical knowledge, just instruction-following).
Live-tested directly against Ollama for that exact task and found it **never
returns a parseable grade** — it echoes the verify prompt back or hallucinates
unrelated PubMed-metadata-style text instead of grading, on both the real
verify prompt and a trivial "what is 2+2" sanity check. `llama3.1:8b` was
substituted and correctly graded 11/11 real test answers when tested the same
way. `meditron:7b` is not used by any code path. Also parked: `qwen3:32b`
(optional later; always `think: false`). No second medical model.

### Retrieval (unchanged)
- Active dense model: `sentence-transformers/all-MiniLM-L6-v2`
- Active ranking: dense + BM25 reciprocal-rank fusion (no cross-encoder reranker)
- Future candidates requiring retrieval evaluation: `bge-m3`,
  `bge-reranker-v2-m3`

## Do not use
- vLLM  
- `meditron` / other medical chat models as the final RAG answerer  
- A third active generator (keep one backup only)  
- coder models (`qwen2.5-coder`, `deepseek-coder`) for the agent

## Config pointers
- `.agents/rules/agent.md` / `.claude/rules/agent.md`  
- `.agents/AGENTS.md`  
- Machine-readable: `experiments/llm_bakeoff/runs/summary.json`
