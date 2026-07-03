#!/usr/bin/env python3
"""
First-pass misdiagnosis sequence extractor — keyword/regex phase.

Usage:
    python3 nlp/extract_misdiagnosis.py data/nlp/processed/sle_case_reports.jsonl

Reads a processed JSONL (CaseReport schema), extracts misdiagnosis_sequence from
abstract text using two-pass regex, writes an updated JSONL in-place, then prints
a coverage report.

Extraction passes
-----------------
Pass 1 (high confidence): named wrong-diagnosis patterns
  - "initially / previously / wrongly diagnosed as/with <X>"
  - "misdiagnosed as/with <X>"
  - "prior diagnosis of <X>"
  - "presenting diagnosis was/of <X>"
  - "<X> masquerading/mimicking as SLE/lupus"

Pass 2 (medium confidence): semantic indicators
  - "initially/first treated/managed as/for <X>"
  - "thought to have <X>"
  - "suspicious of <X>" / "suspected <X>"

Pass 3 (gazetteer fallback): when a misdiagnosis keyword fires but no regex
pattern parses a clean entity, check the abstract for a literal mention of a
condition from a curated list of documented SLE mimics (see
docs/research_references.md). Lower confidence than regex matches — never
overrides them.

Where keywords appear but no entity can be extracted (by regex or gazetteer),
the record is flagged as KEYWORD_NO_ENTITY in the report — these are the
cases where NLP/LLM is needed next.

Output
------
- Updated JSONL (same path) with misdiagnosis_sequence populated
- Coverage report to stdout
- KEYWORD_NO_ENTITY cases to stderr

Conforms to: schemas/case_report.py (misdiagnosis_sequence: List[str])
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


# ── entity capture helpers ────────────────────────────────────────────────────

# Trailing words that indicate we grabbed noise, not the disease name
_TRAILING_FILLER = re.compile(
    r"\s*\b(and|or|but|with|for|in|of|at|to|a|an|the|was|were|has|have|"
    r"after|before|until|during|since|which|that|who|as|by|on|from)\b\s*$",
    re.I,
)

# Common noise terms that suggest captured entity is not a disease name.
# \b after the group matters: without it, the "a"/"an"/"the" alternatives
# match as bare prefixes of unrelated words ("anorexia" starts with "an").
_NOISE_START = re.compile(
    r"^(?:the|this|a|an|its|their|these|following|above|below|"
    r"symptom|sign|finding|evaluation|investigation|workup|"
    r"treatment|therapy|patient|case|report|study|literature|"
    r"result|outcome|data|underlying|concurrent|coexist)\b",
    re.I,
)

# Person-descriptor words: if these appear anywhere in a captured entity, it's
# a mis-scoped subject-NP capture (e.g. "female patient who"), not a diagnosis.
# Needed because passive-voice patterns ("X was initially diagnosed") have no
# fixed left boundary and can walk backward into the sentence's subject.
_PERSON_DESCRIPTOR = re.compile(
    r"\b(?:patient|case|individual|subject|woman|man|male|female|boy|girl|"
    r"child|infant|adult|who|she|he|they|year-old|man\b|woman\b)\b",
    re.I,
)

# Target disease terms to exclude from wrong-diagnosis list
_TARGET_TERMS = (
    "sle", "systemic lupus", "lupus erythematosus", "lupus",
    "sjogren", "mctd", "mixed connective tissue",
    "myositis", "antiphospholipid",
)


def _clean_entity(raw: str) -> str | None:
    """
    Strip trailing filler words, validate length and content.
    Returns lowercase cleaned entity or None if it looks like noise.
    """
    e = raw.strip()
    # iteratively strip trailing filler (handles "X and the" etc.)
    for _ in range(5):
        e2 = _TRAILING_FILLER.sub("", e).strip()
        if e2 == e:
            break
        e = e2
    # length guard
    if len(e) < 4 or len(e) > 80:
        return None
    # starts with a known-noise term
    if _NOISE_START.match(e):
        return None
    # contains a person-descriptor word -> mis-scoped subject-NP, not a diagnosis
    if _PERSON_DESCRIPTOR.search(e):
        return None
    return e.lower().strip(" .,;-")


def _filter_target(entity: str, disease: str) -> bool:
    """Return True if entity is a target disease (should be excluded)."""
    e = entity.lower()
    # Word-boundary match, not raw substring: "myositis" must not match inside
    # "dermatomyositis"/"polymyositis" — those are real wrong-diagnosis mimics
    # of SLE, not the (undergrad-scope) Inflammatory Myositis target itself.
    if any(re.search(rf"\b{re.escape(t)}\b", e) for t in _TARGET_TERMS):
        return True
    if re.search(rf"\b{re.escape(disease.lower().replace('_', ' '))}\b", e):
        return True
    return False


# ── regex patterns ─────────────────────────────────────────────────────────────

# Capture group: 1–6 words up to sentence/clause boundary
_W = r"([\w][\w\s'\-]{2,60}?)"
# Stop before punctuation, a following parenthetical (e.g. "NMOSD (an X)" or a
# trailing acronym gloss "X (ABBR)"), or one of these clause-boundary words.
_STOP = r"(?=[,;.!?(]|\s+(?:and\b|but\b|however\b|which\b|who\b|that\b|was\b|were\b|after\b|before\b|until\b|while\b)|$)"

HIGH_CONFIDENCE: list[re.Pattern] = [
    # "initially diagnosed as/with X"
    re.compile(rf"(?:initially|first)\s+diagnosed\s+(?:as|with|for)\s+{_W}{_STOP}", re.I),
    # "misdiagnosed as/with X"
    re.compile(rf"misdiagnosed\s+(?:as|with|for)\s+{_W}{_STOP}", re.I),
    # "previously diagnosed as/with X"
    re.compile(rf"previously\s+diagnosed\s+(?:as|with|for)\s+{_W}{_STOP}", re.I),
    # "prior diagnosis of X"
    re.compile(rf"prior\s+diagnosis\s+of\s+{_W}{_STOP}", re.I),
    # "wrongly diagnosed as/with X"
    re.compile(rf"wrongly\s+diagnosed\s+(?:as|with|for)\s+{_W}{_STOP}", re.I),
    # "presenting diagnosis was/of X"
    re.compile(rf"presenting\s+diagnosis\s+(?:was|of)\s+{_W}{_STOP}", re.I),
    # "delayed diagnosis of X" — captures who was missed, not what was wrong
    re.compile(rf"delayed\s+diagnosis\s+of\s+{_W}{_STOP}", re.I),
    # "referred after X years with a diagnosis of Y"
    re.compile(rf"referred\s+after.{{3,60}}?diagnosis\s+of\s+{_W}{_STOP}", re.I),
    # "X was initially/first diagnosed" — passive voice, entity precedes the verb.
    # Bounded to <=4 words (disease-name subjects are short) so it can't walk
    # back across a whole sentence when there's no comma/period to stop it.
    re.compile(rf"((?:[A-Za-z][\w'\-]*\s+){{0,3}}[A-Za-z][\w'\-]*)\s+(?:was|were)\s+(?:initially|first)\s+diagnosed\b", re.I),
]

# "X masquerading/mimicking as SLE/lupus" → X is a condition wrongly called lupus
_MASQUERADE = re.compile(
    r"([\w][\w\s'\-]{3,50}?)\s+(?:masquerad\w*|mimick\w*)\s+as\s+"
    r"(?:SLE|systemic lupus|lupus erythematosus|lupus)",
    re.I,
)

MEDIUM_CONFIDENCE: list[re.Pattern] = [
    re.compile(rf"initially\s+(?:treated|managed)\s+(?:as|for)\s+{_W}{_STOP}", re.I),
    re.compile(rf"thought\s+to\s+have\s+{_W}{_STOP}", re.I),
    # "suspicious of X" / "suspected X" — a working diagnosis considered before the real one
    re.compile(rf"suspicious\s+of\s+{_W}{_STOP}", re.I),
    re.compile(rf"suspected\s+(?:of\s+having\s+|to\s+have\s+)?{_W}{_STOP}", re.I),
]

# NOTE: a generic forward-direction "mimick*/masquerad* <X>" pattern (without
# requiring "...as SLE/lupus") was tried and removed — it matched "mimicking
# <symptom/manifestation>" (e.g. "mimicking a LN flare", "mimicking vascular,
# infectious ... processes") far more often than it matched a real named wrong
# diagnosis. Same trap the module already documents for "presenting as X".
# _MASQUERADE below (which anchors on "...as SLE/lupus") stays; it doesn't
# share this problem because the target-disease anchor rules out symptom talk.

# Signal-only: keyword present but entity extraction is the hard part
_SIGNAL_ONLY = re.compile(
    r"misdiagnos|initially diagnosed|previously diagnosed|prior diagnosis|"
    r"delayed diagnosis|wrongly diagnosed|masquerad|mimick",
    re.I,
)

# ── gazetteer fallback ──────────────────────────────────────────────────────
#
# Curated list of conditions documented to be mistaken for / mistaken as SLE,
# from "Mimickers of Systemic Lupus Erythematosus: Case Series and Literature
# Overview" (PMC12525093, see docs/research_references.md). Used only as a
# last resort when a misdiagnosis keyword fires (_SIGNAL_ONLY) but no regex
# pattern could parse a clean entity out of the sentence structure — i.e. it
# never competes with or overrides a HIGH/MEDIUM regex match.
_KNOWN_SLE_MIMICS = (
    "LRBA deficiency", "CTLA-4 insufficiency", "HELIOS deficiency",
    "SOCS1 haploinsufficiency", "TLR7 deficiency", "UNC93B1 deficiency",
    "IRE1α deficiency", "DOCK11 deficiency",
    "autoimmune lymphoproliferative disorder", "DNASE1L3 deficiency", "SPENCD",
    "Aicardi-Goutières syndrome", "AGS", "SAVI", "PRAAS",
    "Singleton-Merten syndrome",
    "dermatomyositis", "polymyositis", "Still's disease",
    "neuromyelitis optica spectrum disorder", "NMOSD", "multiple sclerosis",
    "Castleman disease",
    "parvovirus B19", "endocarditis", "hepatitis", "HIV", "Epstein-Barr virus",
    "cytomegalovirus", "Borrelia", "Lyme disease", "toxoplasmosis",
    "histoplasmosis", "tuberculosis", "leprosy", "leishmaniasis",
    "Whipple's disease",
    "angioimmunoblastic T-cell lymphoma", "lymphoma",
    "myelodysplastic syndrome", "atrial myxoma",
    "drug-induced lupus",
    "graft-versus-host disease",
    "hypocomplementemic urticarial vasculitis syndrome", "Schnitzler syndrome",
)
_MIMIC_GAZETTEER = [
    (term, re.compile(rf"\b{re.escape(term)}\b", re.I)) for term in _KNOWN_SLE_MIMICS
]


def _gazetteer_match(abstract: str, disease: str) -> list[str]:
    """
    Only accept a mimic-term match if it shares a sentence with a misdiagnosis
    signal keyword. Without this, generic differential-diagnosis boilerplate
    ("...KFD mimics infectious, autoimmune, or malignant disorders like
    lymphoma...") matches on term presence alone, unrelated to what actually
    happened to this patient — same class of false positive as PMID 39912674,
    40110311, 40936738 etc. in the eval run that added this gazetteer.
    """
    found: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", abstract):
        if not _SIGNAL_ONLY.search(sentence):
            continue
        for term, pat in _MIMIC_GAZETTEER:
            if pat.search(sentence):
                entity = term.lower()
                if not _filter_target(entity, disease) and entity not in found:
                    found.append(entity)
    return found


# ── main extraction logic ─────────────────────────────────────────────────────

def extract(abstract: str, disease: str) -> tuple[list[str], str]:
    """
    Extract misdiagnosis sequences from a case report abstract.

    Returns
    -------
    (sequences, evidence_level)
        sequences      : list of wrong-diagnosis strings (may be empty)
        evidence_level : 'high' | 'medium' | 'signal_only' | 'none'
    """
    if not abstract or len(abstract) < 30:
        return [], "none"

    found: list[str] = []

    for pat in HIGH_CONFIDENCE:
        for m in pat.finditer(abstract):
            raw = m.group(1)
            entity = _clean_entity(raw)
            if entity and not _filter_target(entity, disease) and entity not in found:
                found.append(entity)

    for m in _MASQUERADE.finditer(abstract):
        raw = m.group(1)
        entity = _clean_entity(raw)
        if entity and not _filter_target(entity, disease) and entity not in found:
            found.append(entity)

    if found:
        return found, "high"

    med: list[str] = []
    for pat in MEDIUM_CONFIDENCE:
        for m in pat.finditer(abstract):
            raw = m.group(1)
            entity = _clean_entity(raw)
            if entity and not _filter_target(entity, disease) and entity not in med:
                med.append(entity)

    if med:
        return med, "medium"

    if _SIGNAL_ONLY.search(abstract):
        gaz = _gazetteer_match(abstract, disease)
        if gaz:
            return gaz, "gazetteer"
        return [], "signal_only"

    return [], "none"


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("jsonl", help="Path to processed JSONL (e.g. data/nlp/processed/sle_case_reports.jsonl)")
    parser.add_argument("--dry-run", action="store_true", help="Print report without writing to disk")
    args = parser.parse_args()

    path = Path(args.jsonl)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 1

    records: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    stats = {"high": 0, "medium": 0, "gazetteer": 0, "signal_only": 0, "none": 0, "no_abstract": 0}
    signal_only_pmids: list[str] = []
    extracted_examples: list[tuple[str, list[str]]] = []
    updated: list[dict] = []

    for rec in records:
        r = deepcopy(rec)
        abstract = r.get("abstract", "")
        disease = r.get("disease", "")

        if not abstract or len(abstract) < 30:
            stats["no_abstract"] += 1
            updated.append(r)
            continue

        seqs, level = extract(abstract, disease)
        stats[level] += 1

        if level == "signal_only":
            signal_only_pmids.append(r["pubmed_id"])

        if seqs:
            r["misdiagnosis_sequence"] = seqs
            extracted_examples.append((r["pubmed_id"], seqs))
        updated.append(r)

    # ── report ────────────────────────────────────────────────────────────────
    total = len(records)
    populated = stats["high"] + stats["medium"] + stats["gazetteer"]
    print(f"\n{'='*60}")
    print(f"Misdiagnosis extraction — {path.name}")
    print(f"{'='*60}")
    print(f"  Total records      : {total}")
    print(f"  No abstract        : {stats['no_abstract']}")
    print(f"  High-confidence    : {stats['high']:>3}  (keyword + named entity extracted)")
    print(f"  Medium-confidence  : {stats['medium']:>3}  (semantic indicator + entity)")
    print(f"  Gazetteer          : {stats['gazetteer']:>3}  (keyword + known SLE-mimic name matched)")
    print(f"  Signal only        : {stats['signal_only']:>3}  (keyword found, entity unclear — NLP needed)")
    print(f"  No signal          : {stats['none']:>3}  (no misdiagnosis indicators)")
    print(f"  misdiagnosis_sequence populated : {populated}/{total}")
    print()

    if extracted_examples:
        print("Extracted sequences:")
        for pmid, seqs in extracted_examples:
            print(f"  PMID {pmid}: {seqs}")
        print()

    if signal_only_pmids:
        print("KEYWORD_NO_ENTITY — keyword found but entity not cleanly extracted:")
        print("  These need NLP (PubMedBERT NER) or LLM to resolve:")
        for pmid in signal_only_pmids:
            print(f"  PMID {pmid}", file=sys.stderr)
            print(f"  PMID {pmid}")
        print()

    print("Coverage gap analysis:")
    gap_pct = stats["none"] / total * 100 if total else 0
    print(f"  {stats['none']}/{total} records ({gap_pct:.0f}%) have no detectable misdiagnosis signal.")
    print(f"  Reasons keywords are NOT enough:")
    print(f"    1. SLE presenting as <symptom> ≠ a wrong diagnosis (e.g. 'presenting as nephrotic syndrome')")
    print(f"    2. Misdiagnosis implied but no trigger keyword used (e.g. 'worked up for X for 3 years')")
    print(f"    3. Abstract truncated — full text has the signal, abstract doesn't")
    print(f"    4. Signal in case narrative, not abstract (PMC full text needed)")
    print()

    if args.dry_run:
        print("DRY RUN — no files written.")
        return 0

    # ── write updated JSONL ───────────────────────────────────────────────────
    with path.open("w", encoding="utf-8") as f:
        for r in updated:
            f.write(json.dumps(r, default=str) + "\n")
    print(f"Written: {path}  ({total} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
