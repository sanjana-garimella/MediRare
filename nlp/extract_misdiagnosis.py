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
import os
import re
import sys
import tempfile
import unicodedata
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
    r"having|to|for|only|conditions?|"
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

_EVIDENCE_RANK = {
    "none": 0,
    "signal_only": 0,
    "legacy_unreviewed": 1,
    "llm": 1,
    "gazetteer": 2,
    "medium": 3,
    "high": 4,
    "reviewed": 5,
}

_VAGUE_ENTITIES = {
    "other disease", "other diseases", "various diseases", "several diseases",
    "many diseases", "a disease", "underlying disease", "clinical condition",
    "other condition", "other conditions", "various conditions",
    "reactive", "idiopathic", "viral factors", "tumor pathologies",
    "cardiac involvement", "light chain restricted expression",
}


def _normalize_unicode(text: str) -> str:
    text = (text or "").replace("’", "").replace("'", "")
    text = unicodedata.normalize("NFKD", text or "")
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        text.encode("ascii", "ignore").decode().lower(),
    ).strip()


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
    cleaned = e.lower().strip(" .,;-")
    if _normalize_unicode(cleaned) in _VAGUE_ENTITIES:
        return None
    return cleaned


_DISEASE_ALIASES = {
    "sjogrens": ("sjogren", "sjogrens"),
    "sle": (
        "sle", "npsle", "neuropsychiatric sle",
        "systemic lupus erythematosus", "lupus",
    ),
    "mctd": ("mctd", "mixed connective tissue disease"),
}


def _disease_aliases(disease: str) -> tuple[str, ...]:
    disease_norm = _normalize_unicode(disease.replace("_", " "))
    return _DISEASE_ALIASES.get(disease_norm, (disease_norm,))


def _filter_target(entity: str, disease: str) -> bool:
    """Return True only for self-target aliases of the record's true disease."""
    e = _normalize_unicode(entity)
    if any(re.search(rf"\b{re.escape(alias)}\b", e) for alias in _disease_aliases(disease)):
        return True
    return False


# Exclusion/differential-diagnosis cues: co-occurrence with these near an
# entity or the record's own target disease means the mention describes a
# diagnosis being *ruled out* or *listed as one of many possibilities*, not
# something this patient was actually diagnosed/treated as.
_EXCLUSION_CUE = re.compile(
    r"\b(?:exclud\w+|ruled?\s+out|rule\s+out|inconsistent\s+with|"
    r"against\s+(?:a\s+)?diagnos\w*|not\s+consistent\s+with|"
    r"unlikely\s+to\s+be|not\s+support\w*|negative\s+for)\b",
    re.I,
)

# Broad relation-signal set covering every keyword used across
# HIGH_CONFIDENCE / MEDIUM_CONFIDENCE / the gazetteer, so re-validating an
# already-matched entity against this can only ever be a no-op-or-stricter
# check, never a source of new false negatives on genuinely fresh matches.
_RELATION_SIGNAL = re.compile(
    r"misdiagnos|diagnos|treated|managed|mistaken|confused|thought|"
    r"suspect|suspicio|presum|mimic|masquerad|working\s+diagnosis",
    re.I,
)

# A mention embedded in a generic teaching list ("common causes of X
# include A, B, C...") describes background differential-diagnosis
# knowledge, not a specific event in this patient's case.
_GENERIC_LIST_CUE = re.compile(
    r"\b(?:common\s+causes?\s+of|differential\s+diagnos\w*|such\s+as|"
    r"includ\w+)\b",
    re.I,
)


def _ground_entity(entity: str, abstract: str) -> bool:
    """Re-validate one entity (fresh or preserved) against the abstract.

    Kept only if at least one sentence literally mentions it AND carries a
    misdiagnosis-relation signal AND is not itself (or its immediate next
    sentence) an exclusion of that mention. This is applied uniformly to
    freshly regex-extracted entities and to pre-existing legacy sequences on
    every run, so stale bad data can't hide behind provenance-preservation
    forever (see PMID 41996261 / 41939103 in docs/research_references.md).
    """
    norm_entity = _normalize_unicode(entity)
    if not norm_entity:
        return False
    sentences = re.split(r"(?<=[.!?])\s+", abstract or "")
    for i, sentence in enumerate(sentences):
        norm_sentence = f" {_normalize_unicode(sentence)} "
        if f" {norm_entity} " not in norm_sentence:
            continue
        if not _RELATION_SIGNAL.search(sentence):
            continue
        window = sentences[i : i + 2]
        if any(_EXCLUSION_CUE.search(s) for s in window):
            continue
        return True
    return False


