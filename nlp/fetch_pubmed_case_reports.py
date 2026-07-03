"""
Week 1 NLP starter script (beginner-friendly).

Goal: Fetch 20-30 PubMed case report records for a target disease and write:
- raw XML to data/nlp/raw/
- processed JSONL to data/nlp/processed/

Notes:
- This script queries PubMed via paperscraper's `get_pubmed_papers` (pymed under
  the hood), which itself calls NCBI E-utilities. We pass raw PubMed query
  syntax straight through (see DISEASE_TERMS / MISDIAGNOSIS_TERMS), so query
  semantics are unchanged from the previous direct-E-utilities implementation.
- Week 1 parsing is intentionally "good enough": title/abstract extraction covers most cases
  and is easy to improve later.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

from paperscraper.pubmed import get_pubmed_papers


DISEASE_TERMS = {
    # General corpus: every case report for the disease.
    "SLE": '"systemic lupus erythematosus" AND "case report"',
    "Sjogrens": '"Sjogren syndrome" AND "case report"',
    "MCTD": '"mixed connective tissue disease" AND "case report"',
}

# Misdiagnosis-focused corpus: same diseases, but restricted to case reports
# whose title/abstract signals a diagnostic error or mimic. The generic query
# buries misdiagnosis cases (~4 per 50); this query surfaces them (~500+ for SLE).
# The misdiagnosis trigger block is shared across diseases.
_MISDX_TRIGGERS = (
    '(misdiagnos*[tiab] OR "initially diagnosed"[tiab] OR mimicking[tiab] '
    'OR masquerading[tiab] OR "delayed diagnosis"[tiab] OR "initially treated"[tiab])'
)
MISDIAGNOSIS_TERMS = {
    "SLE": f'"systemic lupus erythematosus"[tiab] AND {_MISDX_TRIGGERS} AND "case reports"[ptyp]',
    "Sjogrens": f'"primary Sjogren\'s syndrome"[tiab] AND {_MISDX_TRIGGERS} AND "case reports"[ptyp]',
    "MCTD": f'"mixed connective tissue disease"[tiab] AND {_MISDX_TRIGGERS} AND "case reports"[ptyp]',
}


@dataclass(frozen=True)
class CaseReport:
    pubmed_id: str
    disease: str
    title: str
    abstract: str
    misdiagnosis_sequence: list[str]
    extracted_at: str


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_case_reports(term: str, retmax: int, disease: str) -> tuple[list[CaseReport], list[ET.Element]]:
    """
    Query PubMed via paperscraper's get_pubmed_papers (pymed -> NCBI
    E-utilities under the hood), passing `term` through as raw PubMed query
    syntax unchanged. Returns parsed CaseReport rows plus each record's raw
    PubmedArticle XML element (for archival to data/nlp/raw/).
    """
    df = get_pubmed_papers(
        term, fields=["pubmed_id", "title", "abstract", "xml"], max_results=retmax
    )
    extracted_at = _iso_now()

    rows: list[CaseReport] = []
    xml_elements: list[ET.Element] = []
    for row in df.to_dict(orient="records"):
        pubmed_id = str(row["pubmed_id"]).strip().split("\n")[0]
        if not pubmed_id:
            continue
        rows.append(
            CaseReport(
                pubmed_id=pubmed_id,
                disease=disease,
                title=(row.get("title") or "").strip(),
                abstract=(row.get("abstract") or "").strip(),
                misdiagnosis_sequence=[],
                extracted_at=extracted_at,
            )
        )
        if isinstance(row.get("xml"), ET.Element):
            xml_elements.append(row["xml"])

    return rows, xml_elements


def write_jsonl(path: Path, rows: Iterable[CaseReport]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r.__dict__, ensure_ascii=True) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--disease", choices=sorted(DISEASE_TERMS.keys()), default="SLE")
    ap.add_argument("--retmax", type=int, default=30)
    ap.add_argument(
        "--focus",
        choices=["general", "misdiagnosis"],
        default="misdiagnosis",
        help="general = all case reports; misdiagnosis = only diagnostic-error/mimic cases (default)",
    )
    args = ap.parse_args()

    if args.retmax > 200:
        ap.error("retmax must be <= 200 (NCBI rate-limit policy; batch for more)")

    term = (MISDIAGNOSIS_TERMS if args.focus == "misdiagnosis" else DISEASE_TERMS)[args.disease]
    print(f"Query [{args.focus}]: {term}")

    Path("data/nlp/raw").mkdir(parents=True, exist_ok=True)
    Path("data/nlp/processed").mkdir(parents=True, exist_ok=True)

    rows, xml_elements = fetch_case_reports(term, retmax=args.retmax, disease=args.disease)

    raw_root = ET.Element("PubmedArticleSet")
    for el in xml_elements:
        raw_root.append(el)
    raw_path = Path(f"data/nlp/raw/{args.disease}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml")
    ET.ElementTree(raw_root).write(raw_path, encoding="utf-8", xml_declaration=True)

    out_path = Path(f"data/nlp/processed/{args.disease.lower()}_case_reports.jsonl")
    write_jsonl(out_path, rows)

    print(f"Wrote raw: {raw_path}")
    print(f"Wrote processed: {out_path} ({len(rows)} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

