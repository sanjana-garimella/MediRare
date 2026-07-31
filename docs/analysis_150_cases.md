# Archived 150-case analysis

The previous version of this document has been retired because it mixed:

- ten synthetic placeholder cases with real PubMed records;
- AI-proposed and extractor-derived labels with independent validation;
- selected case-report counts with prevalence-like clinical conclusions; and
- stale pipeline state from before extraction, indexing, and graph generation.

It must not be cited as evidence that a diagnostic-confusion pattern is common,
causal, clinically validated, or statistically representative.

## Current reproducible scope

The committed research corpus contains 160 PubMed records:

| Disease | Records | Sequence-bearing rows |
|---|---:|---:|
| SLE | 100 | 44 |
| Sjögren's | 39 | 16 |
| MCTD | 21 | 9 |

These sequence counts are pipeline outputs, not confirmed misdiagnoses. All
current ground-truth CSV labels are AI-proposed. The Sjögren's and MCTD labels
are partly derived from keyword/extractor output and therefore provide only
circular internal parsing diagnostics.

Run the current evaluator rather than copying values from prose:

```bash
python3 nlp/eval_extractor.py \
  --pred data/nlp/processed/sle_case_reports.jsonl \
  --truth data/biomedical/sle_misdiagnosis_groundtruth.csv
```

## Interpretation constraints

- Case reports are selected, publication-biased anecdotes.
- An extracted mention may be a differential, comorbidity, complication,
  excluded diagnosis, symptom, or reverse-direction case.
- A PMID citation establishes where text came from; it does not establish
  clinical entailment or correctness.
- Graph edge weights are selected-report counts, never prevalence or risk.
- Classification criteria and antibodies are not stand-alone diagnostic rules.
- Nothing in this repository should guide patient diagnosis or treatment.

## Required before clinical or public claims

Each candidate record needs blinded human adjudication with:

1. the exact supporting evidence span;
2. the final diagnosis;
3. the prior diagnosis actually received;
4. relation type and direction;
5. certainty and exclusion/negation status; and
6. reviewer identity plus disagreement resolution.

Until then, the default graph is intentionally fail-closed and excludes
unreviewed candidates. `data/graph/candidate_misdiagnosis_graph.json`, when
generated, is an annotation queue—not a medical knowledge graph.
