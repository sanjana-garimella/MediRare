"""Ollama helper for misdiagnosis extraction assist (KEYWORD_NO_ENTITY cases)."""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.request

DEFAULT_MODEL = "qwen2.5:14b"  # primary; structured following beats meditron on bake-off
_VAGUE_ENTITIES = {
    "infection", "disease", "condition", "autoimmune disease", "malignancy",
    "cancer", "syndrome", "inflammatory condition", "other conditions",
}
_RELATION_SIGNAL = re.compile(
    r"misdiagnos|diagnos|treated|mistaken|confused|thought|suspect|presum|mimic|masquerad",
    re.I,
)
_NEGATED = re.compile(
    r"\b(?:excluded|ruled out|not supported|no evidence of|negative for|unlikely)\b",
    re.I,
)

_SYSTEM = (
    "You extract wrong diagnoses from clinical case-report abstracts. "
    "Return ONLY a JSON array of lowercase disease/condition names that were "
    "incorrectly diagnosed or treated as before the true diagnosis. "
    "Do NOT include the true/final diagnosis. "
    "Do NOT include symptoms, labs, or vague phrases. "
    "If no named wrong diagnosis appears, return []."
)


def ollama_chat(model: str, system: str, user: str, timeout: int = 120) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 128},
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


def parse_entity_list(text: str) -> list[str]:
    text = text.strip()
    # Prefer fenced or raw JSON array
    m = re.search(r"\[[^\]]*\]", text, re.S)
    if not m:
        return []
    try:
        raw = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out: list[str] = []
    if not isinstance(raw, list):
        return []
    for item in raw:
        if not isinstance(item, str):
            continue
        e = item.strip().lower().strip(" .,;-")
        if 3 <= len(e) <= 80 and e not in _VAGUE_ENTITIES and e not in out:
            out.append(e)
    return out


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


_NEGATION_WINDOW = 1  # sentences after the mention to also scan for a delayed exclusion


def ground_entities(entities: list[str], abstract: str) -> list[str]:
    """Keep entities mentioned (with a relation cue) and not negated nearby.

    Negation is checked over the mention sentence plus the next
    `_NEGATION_WINDOW` sentence(s), because case-report abstracts commonly
    state the wrong diagnosis in one sentence and its exclusion in the next
    (e.g. "...initially treated for tuberculosis. This was later excluded
    and the diagnosis was revised to SLE."). Same-sentence negation alone
    misses this idiomatic two-clause pattern.
    """
    sentences = re.split(r"(?<=[.!?])\s+", abstract or "")
    grounded: list[str] = []
    for entity in entities:
        normalized = _normalize(entity)
        if not normalized or entity in _VAGUE_ENTITIES:
            continue
        words = normalized.split()
        acronym = "".join(word[0] for word in words if word)
        aliases = {normalized}
        # Only trust a derived acronym if it actually appears as an
        # upper-case acronym in the source text; otherwise short acronyms
        # like "ten" (toxic epidermal necrolysis) collide with ordinary
        # English words and cause unrelated sentences to false-positive.
        if 2 <= len(acronym) <= 6 and re.search(
            rf"\b{re.escape(acronym.upper())}\b", abstract or ""
        ):
            aliases.add(acronym)
        supported = False
        for i, sentence in enumerate(sentences):
            sentence_norm = f" {_normalize(sentence)} "
            mentioned = any(f" {alias} " in sentence_norm for alias in aliases)
            if not (mentioned and _RELATION_SIGNAL.search(sentence)):
                continue
            window = sentences[i : i + 1 + _NEGATION_WINDOW]
            if any(_NEGATED.search(s) for s in window):
                continue
            supported = True
            break
        if supported and entity not in grounded:
            grounded.append(entity)
    return grounded


def llm_extract_wrong_diagnoses(
    abstract: str,
    disease: str,
    model: str = DEFAULT_MODEL,
) -> list[str]:
    user = (
        f"True disease context: {disease}\n\n"
        f"Abstract:\n{abstract[:2500]}\n\n"
        "JSON array of wrong diagnoses only:"
    )
    reply = ollama_chat(model, _SYSTEM, user)
    return ground_entities(parse_entity_list(reply), abstract)
