# MediRare — Claude Code Project Context

## What this project does
Multimodal AI system to detect misdiagnosis patterns in rare autoimmune diseases.
Pipeline: PubMed case reports (NLP) + figure extraction (CV) → misdiagnosis knowledge graph → LLM reasoning agent → per-disease research reports.

## Current focus: SLE + Sjögren's (working end-to-end)
MCTD, Inflammatory Myositis, and Antiphospholipid Syndrome are undergrad scope.

## Commands
- Fetch data:     `python3 nlp/fetch_pubmed_case_reports.py --disease SLE --retmax 50`
- Validate:       `python3 schemas/validate_jsonl.py data/nlp/processed/sle_case_reports.jsonl`
- Run tests:      `python3 -m pytest tests/ -v`
- Week1 check:    `python3 scripts/week1_check.py --role nlp`
- Demo:           `streamlit run demo/app.py`
- Merge:          `python3 integration/merge.py`

## Structure
- `nlp/`                → PubMed fetcher, future misdiagnosis extractor
- `cv/`                 → PDF figure extraction (PyMuPDF)
- `data/nlp/processed/` → real PubMed case reports (JSONL)
- `data/biomedical/`    → gold annotated cases, HPO mappings, label guide
- `schemas/`            → data contracts for all pipeline outputs
- `integration/`        → merger + mock stubs
- `demo/`               → Streamlit app

## Data state (as of 2026-06-29)
| Asset | Location | Status |
|---|---|---|
| 50 PubMed records × 3 diseases | `data/nlp/processed/*.jsonl` | Fetched, no extraction yet |
| 10 gold annotated cases | `data/biomedical/annotated_cases.csv` | Hand-crafted, do not overwrite |
| HPO mappings (31 rows) | `data/biomedical/hpo_mapping_table.csv` | SLE, Sjögren's, MCTD |
| Label guide | `data/biomedical/label_guide.md` | Annotation rules |

**Key gap**: `misdiagnosis_sequence` is `[]` for all 150 real records — extraction NLP is #1 next step.
**Sjögren's**: 13/50 records are noise — fix search term to `"primary Sjögren's syndrome" AND "case report"`.

## Misdiagnosis extraction keywords
"initially diagnosed with", "misdiagnosed as", "previously diagnosed", "presenting diagnosis", "referred after", "prior diagnosis", "delayed diagnosis"

## NEVER
- Never overwrite `data/biomedical/annotated_cases.csv` with auto-extracted data (append + human review only)
- Never commit raw XML files from `data/nlp/raw/`
- Never fetch > 200 records per disease per run (NCBI rate limit)
- Never add a new disease without: (1) `DISEASE_TERMS` entry, (2) HPO rows, (3) label guide section
- Never return raw dict from pipeline functions — use schemas in `schemas/`
- Never run network calls inside `tests/` unit tests

## Behavior rules
- Ask before coding if the request is ambiguous or has multiple valid approaches
- Write the minimum code that solves the problem — no speculative abstractions
- Touch only what the task requires — do not refactor neighboring code
- State what you're about to do and why before making changes to data files

## Response style
- Terse. No trailing summaries.
- Don't re-read files already read this session.
- Don't re-explore project structure unless asked.
- Edit existing files; don't create new ones without reason.

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
| ------ | ---------- |
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
