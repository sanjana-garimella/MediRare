# Research references — misdiagnosis extraction & rare-disease NLP/CV

Notes from a literature scan for extending `nlp/extract_misdiagnosis.py` beyond
regex, and `cv/fetch_pmc_figures.py` beyond caption keywords. See
`.claude/rules/nlp.md` for the current extraction rules.

## SLE / Sjögren's misdiagnosis literature (clinical domain)

- [Understanding the impact of delayed diagnosis and misdiagnosis of SLE](https://pmc.ncbi.nlm.nih.gov/articles/PMC11668484/) —
  PMID 11668484, already in the corpus (`cv/extract_figures.py` PMID_DISEASE
  map). Median diagnostic delay ~47 months; ~47% of patients originally
  misdiagnosed.
- [Mimickers of Systemic Lupus Erythematosus: Case Series and Literature Overview](https://pmc.ncbi.nlm.nih.gov/articles/PMC12525093/) —
  hand-curated catalog of conditions SLE gets mistaken for. Useful as a
  gold/validation list to cross-check extracted `misdiagnosis_sequence`
  entities against.
- [Diagnostic dilemma: SLE + Sjögren's mimicking multiple myeloma](https://pmc.ncbi.nlm.nih.gov/articles/PMC12442308/) —
  concrete example of the exact misdiagnosis-sequence structure being modeled.
- [Delayed diagnosis adversely affects outcome in SLE (LuLa cohort)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7933718/) —
  cross-sectional outcome data tying diagnostic delay to organ damage.

## Methodology — closest published analog to this pipeline

- [Temporally annotated textual time series from PubMed Open Access clinical case reports (PMOA-TTS)](https://arxiv.org/html/2505.20323) —
  **read this one first.** 124,699 PubMed OA case reports, same source
  corpus as this project. LLM-extracted structured timelines (symptoms →
  diagnoses → treatments → outcomes) validated against clinician-annotated
  gold timelines via a temporal concordance index. Effectively the mature
  version of `misdiagnosis_sequence` extraction — extracts the *whole*
  diagnosis timeline rather than one field, which would directly capture
  "misdiagnosed as X first, then correctly diagnosed as SLE at time Y."

## Extraction technique — replacing/augmenting regex

- [A comparative study of pre-trained language models for NER in clinical trial eligibility criteria](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9450226/) —
  compares BioBERT, BlueBERT, PubMedBERT, SciBERT for biomedical NER.
  Caveat: these models are tuned for entity detection (disease/drug/symptom
  mention), not the *initially-diagnosed-as* semantic relation — would need
  fine-tuning or a relation-extraction step on top to distinguish "wrong
  diagnosis" from "correct diagnosis" mentions.

## Other adjacent hits (lower priority)

- [ZebraMap: A Multimodal Rare Disease Knowledge Map with LLM-Enriched Information Extraction Pipeline](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12785374/) —
  LLM pipeline parsing case reports into structured fields (symptoms,
  diagnostic methods, differential diagnoses, treatments, outcome).
- [CaseReportBench: An LLM Benchmark Dataset for Dense Information Extraction in Clinical Case Reports](https://arxiv.org/pdf/2505.17265) —
  reference for designing a larger eval set than the current
  `sle_misdiagnosis_groundtruth.csv`.
- [Comparative analysis of LLMs on rare disease identification](https://ojrd.biomedcentral.com/articles/10.1186/s13023-025-03656-w) —
  Claude 3.5 Sonnet reported at 78.9% diagnostic accuracy on rare pediatric
  cases vs. 26.3% for human physicians in the cited study; relevant if
  choosing a model for the downstream reasoning agent.
- [JMIR — NLP approach to identify diagnostic errors in safety event reports](https://www.jmir.org/2024/1/e50935) —
  adjacent field (hospital incident reports, not case-report literature).
  Notes the same failure mode as our regex: struggles with implicit phrasing
  that avoids canonical trigger words; needs full text, not just abstracts.

## Current extractor baseline (for comparison)

`nlp/eval_extractor.py` on 100 SLE records vs.
`data/biomedical/sle_misdiagnosis_groundtruth.csv`:
precision 0.88, recall 0.22, F1 0.35. High precision / low recall — matches
the failure mode called out in the JMIR paper above.

**Update (2026-07-03):** after regex fixes (word-boundary bugs in
`_filter_target`/`_NOISE_START`, a passive-voice pattern, "suspicious of X"
patterns) plus a same-sentence-constrained gazetteer built from the SLE
mimickers reference above: **precision 0.83, recall 0.40, F1 0.54.** Recall
nearly doubled at a ~5-point precision cost. See `nlp/extract_misdiagnosis.py`
for the gazetteer implementation and why the unconstrained version (matching
mimic terms anywhere in the abstract) was rejected — it matched generic
differential-diagnosis boilerplate unrelated to the actual patient.

## Computer vision — figure modality classification

`cv/fetch_pmc_figures.py` classifies each figure's modality (imaging /
histology / lab_chart / rash_image / other) from **caption text only**, via
keyword regex. On the committed corpus (437 figures, see README), 184/437
(42%) land in "other" — the caption just doesn't carry a modality keyword
(e.g. "small subcentimeter prevascular lymph nodes" instead of "CT shows...").
Matches the README's Phase 3 roadmap item: "Figure type classifier: ViT
zero-shot → fine-tune on labeled figures."

- [BiomedCLIP (`microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224`)](https://huggingface.co/microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224) —
  **the direct fit.** CLIP-style vision-language model pretrained on
  PMC-15M — 15 million figure-caption pairs scraped from PubMed Central,
  the exact same corpus this project's figures come from. Classifies
  straight from the image, so it can label figures whose captions have no
  modality keyword at all. Loaded via `open_clip` (official route, not the
  `trust_remote_code=True` community HF ports — see below).
- [Open-PMC](https://arxiv.org/pdf/2503.14377) — newer, higher-quality
  successor dataset to PMC-15M: 2.2M PMC image-text pairs with modality
  annotations and subfigure separation. Worth checking if BiomedCLIP's
  accuracy (see validation notes below) turns out to be a training-data
  quality ceiling rather than a modeling one.
- [ROCOv2 (Radiology Objects in COntext v2)](https://www.nature.com/articles/s41597-024-03496-6) —
  79,789 radiology images from PMC OA with manually curated modality
  concepts (CT/MRI/X-ray/ultrasound + anatomical region). Good candidate
  gold set if this ever moves from zero-shot to fine-tuning — matches the
  "imaging" bucket specifically, at much larger scale than this project's
  own 131 imaging-labeled figures.
- [Biomedical Imaging Modality Classification Using Combined Visual Features and Textual Terms](https://pmc.ncbi.nlm.nih.gov/articles/PMC3170788/) —
  older ImageCLEF-era paper, but the exact architecture this project should
  grow toward: caption keywords **and** visual features combined, not
  either alone. `fetch_pmc_figures.py`'s current design (keyword first,
  vision model only as a fallback for the keyword-miss bucket) is a cheap
  approximation of this; a real combined scorer would outperform either
  tier voting alone.
- [CLIP in Medical Imaging: A Survey](https://arxiv.org/pdf/2312.07353) —
  background reading on where CLIP-style models succeed/fail in medical
  imaging generally; covers the domain-shift problem (natural-image CLIP
  pretraining vs. medical image statistics) that PMC-15M pretraining exists
  to fix.

### Validation notes (2026-07-03)

Manually checked BiomedCLIP zero-shot classification against real
`--download-images` output for figures already in the "other" bucket
(ground truth = my own reading of the caption + figure content), two
separate batches: **10/13 correct (~77%)**. Both misses were small, cropped,
measurement-only figures ("lymph node measuring 12x5mm", no anatomical
context in the crop) — the model reads them as histology or skin close-ups.
One miss scored 97% confidence, so a stricter `CLASSIFY_CONFIDENCE_THRESHOLD`
does not reliably catch this failure mode. Shipped as an opt-in
`--classify-images` flag (fallback tier only, never overrides a
caption-keyword match) with this limitation documented inline in
`cv/fetch_pmc_figures.py` — meaningfully less reliable than the NLP
gazetteer (~4:1 good:bad there vs. this).

Separately found and fixed two caption-regex bugs while pulling test
figures: `echocardiogra`/`angiogra`/`sonograph` stems had a trailing `\b`
that blocked them from ever matching their actual inflected forms
("echocardiography", "angiography", "sonography") — silently dropped the
single most common imaging word in these case reports. And `histolog` (for
"histology") doesn't match "histopathology" (different root after "histo"),
which let at least one real histology caption fall through to a false
"necrotic" → rash_image match. Both fixed directly in `_FIGURE_TYPE_RULES`.
