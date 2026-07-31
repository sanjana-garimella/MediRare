#!/usr/bin/env python3
"""Grounded cite/abstain bake-off against local Ollama models."""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = Path(__file__).resolve().parent / "eval_items.json"
OUT_DIR = Path(__file__).resolve().parent / "runs"


def chat(model: str, system: str, user: str, timeout: int = 300, think: bool | None = False) -> tuple[str, float]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 512},
    }
    # Qwen3 / R1-style models fill num_predict with thinking and return empty content
    # unless think is explicitly disabled for the final cited answerer.
    if think is not None:
        payload["think"] = think
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    elapsed = time.time() - t0
    return (data.get("message") or {}).get("content") or "", elapsed


def format_user(item: dict) -> str:
    lines = [f"Query: {item['query']}", "", "Chunks:"]
    for c in item["chunks"]:
        lines.append(f"- [{c['chunk_id']}]: {c['text']}")
    lines.append("")
    lines.append("Respond per system rules.")
    return "\n".join(lines)


def citations(text: str) -> list[str]:
    return re.findall(r"\[([^\[\]]+?)\]", text)


def score_item(item: dict, answer: str) -> dict:
    expect = item["expect"]
    allowed = {c["chunk_id"] for c in item["chunks"]}
    text = (answer or "").strip()
    upper = text.upper()
    abstained = "INSUFFICIENT_EVIDENCE" in upper.replace(" ", "") or text.strip() == "INSUFFICIENT_EVIDENCE"
    # also accept exact phrase with spaces
    if not abstained:
        abstained = "INSUFFICIENT_EVIDENCE" in upper

    cites = citations(text)
    # Normalize malformed cites like "chunk_id: sle_123_c1"
    normed = []
    for c in cites:
        c2 = c.strip()
        if c2.lower().startswith("chunk_id:"):
            c2 = c2.split(":", 1)[1].strip()
        normed.append(c2)
    cites = normed
    invented = [c for c in cites if c not in allowed]
    valid = [c for c in cites if c in allowed]

    # Heuristic claim invention: very light — flag common labs/diseases absent from chunk text
    blob = " ".join(c["text"] for c in item["chunks"]).lower()
    suspicious = []
    for term in [
        "anti-ro",
        "anti-la",
        "cyclophosphamide",
        "rituximab",
        "five-year survival",
        "pediatric",
        "japan",
        "titer cutoff",
    ]:
        if term in text.lower() and term not in blob:
            suspicious.append(term)

    # Per bake-off skill: 5 binary criteria, but we also track per-item pass for /10
    used_only_context = len(suspicious) == 0 and (abstained or len(invented) == 0)
    cites_ok = abstained or (len(cites) > 0 and len(invented) == 0)
    # For answer/join: every sentence-ish should cite — soft check: at least one valid cite if not abstain
    if expect in {"answer", "join"} and not abstained:
        cites_ok = len(valid) > 0 and len(invented) == 0

    abstain_when_needed = (expect == "abstain" and abstained)
    answered_when_needed = (expect in {"answer", "join"} and not abstained and len(valid) > 0)
    no_invented_claims = len(suspicious) == 0

    # Item pass (counts toward /10)
    if expect == "abstain":
        item_pass = abstained and len(invented) == 0
    else:
        item_pass = (not abstained) and cites_ok and no_invented_claims

    return {
        "item_pass": item_pass,
        "abstained": abstained,
        "citations": cites,
        "invented_citations": invented,
        "suspicious_terms": suspicious,
        "checks": {
            "used_only_context": used_only_context,
            "cites_ok": cites_ok,
            "abstain_when_needed": abstain_when_needed if expect == "abstain" else None,
            "answered_when_needed": answered_when_needed if expect != "abstain" else None,
            "no_invented_claims": no_invented_claims,
        },
    }


def run_model(model: str, role: str, data: dict) -> dict:
    results = []
    total_s = 0.0
    for item in data["items"]:
        user = format_user(item)
        try:
            answer, elapsed = chat(model, data["system"], user)
            err = None
        except Exception as e:  # noqa: BLE001
            answer, elapsed, err = "", 0.0, str(e)
        scored = score_item(item, answer) if not err else {
            "item_pass": False,
            "abstained": False,
            "citations": [],
            "invented_citations": [],
            "suspicious_terms": [],
            "checks": {},
            "error": err,
        }
        total_s += elapsed
        results.append({
            "id": item["id"],
            "expect": item["expect"],
            "elapsed_s": round(elapsed, 2),
            "answer": answer,
            **scored,
        })
        print(f"  {item['id']} pass={scored.get('item_pass')} {elapsed:.1f}s", flush=True)

    passed = sum(1 for r in results if r.get("item_pass"))
    return {
        "model": model,
        "role": role,
        "score_over_10": passed,
        "total_elapsed_s": round(total_s, 1),
        "results": results,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True, help="model:role pairs, e.g. qwen2.5:14b:generator")
    ap.add_argument("--out", type=Path, default=OUT_DIR / "summary.json")
    args = ap.parse_args()

    data = json.loads(EVAL.read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summaries = []
    for spec in args.models:
        parts = spec.split(":")
        # model tags like qwen2.5:14b:generator or hf.co/x:medical
        if len(parts) < 2:
            raise SystemExit(f"bad --models entry {spec}")
        role = parts[-1]
        model = ":".join(parts[:-1])
        print(f"\n=== {model} ({role}) ===", flush=True)
        summary = run_model(model, role, data)
        run_path = OUT_DIR / f"{model.replace('/', '_').replace(':', '_')}.json"
        run_path.write_text(json.dumps(summary, indent=2))
        summaries.append({
            "model": model,
            "role": role,
            "score_over_10": summary["score_over_10"],
            "total_elapsed_s": summary["total_elapsed_s"],
            "failure_modes": [
                r["id"] for r in summary["results"] if not r.get("item_pass")
            ],
            "run_path": str(run_path.relative_to(ROOT)),
        })
        print(f"SCORE {summary['score_over_10']}/10 in {summary['total_elapsed_s']}s", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "diseases": data.get("diseases"),
        "models": summaries,
    }, indent=2))
    print("\nWrote", args.out)


if __name__ == "__main__":
    main()
