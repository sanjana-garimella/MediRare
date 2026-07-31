# MediRare — Agent instructions

Portable project context for Cursor and other coding agents. Claude Code also reads `CLAUDE.md` and `.claude/`. Keep this file and `.claude/rules/` aligned on stack and safety rules.

## What this is
Multimodal system for rare-disease **misdiagnosis patterns**: PubMed NLP + clinical figures (CV) → knowledge graph + hybrid RAG → MCP reasoning agent → reports. Target: pooled model across 12 diseases (HuggingFace + paper).

## Active disease scope (12)
Sarcoidosis, SLE, IgG4-related disease, Guillain-Barre syndrome, Granulomatosis with polyangiitis, Myasthenia gravis, Behcet's disease, Castleman disease, Neuromyelitis optica, Antiphospholipid Syndrome, Sjogren's, MCTD.

Out of scope without Sanjana's OK: Inflammatory Myositis and anything not on that list.

## Commands
```bash
python3 nlp/fetch_pubmed_case_reports.py --disease SLE --retmax 50
python3 schemas/validate_jsonl.py data/nlp/processed/sle_case_reports.jsonl CaseReport
python3 -m pytest tests/ -v
python3 scripts/week1_check.py --role nlp
python3 integration/merge.py
streamlit run demo/app.py
```

## Layout
| Path | Role |
|---|---|
| `nlp/` | PubMed fetch + misdiagnosis extraction |
| `cv/` | PMC/PDF figure extraction |
| `schemas/` | JSONL contracts — no raw dict returns |
| `data/biomedical/` | AI-proposed/internal labels, synthetic fixtures, HPO, label guide |
| `data/nlp/processed/` | Case-report JSONL |
| `integration/` | Merge NLP+CV |
| `demo/` | Streamlit |
| `agent/`, `rag/`, `vector_store/` | Planned RAG agent (may not exist yet) |

## LLM / RAG stack (personal, $0) — locked
- **No vLLM.** Ollama OpenAI-compatible (`http://127.0.0.1:11434`).
- **Primary:** `qwen2.5:14b` — final cited answerer
- **Backup:** `llama3.1:8b` — light / low-RAM fallback (one backup only)
- **`--verify` consistency check:** `llama3.1:8b` (the backup model — reused because it's independent of the primary; not medical verification, still experimental)
- Parked: `meditron:7b` (tried as the `--verify` model; empirically 0/5+ parseable replies through Ollama — echoes the prompt instead of grading. Not used by any code path.), `qwen3:32b` (optional; requires `think: false`)
- Embeddings: MiniLM local default (`rag/index.py`); prefer `bge-m3` when disk allows. Rerank: RRF fuse to top-20.
- Results: `experiments/llm_bakeoff/RESULTS.md`. Rules: `.agents/rules/agent.md`.

## End-to-end (SLE + Sjögren's + MCTD)
```bash
# Re-fetch thin diseases (optional; PubMed ceilings ~39 / ~21 misdiagnosis records)
python3 nlp/fetch_pubmed_case_reports.py --disease Sjogrens --retmax 50 --focus misdiagnosis
python3 nlp/fetch_pubmed_case_reports.py --disease MCTD --retmax 50 --focus misdiagnosis

# Extract safely (preserves stronger existing evidence; LLM assist is opt-in)
PYTHONPATH=. python3 nlp/extract_misdiagnosis.py data/nlp/processed/sle_case_reports.jsonl

# Rebuild chunks → index → graph → merge
bash scripts/e2e.sh

# Ask / demo
PYTHONPATH=. python3 agent/ask.py --query "TB mimic pleural SLE"
# Defaults to reviewed evidence and currently abstains. Internal debugging only:
# add --allow-unreviewed
streamlit run demo/app.py
```


## NEVER
- Overwrite `data/biomedical/annotated_cases.csv` with auto-extract (append + human review only)
- Commit raw XML under `data/nlp/raw/`
- Fetch > 200 records per disease per run (NCBI)
- Add a disease without `DISEASE_TERMS` + HPO rows + label-guide section
- Return raw dicts from pipeline functions — use `schemas/`
- Network calls inside `tests/` unit tests
- Add vLLM or paid-only APIs as hard dependencies

## Behavior
- Ask before coding if ambiguous or multi-approach
- Minimum code; touch only what the task needs
- State intent before changing data files
- Prefer existing patterns in `.claude/skills/` and `.agents/skills/`

## Rules index
| Rule | When |
|---|---|
| `.agents/rules/agent.md` / `.claude/rules/agent.md` | `agent/`, `rag/`, `vector_store/` |
| `.claude/rules/nlp.md` | `nlp/`, `data/nlp/` |
| `.claude/rules/data.md` | `data/biomedical/`, `schemas/`, `tests/` |

## Skills worth invoking
- `fetch-disease` — add/fetch a disease end-to-end (Claude)
- `llm-bakeoff` — grounded cite/abstain model comparison
- `run-pipeline-check` — week1 health check
- `review-changes` / `debug-issue` / `refactor-safely`
