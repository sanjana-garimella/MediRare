"""
Week 1 NLP starter script (beginner-friendly).

Goal: Fetch 20-30 PubMed case report records for a target disease and write:
- raw XML to data/nlp/raw/
- processed JSONL to data/nlp/processed/

Notes:
- This script uses PubMed E-utilities (official NCBI API).
- Week 1 parsing is intentionally "good enough": title/abstract extraction covers most cases
  and is easy to improve later.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import requests
from lxml import etree


EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"


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


def esearch(term: str, retmax: int) -> list[str]:
    r = requests.get(
        EUTILS_BASE + "esearch.fcgi",
        params={"db": "pubmed", "term": term, "retmax": retmax, "retmode": "json"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["esearchresult"]["idlist"]


def efetch_xml(ids: Iterable[str]) -> str:
    r = requests.get(
        EUTILS_BASE + "efetch.fcgi",
        params={"db": "pubmed", "id": ",".join(ids), "retmode": "xml"},
        timeout=60,
    )
    r.raise_for_status()
    return r.text


def parse_pubmed_xml(xml_text: str, disease: str) -> list[CaseReport]:
    # Minimal extraction: PMID, title, abstract.
    root = etree.fromstring(xml_text.encode("utf-8"))
    out: list[CaseReport] = []
    extracted_at = _iso_now()

    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//MedlineCitation/PMID")
        if pmid_el is None or not (pmid_el.text or "").strip():
            continue
        pubmed_id = pmid_el.text.strip()

        title_el = article.find(".//Article/ArticleTitle")
        title = "".join(title_el.itertext()).strip() if title_el is not None else ""

        abs_el = article.find(".//Article/Abstract")
        if abs_el is None:
            abstract = ""
        else:
            parts = []
            for at in abs_el.findall(".//AbstractText"):
                label = (at.get("Label") or "").strip()
                txt = "".join(at.itertext()).strip()
                if not txt:
                    continue
                parts.append(f"{label}: {txt}" if label else txt)
            abstract = "\n".join(parts).strip()

        out.append(
            CaseReport(
                pubmed_id=pubmed_id,
                disease=disease,
                title=title,
                abstract=abstract,
                misdiagnosis_sequence=[],
                extracted_at=extracted_at,
            )
        )

    return out


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
    ap.add_argument("--sleep_s", type=float, default=0.34, help="Be polite to NCBI.")
    args = ap.parse_args()

    if args.retmax > 200:
        ap.error("retmax must be <= 200 (NCBI rate-limit policy; batch for more)")

    term = (MISDIAGNOSIS_TERMS if args.focus == "misdiagnosis" else DISEASE_TERMS)[args.disease]
    print(f"Query [{args.focus}]: {term}")

    Path("data/nlp/raw").mkdir(parents=True, exist_ok=True)
    Path("data/nlp/processed").mkdir(parents=True, exist_ok=True)

    ids = esearch(term, retmax=args.retmax)
    time.sleep(args.sleep_s)
    xml_text = efetch_xml(ids)

    raw_path = Path(f"data/nlp/raw/{args.disease}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml")
    raw_path.write_text(xml_text, encoding="utf-8")

    rows = parse_pubmed_xml(xml_text, disease=args.disease)

    out_path = Path(f"data/nlp/processed/{args.disease.lower()}_case_reports.jsonl")
    write_jsonl(out_path, rows)

    print(f"Wrote raw: {raw_path}")
    print(f"Wrote processed: {out_path} ({len(rows)} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

