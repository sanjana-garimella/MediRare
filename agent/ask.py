#!/usr/bin/env python3
"""
Thin MediRare cite/abstain agent over hybrid RAG + Ollama.

Usage:
    python3 agent/ask.py --query "What infection is confused with SLE pleural effusion?"
    python3 agent/ask.py --query "Five-year survival of Castleman in Japan?"   # should abstain
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.retrieve import retrieve  # noqa: E402
from rag.chunk import sentence_split  # noqa: E402

SYSTEM = (
    "You are MediRare's internal research assistant for case-report extraction. "
    "Answer ONLY from the provided chunks, and ONLY the parts of each chunk that "
    "directly answer the query, do not narrate unrelated details from a chunk "
    "just because it was retrieved. "
    "Describe evidence as 'a selected case report described ...'; never generalize "
    "to patients, prevalence, risk, commonness, causality, diagnostic advice, "
    "treatment advice, or what clinicians should do. "
    "If a chunk is only tangentially related to the query, omit it rather than "
    "including it for coverage. "
    "Every sentence MUST end with a citation like [chunk_id] using an id from the provided set. "
    "If the chunks do not support an answer, reply with exactly: INSUFFICIENT_EVIDENCE "
    "Do not use outside medical knowledge."
)

PRIMARY_MODEL = "qwen2.5:14b"
BACKUP_MODEL = "llama3.1:8b"
MEDICAL_MODEL = "meditron:7b"
# meditron:7b does not reliably follow the verification instruction format in
# this deployment — live testing showed it echoes the prompt or hallucinates
# unrelated content instead of grading (0/5 parseable replies). llama3.1:8b is
# used instead: it is a genuinely independent model from the primary answerer
# (so it isn't just grading its own homework) and reliably follows the format.
VERIFY_MODEL = BACKUP_MODEL


def ollama_chat(model: str, system: str, user: str, timeout: int = 180) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.1, "num_predict": 512},
    }
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    return (data.get("message") or {}).get("content") or ""


def format_user(query: str, chunks: list[dict]) -> str:
    lines = [f"Query: {query}", "", "Chunks:"]
    for c in chunks:
        context = (c.get("context") or "").strip()
        body = (c.get("body") or c.get("text") or "").strip()
        lines.append(f"- [{c['chunk_id']}]: {context} {body}".strip())
    lines.append("")
    lines.append("Respond per system rules.")
    return "\n".join(lines)


def extract_citations(text: str) -> list[str]:
    cites = re.findall(r"\[([^\[\]]+?)\]", text)
    normed = []
    for c in cites:
        c2 = c.strip()
        if c2.lower().startswith("chunk_id:"):
            c2 = c2.split(":", 1)[1].strip()
        normed.append(c2)
    return normed


def validate_answer(answer: str, allowed_ids: set[str]) -> dict:
    """Retain only sentences carrying at least one citation from this retrieval."""
    text = (answer or "").strip()
    upper = re.sub(r"[\s_]+", "", text.upper())
    if "INSUFFICIENTEVIDENCE" in upper:
        return {
            "status": "abstained",
            "answer": "INSUFFICIENT_EVIDENCE",
            "citations": [],
            "stripped": [],
        }

    invented = list(dict.fromkeys(c for c in extract_citations(text) if c not in allowed_ids))
    retained = []
    # Keep line/bullet boundaries: flattening them lets one citation on a prior
    # line incorrectly validate the next claim. Semicolon-separated clauses are
    # also independent claims for citation purposes.
    for line in text.splitlines() or [text]:
        line = re.sub(r"^\s*(?:[-*•‣◦▪▫●○]|\d+[.)])\s*", "", line).strip()
        if not line:
            continue
        for sentence in sentence_split(line):
            for claim in (part.strip() for part in re.split(r"\s*;\s*", sentence)):
                if not claim:
                    continue
                sentence_cites = extract_citations(claim)
                # Mixed valid/invalid citations make the claim ambiguous; fail
                # closed instead of stripping only the fabricated marker.
                if (
                    not sentence_cites
                    or any(c not in allowed_ids for c in sentence_cites)
                ):
                    continue
                prose = re.sub(r"\[[^\[\]]+?\]", "", claim)
                if not re.search(r"[A-Za-z0-9]", prose):
                    continue
                retained.append(re.sub(r"\s+([,.;!?])", r"\1", claim).strip())
    cleaned_text = " ".join(retained).strip()
    valid = list(dict.fromkeys(c for c in extract_citations(cleaned_text) if c in allowed_ids))

    if not valid:
        return {
            "status": "abstained",
            "answer": "INSUFFICIENT_EVIDENCE",
            "citations": [],
            "stripped": invented,
        }
    return {
        "status": "answered",
        "answer": cleaned_text,
        "citations": valid,
        "stripped": invented,
    }


def _canonical_tokens(text: str) -> set[str]:
    """Tokenize clinical text while collapsing a small controlled alias set."""
    # Typographic apostrophes (U+2019/U+2018, common in PubMed abstracts —
    # "Sjögren's") must become a plain "'" before NFKD/ascii-encoding, which
    # otherwise silently drops them and breaks the "(?:'s)?" phrase-alias
    # patterns below, leaking a spurious extra "syndrome" token instead of
    # collapsing the whole phrase to its short alias.
    text = (text or "").replace("\u2019", "'").replace("\u2018", "'")
    normalized = unicodedata.normalize("NFKD", text)
    normalized = normalized.encode("ascii", "ignore").decode().lower()
    phrase_aliases = {
        r"\bmixed connective tissue disease\b": " mctd ",
        r"\bneuromyelitis optica spectrum disorder\b": " nmosd ",
        r"\brheumatoid arthritis\b": " ra ",
        r"\bsystemic lupus erythematosus\b": " sle ",
        r"\bsjogren(?:'s)? syndrome\b": " sjogren ",
        r"\btuberculosis\b": " tb ",
    }
    for pattern, replacement in phrase_aliases.items():
        normalized = re.sub(pattern, replacement, normalized)
    token_aliases = {
        "lupus": "sle",
        "sjogrens": "sjogren",
        "tubercular": "tb",
        "tuberculous": "tb",
    }
    return {
        token_aliases.get(token, token)
        for token in re.findall(r"[a-z0-9]+", normalized)
    }


def grade_evidence(query: str, chunks: list[dict]) -> float:
    """Best-chunk lexical coverage over body text, excluding generic terms."""
    if not chunks:
        return 0.0
    stopwords = {
        "the", "and", "for", "with", "from", "that", "this", "what", "which",
        "who", "how", "was", "were", "are", "case", "report", "patient",
        "diagnosis", "diagnosed", "misdiagnosis", "mimic", "wrong", "initial",
        "example", "query", "function", "return", "python", "docstring",
    }
    q_terms = {
        token
        for token in _canonical_tokens(query)
        if token not in stopwords and (len(token) > 2 or token in {"tb", "ra"})
    }
    if not q_terms:
        return 0.0
    scores: list[float] = []
    for c in chunks:
        body = c.get("body")
        if body is None:
            body = re.sub(
                r"^This chunk from .*? case report \S+ describes .*?\.\s*",
                "",
                c.get("text") or "",
                count=1,
                flags=re.I,
            )
        words = _canonical_tokens(body)
        hit = sum(1 for t in q_terms if t in words)
        scores.append(hit / len(q_terms))
    return float(max(scores, default=0.0))


def _error_result(
    code: str,
    message: str,
    *,
    model: str,
    hops: list[dict] | None = None,
    grade: float = 0.0,
) -> dict:
    return {
        "status": "error",
        "answer": "SERVICE_UNAVAILABLE",
        "citations": [],
        "stripped": [],
        "grade": grade,
        "hops": hops or [],
        "model": model,
        "verify": None,
        "error": {"code": code, "message": message},
    }


def rewrite_query(query: str, model: str) -> str:
    prompt = (
        "Rewrite this clinical retrieval query to be more specific about "
        "misdiagnosis / mimic / wrong initial diagnosis. Return only the rewritten query.\n\n"
        f"Query: {query}"
    )
    try:
        out = ollama_chat(model, "You rewrite search queries. No commentary.", prompt, timeout=60)
    except Exception:  # noqa: BLE001
        return query
    line = (out or "").strip().splitlines()[0].strip()
    return line or query


def verify_claims(answer: str, chunks: list[dict], model: str = VERIFY_MODEL) -> dict:
    """Optional fail-closed consistency signal; not medical verification.

    Distinguishes two distinct failure modes so callers/UI never conflate
    them: a verifier that could not be reached or produced no parseable
    grade ("reason": "unparseable"/"exception") vs. a verifier that ran
    successfully and reported the answer isn't fully supported
    ("reason": "graded"). Both fail closed (ok=False), but only "graded"
    reflects an actual judgment about the answer's content.
    """
    if answer.strip() == "INSUFFICIENT_EVIDENCE":
        return {"ok": True, "support": 1.0, "reason": "abstained", "detail": "abstained"}
    blob = "\n".join(f"[{c['chunk_id']}] {c['text']}" for c in chunks[:8])
    user = (
        "For each sentence in ANSWER, say SUPPORT or UNSUPPORTED based only on CHUNKS. "
        "End with a line SUPPORT_FRACTION=x.xx\n\n"
        f"CHUNKS:\n{blob}\n\nANSWER:\n{answer}"
    )
    try:
        reply = ollama_chat(
            model,
            "You verify medical claims against provided chunks only.",
            user,
            timeout=120,
        )
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "support": None, "reason": "exception", "detail": f"verify_failed:{e}"}
    m = re.search(r"SUPPORT_FRACTION\s*=\s*([0-9.]+)", reply or "", re.I)
    frac = float(m.group(1)) if m else None
    if frac is None:
        return {"ok": False, "support": None, "reason": "unparseable", "detail": (reply or "")[:500]}
    ok = frac >= 1.0
    return {"ok": ok, "support": frac, "reason": "graded", "detail": (reply or "")[:500]}


def ask(
    query: str,
    *,
    index_dir: Path = Path("data/rag/index"),
    model: str = PRIMARY_MODEL,
    backup: str = BACKUP_MODEL,
    max_hops: int = 3,
    grade_threshold: float = 0.4,
    verify: bool = False,
    allow_unreviewed: bool = False,
) -> dict:
    hops = []
    q = query
    chunks: list[dict] = []
    grade = 0.0
    best_chunks: list[dict] = []
    best_grade = -1.0
    best_query = query
    # Only conclude "no clinician-reviewed evidence exists at all" after
    # every hop (including rewritten-query hops) comes back empty. A single
    # hop with zero reviewed chunks doesn't mean a later, rewritten query
    # can't find any — short-circuiting on hop 1 alone defeats the CRAG loop.
    any_hop_had_reviewed_evidence = False
    for hop in range(1, max_hops + 1):
        try:
            chunks = retrieve(q, index_dir, candidates=150, top=20)
        except Exception as exc:  # noqa: BLE001 - index backends raise varied errors
            return _error_result(
                "retrieval_index_unavailable",
                str(exc),
                model=model,
                hops=hops,
                grade=max(best_grade, 0.0),
            )
        if not allow_unreviewed:
            chunks = [c for c in chunks if c.get("review_status") == "reviewed"]
        if chunks:
            any_hop_had_reviewed_evidence = True
        grade = grade_evidence(q, chunks) if chunks else 0.0
        hops.append({"hop": hop, "query": q, "grade": round(grade, 3), "n_chunks": len(chunks)})
        if grade > best_grade:
            best_grade, best_chunks, best_query = grade, chunks, q
        if grade >= grade_threshold:
            break
        if hop < max_hops:
            q = rewrite_query(q, model)

    if not allow_unreviewed and not any_hop_had_reviewed_evidence:
        return {
            "status": "abstained",
            "answer": "INSUFFICIENT_EVIDENCE",
            "citations": [],
            "stripped": [],
            "grade": 0.0,
            "hops": hops,
            "model": model,
            "verify": None,
            "evidence_status": "no_clinician_reviewed_evidence",
        }

    chunks, grade, q = best_chunks, max(best_grade, 0.0), best_query
    if grade < grade_threshold:
        return {
            "status": "abstained",
            "answer": "INSUFFICIENT_EVIDENCE",
            "citations": [],
            "stripped": [],
            "grade": grade,
            "hops": hops,
            "model": model,
            "verify": None,
        }

    allowed = {c["chunk_id"] for c in chunks}
    user = format_user(query, chunks)
    try:
        raw = ollama_chat(model, SYSTEM, user)
    except Exception as primary_exc:  # noqa: BLE001
        try:
            raw = ollama_chat(backup, SYSTEM, user)
            model = backup
        except Exception as backup_exc:  # noqa: BLE001
            return _error_result(
                "ollama_unavailable",
                f"primary failed: {primary_exc}; backup failed: {backup_exc}",
                model=model,
                hops=hops,
                grade=grade,
            )

    validated = validate_answer(raw, allowed)
    verified = verify_claims(validated["answer"], chunks) if verify else None
    if verified and not verified.get("ok", True):
        validated = {
            "status": "abstained",
            "answer": "INSUFFICIENT_EVIDENCE",
            "citations": [],
            "stripped": validated.get("stripped", []),
            "evidence_status": (
                "verifier_unavailable"
                if verified.get("reason") in ("unparseable", "exception")
                else "verifier_rejected"
            ),
        }

    return {
        **validated,
        "grade": grade,
        "hops": hops,
        "model": model,
        "verify": verified,
        "raw": raw,
        "chunks_used": [c["chunk_id"] for c in chunks[:20]],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query", required=True)
    ap.add_argument("--index", default="data/rag/index")
    ap.add_argument("--model", default=PRIMARY_MODEL)
    ap.add_argument("--backup", default=BACKUP_MODEL)
    ap.add_argument(
        "--verify",
        action="store_true",
        help=(
            f"Run experimental cross-model consistency check via {VERIFY_MODEL} "
            "(not medical verification)"
        ),
    )
    ap.add_argument(
        "--allow-unreviewed",
        action="store_true",
        help="Internal research only: permit generation from unreviewed case-report chunks",
    )
    ap.add_argument("--json", action="store_true", help="Print full JSON result")
    args = ap.parse_args()

    result = ask(
        args.query,
        index_dir=Path(args.index),
        model=args.model,
        backup=args.backup,
        verify=args.verify,
        allow_unreviewed=args.allow_unreviewed,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"status={result['status']} model={result['model']} grade={result['grade']}")
        print(result["answer"])
        if result.get("citations"):
            print("citations:", ", ".join(result["citations"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
