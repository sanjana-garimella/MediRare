from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


st.set_page_config(page_title="MediRare", layout="wide")
st.title("MediRare — research extraction prototype")
st.warning(
    "Not medical advice or clinical decision support. Case reports are "
    "publication-biased anecdotes; current labels and candidate relations are "
    "AI-extracted and not clinician-reviewed. Counts are not prevalence, risk, "
    "causality, or diagnostic recommendations. A citation proves source "
    "provenance only—not clinical correctness."
)
show_unreviewed = st.checkbox(
    "Enable unreviewed research outputs",
    value=False,
    help="For internal inspection only. Do not use for patient care.",
)

tab_ask, tab_graph, tab_data = st.tabs(["Ask", "Knowledge graph", "Merged records"])

with tab_ask:
    st.caption("Cite/abstain agent over hybrid RAG (Ollama `qwen2.5:14b`). Requires local Ollama + built index.")
    q = st.text_input("Question", placeholder="What infection is confused with SLE pleural effusion?")
    verify = st.checkbox(
        "Experimental cross-model consistency check via llama3.1:8b "
        "(not medical verification)",
        value=False,
    )
    if st.button("Ask", type="primary") and q.strip():
        index = ROOT / "data/rag/index"
        if not ((index / "CURRENT").exists() or (index / "meta.json").exists()):
            st.error("Missing data/rag/index — run scripts/e2e.sh or rag/index.py first.")
        else:
            with st.spinner("Retrieving + generating..."):
                from agent.ask import ask

                # Always call ask(); its own reviewed-evidence gate decides
                # whether to abstain. The checkbox only controls whether
                # unreviewed evidence is permitted, never bypasses ask().
                result = ask(
                    q.strip(),
                    index_dir=index,
                    verify=verify,
                    allow_unreviewed=show_unreviewed,
                )
            if result["status"] == "error":
                error = result.get("error") or {}
                st.error(
                    f"{error.get('code', 'service_error')}: "
                    f"{error.get('message', 'The service is unavailable.')}"
                )
            elif result.get("evidence_status") == "no_clinician_reviewed_evidence":
                st.info(
                    "Abstained: no clinician-reviewed evidence is available for this "
                    "query yet. Check 'Enable unreviewed research outputs' above to "
                    "inspect unreviewed candidate evidence instead (internal use only)."
                )
            elif result.get("evidence_status") == "verifier_unavailable":
                st.warning(
                    "Abstained: the consistency-check model did not return a usable "
                    "grade (not necessarily a bad answer — the checker itself failed). "
                    "Try again with verification off to see the underlying answer."
                )
            elif result.get("evidence_status") == "verifier_rejected":
                st.info(
                    "Abstained: the cross-model consistency check flagged this answer "
                    "as not fully supported by the retrieved evidence."
                )
            else:
                st.write(f"**Status:** `{result['status']}` · model `{result['model']}` · grade `{result['grade']:.2f}`")
                st.markdown(result["answer"])
                if result.get("citations"):
                    st.write("Citations:", ", ".join(f"`{c}`" for c in result["citations"]))
            with st.expander("Hops / debug"):
                st.json({"hops": result.get("hops"), "stripped": result.get("stripped"), "verify": result.get("verify")})

with tab_graph:
    reviewed_path = ROOT / "data/graph/misdiagnosis_graph.json"
    candidate_path = ROOT / "data/graph/candidate_misdiagnosis_graph.json"
    graph_path = candidate_path if show_unreviewed else reviewed_path
    if show_unreviewed:
        st.caption(
            "Showing the **candidate** graph (includes unreviewed edges) because "
            "'Enable unreviewed research outputs' is checked above. Internal use only."
        )
    else:
        st.caption(
            "Showing the clinician-reviewed graph only. Check 'Enable unreviewed "
            "research outputs' above to also see unreviewed candidate relations."
        )
    if not graph_path.exists():
        fallback = reviewed_path if show_unreviewed else candidate_path
        st.warning(
            f"Missing {graph_path.relative_to(ROOT)}. Run graph/build_graph.py "
            f"({'add --include-unreviewed' if show_unreviewed else ''}) — see scripts/e2e.sh."
        )
        graph_path = fallback if fallback.exists() else None
    if graph_path and graph_path.exists():
        g = json.loads(graph_path.read_text())
        st.write(f"**{g['n_nodes']} nodes · {g['n_edges']} edges**")
        edges = sorted(g["edges"], key=lambda e: e.get("weight") or 0, reverse=True)
        if not edges:
            st.info("No explicitly clinician-reviewed relations are available yet.")
        df_e = pd.DataFrame(
            [
                {
                    "target_disease": e["source"],
                    "wrong_diagnosis": e["target"],
                    "report_count": e.get("weight"),
                    "review_status": e.get("review_status"),
                    "pmids": ", ".join((e.get("pmids") or [])[:5]),
                }
                for e in edges[:50]
            ]
        )
        st.dataframe(df_e, use_container_width=True, hide_index=True)

with tab_data:
    data_path = ROOT / "integration/merged_records.jsonl"
    if not data_path.exists():
        st.warning("Missing integration/merged_records.jsonl. Run: python3 integration/merge.py --real")
    else:
        st.caption(
            "`annotation_status` — how misdiagnosis_sequence was produced: "
            "`high`/`medium`/`gazetteer` = regex/keyword pattern matched a named "
            "wrong diagnosis; `llm` = Ollama-assisted extraction; "
            "`legacy_unreviewed` = older candidate data, re-validated against the "
            "abstract on every run but not clinician-reviewed; `signal_only` = a "
            "misdiagnosis keyword was found but no entity could be extracted; "
            "`none`/`unreviewed` = no misdiagnosis signal detected. None of these "
            "values mean clinician-reviewed — only `reviewed` (not yet present in "
            "this dataset) would."
        )
        records = load_jsonl(data_path)
        df = pd.DataFrame(
            [
                {
                    "pubmed_id": r.get("pubmed_id"),
                    "disease": r.get("disease"),
                    "has_case_report": r.get("case_report") is not None,
                    "misdiagnosis_sequence": ", ".join(
                        ((r.get("case_report") or {}).get("misdiagnosis_sequence") or [])[:5]
                    ),
                    "annotation_status": (
                        (r.get("case_report") or {}).get("misdiagnosis_provenance")
                        or "unreviewed"
                    ),
                    "figure_count": len(r.get("figures") or []),
                }
                for r in records
            ]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
