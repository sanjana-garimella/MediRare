#!/usr/bin/env python3
"""
Fetch clinical figure metadata from PubMed Central open-access articles.

Usage:
    python3 cv/fetch_pmc_figures.py \
        --jsonl data/nlp/processed/sle_case_reports.jsonl \
                data/nlp/processed/sjogrens_case_reports.jsonl \
                data/nlp/processed/mctd_case_reports.jsonl \
        --out data/cv/figure_metadata.jsonl

For each PubMed record:
  1. elink PubMed ID -> PMC ID (only open-access articles have one accessible)
  2. efetch the PMC full-text XML
  3. parse <fig> elements: label, caption, graphic ref
  4. classify figure_type by caption keywords

Writes one JSON object per article (with a nested figures[] list) to --out.
This is the script that regenerates data/cv/figure_metadata.jsonl from scratch,
making the CV pipeline reproducible from the committed NLP records alone.

NCBI rate limit: 3 req/sec without an API key. We sleep 0.4s between calls.
Most case reports are NOT open-access; expect ~15-20% to yield figures.

Note: PMC serves figure *metadata* (captions, labels, image filenames) via XML,
but the image binaries are not downloadable through the efetch API. This script
captures everything needed to classify and reason over figures; downloading the
actual PNGs requires the PMC OA bulk service (see roadmap).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen
from xml.etree import ElementTree as ET

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
SLEEP = 0.4  # seconds between NCBI requests (3 req/sec limit, no API key)


# ── figure type classification ────────────────────────────────────────────────

# Order matters: specific imaging/histology modalities are checked before the
# generic skin terms, so "cystic lesion on CT scan" classifies as imaging, not
# rash_image (the word "lesion" would otherwise win on order alone).
_FIGURE_TYPE_RULES = [
    ("imaging", r"\b(CT|MRI|ultrasound|sonograph|radiograph|X-ray|echocardiogra|angiogra|PET|scan|contrast-enhanced)\b"),
    ("histology", r"\b(biopsy|histolog|stain|H&E|PAS|immunohistochem|magnif|×\s?\d|microscop|glomerul|tubul)\b"),
    ("lab_chart", r"\b(trend|level over|titer|graph|plot|curve|timeline|chart|time course)\b"),
    ("rash_image", r"\b(rash|erythema|skin|cutaneous|malar|purpura|papule|macule|dermat|necrotic)\b"),
]


def classify_figure(caption: str) -> str:
    for ftype, pattern in _FIGURE_TYPE_RULES:
        if re.search(pattern, caption, re.IGNORECASE):
            return ftype
    return "other"


# ── NCBI helpers ───────────────────────────────────────────────────────────────

def _get(url: str) -> bytes:
    with urlopen(url, timeout=30) as r:
        return r.read()


def pmid_to_pmcid(pmid: str) -> str | None:
    """Resolve a PubMed ID to its PMC ID via elink. Returns None if not in PMC."""
    url = f"{EUTILS}/elink.fcgi?dbfrom=pubmed&db=pmc&id={pmid}&retmode=xml"
    try:
        root = ET.fromstring(_get(url))
    except Exception:
        return None
    for link in root.iter("Link"):
        ident = link.findtext("Id")
        if ident:
            return f"PMC{ident}"
    return None


def fetch_pmc_figures(pmcid: str) -> list[dict]:
    """Fetch PMC full-text XML and extract figure metadata."""
    numeric = pmcid.replace("PMC", "")
    url = f"{EUTILS}/efetch.fcgi?db=pmc&id={numeric}&retmode=xml"
    try:
        root = ET.fromstring(_get(url))
    except Exception:
        return []

    figures: list[dict] = []
    for fig in root.iter("fig"):
        label = (fig.findtext("label") or "").strip()
        caption_el = fig.find("caption")
        caption = ""
        if caption_el is not None:
            caption = " ".join("".join(p.itertext()).strip() for p in caption_el)
            caption = re.sub(r"\s+", " ", caption).strip()
        graphic = fig.find(".//graphic")
        img_ref = ""
        if graphic is not None:
            for k, v in graphic.attrib.items():
                if k.endswith("href"):
                    img_ref = v
                    break
        figures.append(
            {
                "label": label,
                "caption": caption,
                "img_ref": img_ref,
                "figure_type": classify_figure(caption),
            }
        )
    return figures


# ── main ───────────────────────────────────────────────────────────────────────

def load_records(paths: list[Path]) -> list[dict]:
    records: list[dict] = []
    for p in paths:
        with p.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--jsonl", nargs="+", required=True, help="Processed NLP JSONL file(s)")
    ap.add_argument("--out", required=True, help="Output figure metadata JSONL")
    ap.add_argument("--limit", type=int, default=0, help="Cap records scanned (0 = all)")
    args = ap.parse_args()

    paths = [Path(p) for p in args.jsonl]
    for p in paths:
        if not p.exists():
            print(f"ERROR: not found: {p}", file=sys.stderr)
            return 1

    records = load_records(paths)
    if args.limit:
        records = records[: args.limit]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    articles: list[dict] = []
    open_access = 0
    total_figures = 0

    print(f"Scanning {len(records)} records for PMC open-access figures ...")
    for i, rec in enumerate(records, 1):
        pmid = rec["pubmed_id"]
        disease = rec.get("disease", "")
        title = rec.get("title", "")

        pmcid = pmid_to_pmcid(pmid)
        time.sleep(SLEEP)
        if not pmcid:
            continue

        figures = fetch_pmc_figures(pmcid)
        time.sleep(SLEEP)
        if not figures:
            continue

        open_access += 1
        total_figures += len(figures)
        articles.append(
            {
                "pubmed_id": pmid,
                "pmc_id": pmcid,
                "disease": disease,
                "title": title,
                "figure_count": len(figures),
                "figures": figures,
            }
        )
        print(f"  [{i}/{len(records)}] {pmid} -> {pmcid}: {len(figures)} figures")

    with out_path.open("w", encoding="utf-8") as f:
        for a in articles:
            f.write(json.dumps(a, ensure_ascii=True) + "\n")

    print(f"\n{'='*60}")
    print(f"CV figure fetch complete")
    print(f"{'='*60}")
    print(f"  Records scanned       : {len(records)}")
    print(f"  Open-access w/ figures : {open_access}")
    print(f"  Total figures          : {total_figures}")
    print(f"  Written                : {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
