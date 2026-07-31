---
name: llm-bakeoff
description: >
  Run a $0 grounded bake-off to pick MediRare's RAG generator. Use when choosing
  or swapping LLM backends (Ollama/Qwen/DeepSeek/GLM/Llama/medical OSS), when
  someone asks "which model", or before locking agent/ config.
---

# MediRare LLM bake-off

## Goal
Pick a **free** OpenAI-compatible generator for cite/abstain RAG — not a medical trivia champion.
This ten-item protocol is a contract smoke test, not a statistically
discriminating benchmark.



## Locked defaults (1 primary + 1 backup + 1 medical side tool)
Do not re-litigate unless re-running this skill:
- Primary: `qwen2.5:14b`
- Backup: `llama3.1:8b` (one backup only)
- `--verify` consistency check: `llama3.1:8b` (the backup model; not medical verification)
- Parked: `meditron:7b` (tried for `--verify`; never returns a parseable grade through Ollama), `qwen3:32b`
- Evidence: `experiments/llm_bakeoff/RESULTS.md`

## Constraints (do not violate)
- No vLLM. No paid APIs as hard deps.
- Serving: Ollama / LM Studio / llama.cpp (`/v1/chat/completions`).
- Score **grounded citation discipline**, not open diagnosis accuracy.
- Full stack rules: `.agents/rules/agent.md` / `.claude/rules/agent.md`.

## Candidate set (default)
1. Qwen2.5-14B (Ollama) — primary local
2. DeepSeek-R1-Distill-Qwen-14B — reasoning; watch verbosity
3. Llama 3.1 8B — weak-hardware baseline
4. GLM-4-9B — optional local
5. Optional: Gemini free tier (best free API quality; not local OSS)
6. Optional medical side: OpenBioLLM-8B or BioMistral-7B (verifier/extractor slot only)

If RAM ≤16GB and no big GPU: use 7B–8B variants of (1)/(2) instead of 14B.

## Eval protocol (same 10 items for every model)
Build prompts from real MediRare chunks (`chunk_id` + text), not model memory.

| Count | Expectation |
|---|---|
| 4 | Answer with sentences each citing real `[chunk_id]` |
| 3 | `INSUFFICIENT_EVIDENCE` abstain |
| 3 | Needs 2-chunk join or short query rewrite |

System contract (same for all):
- Answer only from provided chunks
- Every sentence ends with `[chunk_id]` from the provided set
- If unsupported → exactly `INSUFFICIENT_EVIDENCE`
- No outside medical knowledge

## Scoring (0/1 each; sum /10)
1. Used only provided context (no clear outside facts)
2. All citations ∈ retrieved id set
3. Abstained when expected
4. Did not abstain when evidence was sufficient
5. No invented disease/lab claims beyond chunks

Winner = highest sum. Tie-break: fewer tokens, then faster, then more local/OSS.

## Roles after bake-off
| Role | Prefer |
|---|---|
| Final cited answer | Bake-off winner (usually general instruct) |
| Evidence grade / claim check | Winner or R1-distill |
| Misdiagnosis extraction assist | Optional medical 7–8B **or** winner + schema |
| Active retrieval | MiniLM + BM25 + RRF; no cross-encoder reranker |
| Future retrieval candidates | `bge-m3` + `bge-reranker-v2-m3` after a retrieval benchmark |

## Output format
- Table: model → score /10 → one-line failure mode
- Recommended default `base_url` + `model`
- Note hardware assumption
- Keep under 20 lines

## NEVER
- Declare a winner from Arena/MMLU alone
- Make medical OSS the final answerer without beating the general model on this eval
- Add vLLM or paid keys to repo config
