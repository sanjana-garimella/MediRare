from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

D3_JS = (ROOT / "demo/static/d3.v7.min.js").read_text(encoding="utf-8")


def render_force_graph(edges: list[dict], disease_colors: list[str]) -> str:
    """Collapsible D3 force-directed graph: disease hubs expand on click to
    reveal the diagnoses they were confused with. All client-side (drag,
    zoom, expand/collapse) so no Streamlit rerun is needed for interaction.
    """
    diseases = sorted({e["source"] for e in edges})
    nodes = [{"id": d, "type": "disease", "color": disease_colors[i % len(disease_colors)]}
              for i, d in enumerate(diseases)]
    MAX_CHILDREN_PER_DISEASE = 20
    # wrong_dx nodes are keyed by diagnosis label alone (not per-disease), so a
    # diagnosis that multiple diseases were confused with (e.g. "multiple
    # sclerosis" for both Sjogren's and MCTD) renders as one shared node with
    # edges to each disease, surfacing the cross-disease overlap.
    children: dict[str, list[dict]] = {d: [] for d in diseases}
    seen_wrong_dx: set[str] = set()
    edges_by_disease: dict[str, list[dict]] = {d: [] for d in diseases}
    for e in edges:
        edges_by_disease[e["source"]].append(e)
    for disease, disease_edges in edges_by_disease.items():
        top_edges = sorted(disease_edges, key=lambda e: e.get("weight") or 0, reverse=True)[:MAX_CHILDREN_PER_DISEASE]
        for e in top_edges:
            wrong_dx, weight = e["target"], e.get("weight") or 1
            if wrong_dx not in seen_wrong_dx:
                nodes.append({"id": wrong_dx, "type": "wrong_dx", "label": wrong_dx})
                seen_wrong_dx.add(wrong_dx)
            children[disease].append({"id": wrong_dx, "weight": weight, "pmids": e.get("pmids") or []})

    data_json = json.dumps({"nodes": nodes, "children": children})
    return f"""
    <div id="graph-root" style="position:relative; font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;">
      <svg id="graph-svg" viewBox="0 0 1000 620" width="100%" height="620" preserveAspectRatio="xMidYMid meet"
           style="background:#fcfcfb; border:1px solid #e1e0d9; border-radius:8px; display:block;">
        <defs>
          <filter id="node-shadow" x="-50%" y="-50%" width="200%" height="200%">
            <feDropShadow dx="0" dy="2" stdDeviation="2.5" flood-color="#0b0b0b" flood-opacity="0.3"/>
          </filter>
          <radialGradient id="sphere-highlight" cx="32%" cy="28%" r="70%">
            <stop offset="0%" stop-color="#ffffff" stop-opacity="0.7"/>
            <stop offset="30%" stop-color="#ffffff" stop-opacity="0.18"/>
            <stop offset="70%" stop-color="#ffffff" stop-opacity="0"/>
          </radialGradient>
          <radialGradient id="sphere-shade" cx="65%" cy="75%" r="70%">
            <stop offset="0%" stop-color="#000000" stop-opacity="0"/>
            <stop offset="100%" stop-color="#000000" stop-opacity="0.14"/>
          </radialGradient>
        </defs>
      </svg>
      <div id="graph-tooltip" style="position:absolute; pointer-events:none; opacity:0;
           background:#262624; color:#ffffff; border:1px solid rgba(255,255,255,0.15);
           border-radius:6px; padding:8px 10px; font-size:13px; max-width:280px;
           box-shadow:0 4px 12px rgba(0,0,0,0.25); white-space:pre-line; z-index:10;"></div>
      <div id="graph-detail" style="margin-top:10px; font-size:14px; color:#0b0b0b;"></div>
      <div style="margin-top:6px; font-size:12px; color:#898781;">
        Click a disease to expand or collapse it. Drag to reposition, double-click to unpin. Scroll to zoom.
      </div>
    </div>
    <script>{D3_JS}</script>
    <script>
    (function() {{
      const raw = {data_json};
      const byId = new Map(raw.nodes.map(n => [n.id, n]));
      const childrenOf = raw.children;
      const diseaseIds = Object.keys(childrenOf);
      const diseaseColor = new Map(raw.nodes.filter(n => n.type === "disease").map(n => [n.id, n.color]));
      const expanded = new Set();

      const svg = d3.select("#graph-svg");
      const width = 1000;
      const height = 620;
      const margin = 70;
      const container = svg.append("g");
      const zoom = d3.zoom().scaleExtent([0.3, 3]).on("zoom", (ev) => container.attr("transform", ev.transform));
      svg.call(zoom);

      const tooltip = d3.select("#graph-tooltip");
      const detail = d3.select("#graph-detail");

      let activeNodes = raw.nodes.filter(n => n.type === "disease");
      diseaseIds.forEach((d, i) => {{
        const anchor = byId.get(d);
        anchor.anchorX = width * (i + 1) / (diseaseIds.length + 1);
        anchor.anchorY = height / 2;
        anchor.x = anchor.anchorX;
        anchor.y = anchor.anchorY;
      }});
      let activeLinks = [];

      // A wrong_dx node is shared across diseases, so its weight depends on
      // which diseases are currently expanded, recomputed from active links
      // rather than stored on the node itself.
      let weightById = new Map();
      function linksFor(nodeId) {{
        return activeLinks.filter(l => (typeof l.target === "object" ? l.target.id : l.target) === nodeId);
      }}
      function radius(d) {{ return d.type === "disease" ? 26 : 8 + Math.min(weightById.get(d.id) || 1, 8) * 2; }}
      // Collision must account for the label's width, not just the circle,
      // or adjacent labels overlap each other (labels always sit to one side).
      function collideRadius(d) {{
        const labelLen = (d.type === "disease" ? d.id : (d.label || "")).length;
        return radius(d) + 6 + labelLen * 3.1;
      }}
      function clamp(v, lo, hi) {{ return Math.max(lo, Math.min(hi, v)); }}

      const linkForce = d3.forceLink().id(d => d.id).distance(l => l.target.type === "disease" ? 0 : 100).strength(0.9);
      const sim = d3.forceSimulation()
        .force("link", linkForce)
        .force("charge", d3.forceManyBody().strength(d => d.type === "disease" ? -1200 : -140).distanceMax(260))
        .force("collide", d3.forceCollide().radius(collideRadius).strength(0.9).iterations(3))
        .force("x", d3.forceX(d => d.anchorX ?? width / 2).strength(d => d.type === "disease" ? 0.2 : 0.03))
        .force("y", d3.forceY(d => d.anchorY ?? height / 2).strength(d => d.type === "disease" ? 0.2 : 0.05))
        .alphaDecay(0.04)
        .velocityDecay(0.5);

      let linkSel = container.append("g").attr("stroke-opacity", 0.55)
        .selectAll("line");
      let nodeSel = container.append("g").selectAll("g");

      function drag(simulation) {{
        function started(ev, d) {{ if (!ev.active) simulation.alphaTarget(0.25).restart(); d.fx = d.x; d.fy = d.y; }}
        function dragged(ev, d) {{ d.fx = clamp(ev.x, margin, width - margin); d.fy = clamp(ev.y, margin, height - margin); }}
        function ended(ev, d) {{ if (!ev.active) simulation.alphaTarget(0); }}
        return d3.drag().on("start", started).on("drag", dragged).on("end", ended);
      }}

      function restart() {{
        weightById = new Map();
        activeLinks.forEach(l => {{
          const t = typeof l.target === "object" ? l.target.id : l.target;
          weightById.set(t, (weightById.get(t) || 0) + (l.weight || 1));
        }});

        sim.nodes(activeNodes);
        linkForce.links(activeLinks);

        linkSel = linkSel.data(activeLinks, d => d.source.id + "->" + d.target.id + "@" + (d.source.id ? "" : ""));
        linkSel.exit().transition().duration(200).attr("stroke-opacity", 0).remove();
        const linkColor = d => diseaseColor.get(typeof d.source === "object" ? d.source.id : d.source) || "#c3c2b7";
        const enteredLinks = linkSel.enter().append("line")
          .attr("stroke", linkColor)
          .attr("stroke-width", d => 1 + Math.min(d.weight || 1, 6) * 0.6)
          .attr("stroke-opacity", 0);
        enteredLinks.transition().duration(450).attr("stroke-opacity", 0.55);
        linkSel = enteredLinks.merge(linkSel)
          .attr("stroke", linkColor)
          .attr("stroke-width", d => 1 + Math.min(d.weight || 1, 6) * 0.6);

        nodeSel = nodeSel.data(activeNodes, d => d.id);
        nodeSel.exit().transition().duration(200).style("opacity", 0).remove();
        const entered = nodeSel.enter().append("g").style("cursor", "pointer");
        // A slow, continuous pulse ring behind disease hubs (SMIL <animate>,
        // no JS loop needed) so they read as "alive," not static icons.
        entered.filter(d => d.type === "disease").append("circle").attr("class", "pulse-ring")
          .attr("fill", "none").attr("stroke", d => d.color).attr("stroke-width", 2).style("pointer-events", "none")
          .call(sel => {{
            sel.append("animate").attr("attributeName", "r").attr("values", "26;40;26").attr("dur", "2.8s").attr("repeatCount", "indefinite");
            sel.append("animate").attr("attributeName", "stroke-opacity").attr("values", "0.5;0;0.5").attr("dur", "2.8s").attr("repeatCount", "indefinite");
          }});
        // "visual" wraps everything that should scale together on hover,
        // kept separate from the outer <g> so the tick handler's translate
        // (outer) and the hover scale (inner) never fight over transform.
        const visual = entered.append("g").attr("class", "visual").attr("filter", "url(#node-shadow)")
          .style("transform-box", "fill-box").style("transform-origin", "center")
          .style("transition", "transform 0.15s ease-out");
        visual.append("circle").attr("class", "base-circle").attr("stroke-width", 2).attr("r", 0);
        // Shade + highlight overlays give a glossy sphere look, purely
        // decorative so they must never intercept pointer events.
        visual.append("circle").attr("class", "shade-circle")
          .attr("fill", "url(#sphere-shade)").attr("stroke", "none").style("pointer-events", "none").attr("r", 0);
        visual.append("circle").attr("class", "highlight-circle")
          .attr("fill", "url(#sphere-highlight)").attr("stroke", "none").style("pointer-events", "none").attr("r", 0);
        visual.append("text")
          .attr("class", "node-label")
          .text(d => d.type === "disease" ? d.id : d.label)
          .attr("y", 4)
          .attr("font-size", d => d.type === "disease" ? 14 : 12)
          .attr("font-weight", d => d.type === "disease" ? 700 : 400)
          .attr("fill", d => d.type === "disease" ? "#0b0b0b" : "#52514e")
          .attr("paint-order", "stroke").attr("stroke", "#fcfcfb").attr("stroke-width", 3)
          .style("opacity", 0).transition().delay(150).duration(250).style("opacity", 1);

        entered.call(drag(sim));
        entered.on("mousemove", (ev) => {{
            const box = document.getElementById("graph-root").getBoundingClientRect();
            tooltip.style("left", (ev.clientX - box.left + 12) + "px").style("top", (ev.clientY - box.top + 12) + "px");
          }})
          .on("mouseover", function() {{ d3.select(this).select(".visual").style("transform", "scale(1.18)"); }})
          .on("mouseout", function() {{ d3.select(this).select(".visual").style("transform", "scale(1)"); tooltip.style("opacity", 0); }})
          .on("dblclick", (ev, d) => {{ d.fx = null; d.fy = null; sim.alphaTarget(0.25).restart(); setTimeout(() => sim.alphaTarget(0), 300); }})
          .on("click", function(ev, d) {{
            ev.stopPropagation();
            const visualEl = d3.select(this).select(".visual");
            visualEl.style("transform", "scale(0.85)").transition().duration(180).style("transform", "scale(1)");
            if (d.type === "disease") {{
              toggleDisease(d.id);
            }} else {{
              const rows = linksFor(d.id);
              const html = rows.map(l => {{
                const s = typeof l.source === "object" ? l.source.id : l.source;
                const pmids = (l.pmids || []).map(p => `<a href="https://pubmed.ncbi.nlm.nih.gov/${{p}}/" target="_blank">${{p}}</a>`).join(", ");
                return `${{s}}: ${{l.weight}} report${{l.weight > 1 ? "s" : ""}} (${{pmids}})`;
              }}).join("<br>");
              const diseaseCount = rows.length;
              detail.html(`<b>Misdiagnosed as "${{d.label}}"</b>` +
                (diseaseCount > 1 ? ` (shared across ${{diseaseCount}} diseases)<br>` : "<br>") + html);
            }}
          }});
        nodeSel = entered.merge(nodeSel);

        // A wrong_dx node takes its single parent disease's color when only
        // one disease is confused with it; a shared node (multiple diseases)
        // stays neutral gray with a colored ring per connected disease so
        // identity isn't lost, but it doesn't falsely read as one disease.
        function baseFill(d) {{
          if (d.type === "disease") return d.color;
          const parents = [...new Set(linksFor(d.id).map(l => typeof l.source === "object" ? l.source.id : l.source))];
          return parents.length === 1 ? diseaseColor.get(parents[0]) : "#9a988f";
        }}
        nodeSel.select(".base-circle").transition().duration(400).ease(d3.easeBackOut.overshoot(1.6)).attr("r", radius);
        nodeSel.select(".base-circle")
          .attr("fill", baseFill)
          .attr("fill-opacity", 1)
          .attr("stroke", d => {{
            if (d.type === "disease") return "#ffffff";
            const parents = [...new Set(linksFor(d.id).map(l => typeof l.source === "object" ? l.source.id : l.source))];
            return parents.length > 1 ? "#0b0b0b" : "#ffffff";
          }});
        nodeSel.select(".shade-circle").transition().duration(400).ease(d3.easeBackOut.overshoot(1.6)).attr("r", radius);
        nodeSel.select(".highlight-circle").transition().duration(400).ease(d3.easeBackOut.overshoot(1.6)).attr("r", radius);
        nodeSel.select(".pulse-ring").attr("r", radius);
        nodeSel.on("mouseover", (ev, d) => {{
            const rows = linksFor(d.id);
            const text = d.type === "disease"
              ? `${{d.id}}\\nClick to expand/collapse`
              : `Wrong diagnosis: ${{d.label}}\\n` + rows.map(l => {{
                  const s = typeof l.source === "object" ? l.source.id : l.source;
                  return `${{s}}: ${{l.weight}} report${{l.weight > 1 ? "s" : ""}}`;
                }}).join("\\n");
            tooltip.text(text).style("opacity", 1);
          }});

        sim.alpha(0.8).restart();
      }}

      sim.on("tick", () => {{
        activeNodes.forEach(d => {{
          const r = radius(d);
          d.x = clamp(d.x, margin + r, width - margin - r);
          d.y = clamp(d.y, margin + r, height - margin - r);
        }});
        linkSel
          .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
          .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
        nodeSel.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
      }});

      function activeLinkCount(nodeId) {{
        return activeLinks.filter(l => {{
          const s = typeof l.source === "object" ? l.source.id : l.source;
          const t = typeof l.target === "object" ? l.target.id : l.target;
          return s === nodeId || t === nodeId;
        }}).length;
      }}

      function toggleDisease(diseaseId) {{
        if (expanded.has(diseaseId)) {{
          expanded.delete(diseaseId);
          activeLinks = activeLinks.filter(l => {{
            const s = typeof l.source === "object" ? l.source.id : l.source;
            return s !== diseaseId;
          }});
          // Only drop a wrong_dx node once it has no remaining active links
          // (it may still be shown via another expanded disease that shares it).
          activeNodes = activeNodes.filter(n => n.type === "disease" || activeLinkCount(n.id) > 0);
        }} else {{
          expanded.add(diseaseId);
          const parent = byId.get(diseaseId);
          const kids = childrenOf[diseaseId] || [];
          kids.forEach((c, i) => {{
            const n = byId.get(c.id);
            if (n.x === undefined) {{
              const angle = (i / Math.max(kids.length, 1)) * 2 * Math.PI;
              n.x = parent.x + Math.cos(angle) * 40;
              n.y = parent.y + Math.sin(angle) * 40;
            }}
            if (!activeNodes.includes(n)) activeNodes.push(n);
            activeLinks.push({{source: diseaseId, target: c.id, weight: c.weight, pmids: c.pmids}});
          }});
        }}
        restart();
      }}

      restart();
    }})();
    </script>
    """


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
st.title("MediRare: research extraction prototype")
st.warning(
    "Not medical advice or clinical decision support. Case reports are "
    "publication-biased anecdotes; current labels and candidate relations are "
    "AI-extracted and not clinician-reviewed. Counts are not prevalence, risk, "
    "causality, or diagnostic recommendations. A citation proves source "
    "provenance only, not clinical correctness."
)
with st.expander("What are these diseases? (plain-language primer)", expanded=True):
    st.markdown(
        """
All three are **autoimmune diseases**: the immune system attacks the
body's own tissue instead of germs. Early symptoms (fatigue, fevers, joint
pain) are vague and overlap heavily across diseases, which is exactly why
misdiagnosis happens.

- **SLE (Lupus)**: attacks multiple organs (skin, joints, kidneys, lungs).
- **Sjögren's syndrome**: attacks the glands that make tears and saliva
  (dry eyes/mouth), but also causes fatigue and joint pain.
- **MCTD (Mixed Connective Tissue Disease)**: a blend of lupus,
  scleroderma, and myositis features at once, which makes it inherently
  hard to pin down.

Below, "wrong diagnosis" means a case report where a patient was
initially diagnosed with something else, often an infection (e.g.
tuberculosis), a cancer (e.g. lymphoma), or a different autoimmune disease
(e.g. multiple sclerosis) before the correct diagnosis was reached.
        """
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
            st.error("Missing data/rag/index. Run scripts/e2e.sh or rag/index.py first.")
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
                    "grade (not necessarily a bad answer, the checker itself failed). "
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
            f"({'add --include-unreviewed' if show_unreviewed else ''}). See scripts/e2e.sh."
        )
        graph_path = fallback if fallback.exists() else None
    if graph_path and graph_path.exists():
        g = json.loads(graph_path.read_text())
        st.write(f"**{g['n_nodes']} nodes · {g['n_edges']} edges**")
        edges = sorted(g["edges"], key=lambda e: e.get("weight") or 0, reverse=True)
        if not edges:
            st.info("No explicitly clinician-reviewed relations are available yet.")
        else:
            # Validated categorical palette, dark-surface step (see dataviz
            # skill) used here for its extra saturation on a light canvas.
            DISEASE_COLORS = ["#3987e5", "#d95926", "#199e70"]  # blue, orange, aqua
            diseases = sorted({e["source"] for e in edges})
            legend_bits = " &nbsp;&nbsp; ".join(
                f'<span style="color:{DISEASE_COLORS[i % len(DISEASE_COLORS)]}">&#9679;</span> {d}'
                for i, d in enumerate(diseases)
            )
            st.markdown(legend_bits, unsafe_allow_html=True)
            components.html(render_force_graph(edges, DISEASE_COLORS), height=800, scrolling=True)

            st.markdown("**Explain a specific case**")
            st.caption(
                "The graph above runs entirely in your browser (drag/zoom/expand), so it "
                "can't tell Streamlit which node you clicked. Pick the same disease + "
                "misdiagnosis pair here to get a real, cited explanation of that case "
                "from the RAG agent, instead of just the PMID list."
            )
            pick_col1, pick_col2 = st.columns(2)
            pick_disease = pick_col1.selectbox("Target disease", diseases, key="kg_pick_disease")
            wrong_dx_options = sorted({
                e["target"] for e in edges if e["source"] == pick_disease
            })
            pick_wrong_dx = pick_col2.selectbox("Misdiagnosed as", wrong_dx_options, key="kg_pick_wrong_dx")
            if st.button("Explain this case", key="kg_explain_button"):
                index = ROOT / "data/rag/index"
                if not ((index / "CURRENT").exists() or (index / "meta.json").exists()):
                    st.error("Missing data/rag/index. Run scripts/e2e.sh or rag/index.py first.")
                else:
                    with st.spinner("Retrieving + generating..."):
                        from agent.ask import ask

                        case_query = (
                            f"How was {pick_disease} confused with {pick_wrong_dx} "
                            f"in a case report?"
                        )
                        result = ask(case_query, index_dir=index, allow_unreviewed=show_unreviewed)
                    if result["status"] == "error":
                        error = result.get("error") or {}
                        st.error(f"{error.get('code', 'service_error')}: {error.get('message', 'The service is unavailable.')}")
                    elif result.get("evidence_status") == "no_clinician_reviewed_evidence":
                        st.info(
                            "Abstained: no clinician-reviewed evidence is available for this "
                            "case yet. Check 'Enable unreviewed research outputs' above to "
                            "explain it from unreviewed candidate evidence instead."
                        )
                    elif result["status"] == "abstained":
                        st.info("Abstained: retrieved evidence did not clear the confidence threshold for this case.")
                    else:
                        st.markdown(result["answer"])
                        if result.get("citations"):
                            st.write("Citations:", ", ".join(f"`{c}`" for c in result["citations"]))
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
            "`annotation_status`: how misdiagnosis_sequence was produced. "
            "`high`/`medium`/`gazetteer` = regex/keyword pattern matched a named "
            "wrong diagnosis; `llm` = Ollama-assisted extraction; "
            "`legacy_unreviewed` = older candidate data, re-validated against the "
            "abstract on every run but not clinician-reviewed; `signal_only` = a "
            "misdiagnosis keyword was found but no entity could be extracted; "
            "`none`/`unreviewed` = no misdiagnosis signal detected. None of these "
            "values mean clinician-reviewed. Only `reviewed` (not yet present in "
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