_TARGET_EXCLUDED_TEMPLATES = (
    r"after\s+exclud\w+\s+{d}",
    r"exclud\w+\s+(?:a\s+)?diagnos\w*\s+of\s+{d}",
    r"{d}\s+(?:was|were)\s+(?:ruled\s+out|excluded)",
    r"ruled?\s+out\s+{d}",
    r"(?:against|inconsistent\s+with)\s+(?:a\s+diagnosis\s+of\s+)?{d}",
)


def _target_disease_excluded(abstract: str, disease: str) -> bool:
    """True if the record's OWN target disease is explicitly ruled out
    somewhere in the abstract (e.g. "After excluding systemic lupus
    erythematosus...").

    This means the case report's real final diagnosis is something else
    entirely, so the record's disease-scoping assumption ("target disease
    was confirmed; X was a wrong diagnosis along the way") is invalid — any
    misdiagnosis_sequence attached to it is not trustworthy regardless of
    which specific entities were extracted (see PMID 42112145).
    """
    patterns = [
        re.compile(tmpl.format(d=re.escape(alias)), re.I)
        for alias in _disease_aliases(disease)
        for tmpl in _TARGET_EXCLUDED_TEMPLATES
    ]
    for sentence in re.split(r"(?<=[.!?])\s+", abstract or ""):
        norm_sentence = _normalize_unicode(sentence)
        if any(p.search(norm_sentence) or p.search(sentence) for p in patterns):
            return True
    return False


def _target_disease_unconfirmed(abstract: str, disease: str) -> bool:
    """True if the target disease is mentioned but never affirmed as this
    patient's own diagnosis — only ever inside a generic differential-list
    sentence (e.g. "...autoimmune diseases such as systemic lupus
    erythematosus or rheumatoid arthritis").

    Catches disease-scoping mismatches from overlapping PubMed search terms,
    where the abstract is really about a different disease that happens to
    name the target disease as one of many differentials (see PMID
    41939103, which is a Sjögren's case that only name-drops SLE once, in a
    textbook list of causes of pleural effusion).
    """
    aliases = _disease_aliases(disease)
    mentioned = False
    affirmed = False
    for sentence in re.split(r"(?<=[.!?])\s+", abstract or ""):
        norm_sentence = _normalize_unicode(sentence)
        if not any(re.search(rf"\b{re.escape(a)}\b", norm_sentence) for a in aliases):
            continue
        mentioned = True
        if not _GENERIC_LIST_CUE.search(sentence):
            affirmed = True
    return mentioned and not affirmed


# ── regex patterns ─────────────────────────────────────────────────────────────

