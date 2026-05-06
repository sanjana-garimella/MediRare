from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


st.set_page_config(page_title="MediRare Demo", layout="wide")
st.title("MediRare - Week 1 Demo")

data_path = Path("integration/merged_records.jsonl")
if not data_path.exists():
    st.warning("Missing integration/merged_records.jsonl. Run: python integration/merge.py")
    st.stop()

records = load_jsonl(data_path)
df = pd.DataFrame(
    [
        {
            "pubmed_id": r.get("pubmed_id"),
            "disease": r.get("disease"),
            "has_case_report": r.get("case_report") is not None,
            "figure_count": len(r.get("figures") or []),
        }
        for r in records
    ]
)

st.subheader("Merged Records")
st.dataframe(df, use_container_width=True, hide_index=True)

