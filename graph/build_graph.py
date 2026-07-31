#!/usr/bin/env python3
"""
Build a misdiagnosis knowledge graph from extracted sequences.

Usage:
    python3 graph/build_graph.py \
        --jsonl data/nlp/processed/sle_case_reports.jsonl \
                data/nlp/processed/sjogrens_case_reports.jsonl \
                data/nlp/processed/mctd_case_reports.jsonl \
        --out data/graph/misdiagnosis_graph.json

Nodes: target disease + reviewed/candidate wrong-diagnosis labels
Edges: target_disease --was_misdiagnosed_as--> wrong_dx (with PMID evidence)

The default graph includes only explicitly reviewed, direction-annotated rows.
Use --include-unreviewed only to build a separately labelled annotation queue.
"""
from __future__ import annotations

import argparse
import json
import unicodedata
from collections import defaultdict
from pathlib import Path

import networkx as nx


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def normalize_label(s: str) -> str:
    text = unicodedata.normalize("NFKD", s or "")
    text = text.encode("ascii", "ignore").decode().lower()
    text = " ".join(text.replace("’", "'").strip().split())
    aliases = {
        "systemic lupus erythematosus": "sle",
        "lupus": "sle",
        "neuropsychiatric systemic lupus erythematosus": "sle",
        "npsle": "sle",
        "sjogren syndrome": "sjogrens",
        "sjogren's syndrome": "sjogrens",
        "primary sjogren syndrome": "sjogrens",
        "primary sjogren's syndrome": "sjogrens",
        "mixed connective tissue disease": "mctd",
        "kfd": "kikuchi-fujimoto disease",
        "nmosd": "neuromyelitis optica spectrum disorder",
        "aps": "antiphospholipid syndrome",
        "primary aps": "antiphospholipid syndrome",
        "tb": "tuberculosis",
    }
    return aliases.get(text, text)


def _add_role(g: nx.DiGraph, node: str, role: str) -> None:
    current = set(filter(None, (g.nodes[node].get("roles") or "").split("|"))) if node in g else set()
    current.add(role)
    if node not in g:
        g.add_node(node)
    g.nodes[node]["roles"] = "|".join(sorted(current))


def build_graph(records: list[dict], *, include_unreviewed: bool = False) -> nx.DiGraph:
    """Build disease -> candidate wrong-diagnosis edges.

    The public/default graph is fail-closed: only explicitly reviewed records
    with an explicit relation direction are admitted. ``include_unreviewed`` is
    for a separately-labelled candidate artifact used during annotation.
    """
    g = nx.DiGraph()
    # edge key -> list of pmids
    edge_pmids: dict[tuple[str, str], list[str]] = defaultdict(list)

    for r in records:
        disease = normalize_label(r.get("disease") or "unknown")
        pmid = str(r.get("pubmed_id") or "")
        seqs = r.get("misdiagnosis_sequence") or []
        reviewed = (
            r.get("misdiagnosis_provenance") == "reviewed"
            and r.get("misdiagnosis_review_status") == "reviewed"
            and r.get("misdiagnosis_relation") == "target_was_misdiagnosed_as_entity"
        )
        if not reviewed and not include_unreviewed:
            continue
        if not seqs or not pmid:
            continue
        _add_role(g, disease, "target_disease")
        for wrong in seqs:
            w = normalize_label(wrong)
            if not w or w == disease:
                continue
            _add_role(g, w, "candidate_wrong_diagnosis" if not reviewed else "wrong_diagnosis")
            edge_pmids[(disease, w)].append(pmid)

    for (src, dst), pmids in edge_pmids.items():
        uniq = sorted(set(pmids))
        g.add_edge(
            src,
            dst,
            pmids=uniq,
            weight=len(uniq),
            relation="candidate_misdiagnosed_as" if include_unreviewed else "was_misdiagnosed_as",
            review_status="unreviewed_candidate" if include_unreviewed else "reviewed",
        )
    return g


def graph_to_json(g: nx.DiGraph) -> dict:
    return {
        "n_nodes": g.number_of_nodes(),
        "n_edges": g.number_of_edges(),
        "nodes": [{"id": n, **g.nodes[n]} for n in g.nodes],
        "edges": [
            {
                "source": u,
                "target": v,
                "relation": d.get("relation"),
                "weight": d.get("weight"),
                "pmids": d.get("pmids", []),
            }
            for u, v, d in g.edges(data=True)
        ],
    }


def top_confusion_partners(g: nx.DiGraph, disease: str, k: int = 10) -> list[tuple[str, int, list[str]]]:
    disease = normalize_label(disease)
    partners = []
    for u, v, d in g.out_edges(disease, data=True):
        partners.append((v, int(d.get("weight") or 0), d.get("pmids") or []))
    partners.sort(key=lambda x: x[1], reverse=True)
    return partners[:k]


def most_common_wrong_dx(g: nx.DiGraph, k: int = 15) -> list[tuple[str, int]]:
    scores: dict[str, int] = defaultdict(int)
    for u, v, d in g.edges(data=True):
        if "wrong_diagnosis" in (g.nodes[v].get("roles") or ""):
            scores[v] += int(d.get("weight") or 0)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jsonl", nargs="+", required=True)
    ap.add_argument("--out", default="data/graph/misdiagnosis_graph.json")
    ap.add_argument("--query-disease", default="", help="Print top confusion partners for this disease")
    ap.add_argument(
        "--include-unreviewed",
        action="store_true",
        help="Build a clearly labelled candidate graph; never use as validated findings",
    )
    args = ap.parse_args()

    records: list[dict] = []
    for p in args.jsonl:
        records.extend(load_jsonl(Path(p)))

    g = build_graph(records, include_unreviewed=args.include_unreviewed)
    payload = graph_to_json(g)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    # GraphML cannot store lists — stringify pmids for the .graphml sidecar
    g_ml = g.copy()
    for u, v, d in g_ml.edges(data=True):
        d["pmids"] = ",".join(d.get("pmids") or [])
    nx.write_graphml(g_ml, out.with_suffix(".graphml"))

    print(f"Graph: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges → {out}")
    print("Most common wrong diagnoses:")
    for name, w in most_common_wrong_dx(g, 10):
        print(f"  {w:3d}  {name}")

    if args.query_disease:
        print(f"\nTop confusion partners for {args.query_disease}:")
        for name, w, pmids in top_confusion_partners(g, args.query_disease):
            print(f"  {w:3d}  {name}  pmids={pmids[:5]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