# Capture group: disease-name span up to sentence/clause boundary
_W = r"([\w][\w\s'\-]{2,80}?)"
# Stop before punctuation, a following parenthetical (e.g. "NMOSD (an X)" or a
# trailing acronym gloss "X (ABBR)"), or one of these clause-boundary words.
# Include "with" so "diagnosed as pustular psoriasis with superimposed ..."
# captures the disease, not the long modifier tail (60-char cap used to fail entirely).
_STOP = (
    r"(?=[,;.!?(]|\s+(?:and\b|but\b|with\b|however\b|which\b|who\b|that\b|"
    r"was\b|were\b|after\b|before\b|until\b|while\b|due\b|leading\b|causing\b|"
    r"in\b(?!\s+situ\b)|of\b(?!\s+(?:unknown\s+(?:origin|primary)|the\s+bowel)\b)|"
    r"for\b|at\b|on\b|from\b)|$)"
)

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
    # "referred after X years with a diagnosis of Y"
    re.compile(rf"referred\s+after.{{3,60}}?diagnosis\s+of\s+{_W}{_STOP}", re.I),
    # "mistaken for X" / "confused with X"
    re.compile(rf"mistaken\s+for\s+{_W}{_STOP}", re.I),
    re.compile(rf"confused\s+with\s+{_W}{_STOP}", re.I),
    # "misdiagnosis as X" / "prevent misdiagnosis as X"
    re.compile(rf"misdiagnosis\s+as\s+{_W}{_STOP}", re.I),
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
    re.compile(rf"initially\s+(?:treated|managed)\s+(?:as|for)\s+(?:a\s+)?(?:presumed\s+)?{_W}{_STOP}", re.I),
    re.compile(rf"(?:was|were)\s+treated\s+as\s+(?:a\s+)?(?:presumed\s+)?{_W}{_STOP}", re.I),
    re.compile(rf"thought\s+to\s+(?:have|be)\s+{_W}{_STOP}", re.I),
    # "suspicious of X" / "suspected X" — a working diagnosis considered before the real one
    re.compile(rf"suspicious\s+of\s+{_W}{_STOP}", re.I),
    re.compile(rf"suspected\s+(?:of\s+having\s+|to\s+have\s+)?{_W}{_STOP}", re.I),
    re.compile(rf"working\s+diagnosis\s+of\s+{_W}{_STOP}", re.I),
    # "symptom complex / presentation mimicking X" (X = named disease, not bare symptom)
    re.compile(rf"(?:symptom\s+complex|presentation|features?)\s+mimicking\s+{_W}{_STOP}", re.I),
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
    r"delayed diagnosis|wrongly diagnosed|masquerad|mimick|mistaken for|"
    r"confused with|initially treated|presumed|working diagnosis",
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
    "hemophagocytic lymphohistiocytosis", "HLH",
    "intestinal pseudo-obstruction", "Kikuchi-Fujimoto disease", "KFD",
    "visceral leishmaniasis", "leishmaniasis", "rosacea",
    "pustular psoriasis", "pyrexia of unknown origin",
    "appendicitis", "malakoplakia",
    "parvovirus B19", "endocarditis", "hepatitis", "HIV", "Epstein-Barr virus",
    "cytomegalovirus", "CMV", "Borrelia", "Lyme disease", "toxoplasmosis",
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

    # A case report whose own target disease is explicitly excluded, or only
    # ever name-dropped in a generic differential list, invalidates the
    # entire disease-scoping premise for this record — don't extract
    # anything, regardless of which patterns would otherwise fire.
    if _target_disease_excluded(abstract, disease) or _target_disease_unconfirmed(
        abstract, disease
    ):
        return [], "none"

    found: list[str] = []

    for pat in HIGH_CONFIDENCE:
        for m in pat.finditer(abstract):
            raw = m.group(1)
            entity = _clean_entity(raw)
            if (
                entity
                and not _filter_target(entity, disease)
                and entity not in found
                and _ground_entity(entity, abstract)
            ):
                found.append(entity)

    for m in _MASQUERADE.finditer(abstract):
        raw = m.group(1)
        entity = _clean_entity(raw)
        if (
            entity
            and not _filter_target(entity, disease)
            and entity not in found
            and _ground_entity(entity, abstract)
        ):
            found.append(entity)

    if found:
        return found, "high"

    med: list[str] = []
    for pat in MEDIUM_CONFIDENCE:
        for m in pat.finditer(abstract):
            raw = m.group(1)
            entity = _clean_entity(raw)
            if (
                entity
                and not _filter_target(entity, disease)
                and entity not in med
                and _ground_entity(entity, abstract)
            ):
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

def process_records(
    records: list[dict],
    *,
    llm_fn=None,
    refresh: bool = False,
) -> tuple[list[dict], dict[str, int], list[str], list[tuple[str, list[str]]]]:
    """Extract into copies, preserving stronger existing evidence by default."""
    stats = {
        "high": 0, "medium": 0, "gazetteer": 0, "llm": 0,
        "signal_only": 0, "none": 0, "no_abstract": 0,
        "preserved": 0, "llm_error": 0,
    }
    signal_only_pmids: list[str] = []
    extracted_examples: list[tuple[str, list[str]]] = []
    updated: list[dict] = []

    for rec in records:
        r = deepcopy(rec)
        abstract = r.get("abstract", "")
        disease = r.get("disease", "")
        scoping_invalid = bool(abstract) and (
            _target_disease_excluded(abstract, disease)
            or _target_disease_unconfirmed(abstract, disease)
        )
        prior_candidates = [
            entity
            for entity in (r.get("misdiagnosis_sequence") or [])
            if not _filter_target(entity, disease) and _clean_entity(entity) is not None
        ]
        # Re-validate every pre-existing (including legacy/unreviewed) entity
        # against the abstract on every run, and void the whole prior
        # sequence outright if this record's disease-scoping is invalid.
        # Without this, provenance-preservation would let stale bad data
        # (e.g. PMID 41996261's "idmcd", 42112145's scoping mismatch) survive
        # forever just because it ranks above a fresh "none" result.
        prior = (
            []
            if scoping_invalid
            else [e for e in prior_candidates if _ground_entity(e, abstract)]
        )
        # Legacy rows are candidates, not reviewed truth. They survive a
        # no-signal rerun but can be replaced by fresh regex/gazetteer evidence.
        prior_level = r.get("misdiagnosis_provenance") or (
            "legacy_unreviewed" if prior else "none"
        )

        if not abstract or len(abstract) < 30:
            stats["no_abstract"] += 1
            seqs, level = [], "none"
        else:
            seqs, level = extract(abstract, disease)

        if level == "signal_only" and llm_fn is not None:
            try:
                llm_seqs = llm_fn(abstract, disease)
            except Exception as exc:  # noqa: BLE001 - surfaced and counted below
                stats["llm_error"] += 1
                print(
                    f"LLM_ASSIST_ERROR PMID {r.get('pubmed_id', '?')}: {exc}",
                    file=sys.stderr,
                )
                llm_seqs = []
            llm_seqs = [e for e in llm_seqs if not _filter_target(e, disease)]
            if llm_seqs:
                seqs, level = llm_seqs, "llm"

        preserve_prior = (
            bool(prior)
            and not refresh
            and _EVIDENCE_RANK.get(str(prior_level), 1) > _EVIDENCE_RANK.get(level, 0)
        )
        if preserve_prior:
            seqs, level = prior, str(prior_level)
            r["misdiagnosis_provenance"] = level
            stats["preserved"] += 1
        else:
            changed = (
                seqs != prior
                or level != str(prior_level)
                or "misdiagnosis_provenance" not in r
            )
            r["misdiagnosis_sequence"] = seqs
            r["misdiagnosis_provenance"] = level
            if changed:
                r["misdiagnosis_extracted_at"] = datetime.now(timezone.utc).isoformat()

        if level in stats:
            stats[level] += 1
        elif preserve_prior:
            pass
        if level == "signal_only":
            signal_only_pmids.append(str(r.get("pubmed_id", "")))
        if seqs:
            r["misdiagnosis_sequence"] = seqs
            extracted_examples.append((str(r.get("pubmed_id", "")), seqs))
        elif not preserve_prior:
            r["misdiagnosis_sequence"] = []
        updated.append(r)

    return updated, stats, signal_only_pmids, extracted_examples


def atomic_write_jsonl(path: Path, rows: list[dict]) -> None:
    """Replace a JSONL only after a complete same-directory temporary write."""
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("jsonl", help="Path to processed JSONL (e.g. data/nlp/processed/sle_case_reports.jsonl)")
    parser.add_argument("--dry-run", action="store_true", help="Print report without writing to disk")
    parser.add_argument(
        "--llm-assist",
        action="store_true",
        help="For KEYWORD_NO_ENTITY (signal_only) rows, ask Ollama to extract named wrong diagnoses",
    )
    parser.add_argument(
        "--llm-model",
        default="qwen2.5:14b",
        help="Ollama model for --llm-assist (default: qwen2.5:14b primary)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Deliberately replace stronger existing sequences with this run's result",
    )
    args = parser.parse_args()

    path = Path(args.jsonl)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 1

    llm_fn = None
    if args.llm_assist:
        from nlp.llm_assist import llm_extract_wrong_diagnoses

        llm_fn = lambda abstract, disease: llm_extract_wrong_diagnoses(  # noqa: E731
            abstract, disease, model=args.llm_model
        )

    records: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    updated, stats, signal_only_pmids, extracted_examples = process_records(
        records, llm_fn=llm_fn, refresh=args.refresh
    )

    # ── report ────────────────────────────────────────────────────────────────
    total = len(records)
    populated = sum(bool(r.get("misdiagnosis_sequence")) for r in updated)
    print(f"\n{'='*60}")
    print(f"Misdiagnosis extraction — {path.name}")
    print(f"{'='*60}")
    print(f"  Total records      : {total}")
    print(f"  No abstract        : {stats['no_abstract']}")
    print(f"  High-confidence    : {stats['high']:>3}  (keyword + named entity extracted)")
    print(f"  Medium-confidence  : {stats['medium']:>3}  (semantic indicator + entity)")
    print(f"  Gazetteer          : {stats['gazetteer']:>3}  (keyword + known SLE-mimic name matched)")
    print(f"  LLM-assist         : {stats['llm']:>3}  (signal_only resolved by Ollama)")
    print(f"  Preserved existing : {stats['preserved']:>3}  (stronger prior evidence kept)")
    print(f"  LLM failures       : {stats['llm_error']:>3}  (surfaced; prior data retained)")
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
    atomic_write_jsonl(path, updated)
    print(f"Written: {path}  ({total} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
