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
but the image binaries are not downloadable through the efetch API. To get the
actual image files, pass --download-images: this looks up each open-access
article on NCBI's PMC Open Access dataset mirror on AWS S3 (public, no login,
no signing — s3://pmc-oa-opendata, see registry.opendata.aws/ncbi-pmc), which
serves each article's media files as flat objects alongside its XML/PDF/JSON.
(The older oa.fcgi + FTP oa_package/ bulk-download route is deprecated by NCBI
as of April 2026 and returns dead links — do not resurrect it.)
Results conform to schemas/extracted_figure.py (ExtractedFigure).
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen
from xml.etree import ElementTree as ET

import certifi

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PMC_S3_BUCKET = "https://pmc-oa-opendata.s3.amazonaws.com"
S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
SLEEP = 0.4  # seconds between NCBI requests (3 req/sec limit, no API key)

# Plain urlopen() uses the system/OpenSSL cert store, which on a lot of
# Python installs (esp. python.org macOS builds) doesn't trust anything —
# every HTTPS call in this file fails SSL verification, silently, because
# each caller catches Exception broadly. Use certifi's bundle explicitly,
# same as what `requests` (used elsewhere in this project) does by default.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── figure type classification ────────────────────────────────────────────────

# Order matters: specific imaging/histology modalities are checked before the
# generic skin terms, so "cystic lesion on CT scan" classifies as imaging, not
# rash_image (the word "lesion" would otherwise win on order alone).
#
# Two term shapes here: whole words (CT, MRI, PET, scan) get a trailing \b;
# stems meant to catch multiple suffixes (sonograph->sonography/sonographic,
# echocardiogra->echocardiography/echocardiogram, angiogra->angiography/
# angiogram) get \w* instead — a trailing \b after the bare stem requires a
# word boundary immediately following "echocardiogra", which never happens
# since real words continue "...phy"/"...m". That silently dropped the single
# most common imaging word in these case reports (echocardiography).
_FIGURE_TYPE_RULES = [
    ("imaging", r"\b(?:CT|MRI|ultrasound|radiograph\w*|X-ray|PET|scan\w*|contrast-enhanced|sonograph\w*|echocardiogra\w*|angiogra\w*)\b"),
    # "histopatholog\w*" is separate from "histolog\w*": "histopathology" does
    # NOT contain the substring "histolog" ("histo" + "pathology", not
    # "histo" + "logy"), so it silently fell through to the rash_image check
    # below — where captions describing necrotizing histology ("amorphous
    # necrotic debris") wrongly matched on "necrotic" and got tagged as a
    # skin photo instead of histology. Order still matters: checking this
    # before rash_image is what makes that fix effective.
    ("histology", r"\b(biopsy|histolog\w*|histopatholog\w*|stain|H&E|PAS|immunohistochem|magnif|×\s?\d|microscop|glomerul|tubul)\b"),
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
    with urlopen(url, timeout=30, context=_SSL_CONTEXT) as r:
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


# ── image download via PMC Open Access S3 mirror ──────────────────────────────

def pmc_s3_prefix(pmcid: str) -> str | None:
    """
    Find the versioned article folder for pmcid in the PMC Open Access S3
    bucket (e.g. "PMC13242597.1/"). Returns None if the article isn't in the
    open-access dataset. Picks the highest version if more than one exists.
    """
    url = f"{PMC_S3_BUCKET}/?list-type=2&prefix={quote(pmcid)}.&delimiter=/"
    try:
        root = ET.fromstring(_get(url))
    except Exception:
        return None
    prefixes = [
        p.findtext("s3:Prefix", namespaces=S3_NS)
        for p in root.findall(".//s3:CommonPrefixes", S3_NS)
    ]
    prefixes = [p for p in prefixes if p]
    if not prefixes:
        return None

    def _version(p: str) -> int:
        # "PMC13242597.10/" -> 10. Numeric sort, not lexicographic: a plain
        # string sort would rank ".10/" below ".2/".
        m = re.search(r"\.(\d+)/$", p)
        return int(m.group(1)) if m else -1

    return max(prefixes, key=_version)


def download_figure_images(pmcid: str, img_refs: list[str], out_dir: Path) -> dict[str, str]:
    """
    Download each figure's real image file for pmcid from the PMC Open Access
    S3 mirror. Returns {img_ref: saved_file_path} for whichever refs resolved.
    """
    prefix = pmc_s3_prefix(pmcid)
    if not prefix:
        return {}

    saved: dict[str, str] = {}
    for ref in img_refs:
        filename = Path(ref).name
        url = f"{PMC_S3_BUCKET}/{quote(prefix + filename)}"
        try:
            with urlopen(url, timeout=30, context=_SSL_CONTEXT) as resp:
                data = resp.read()
        except Exception:
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / filename
        dest.write_bytes(data)
        saved[ref] = str(dest.as_posix())
    return saved


# ── zero-shot figure classification (BiomedCLIP fallback) ─────────────────────
#
# classify_figure() only sees captions and misses figures whose caption text
# doesn't carry a modality keyword (e.g. "small subcentimeter prevascular
# lymph nodes" instead of "CT shows..."). BiomedCLIP is a CLIP-style model
# trained on 15M PMC figure-caption pairs (PMC-15M) — same distribution as
# the images this script fetches — so it can classify from pixels directly.
# See docs/research_references.md for the reference and validation notes.
#
# This is a fallback tier only, same pattern as the gazetteer in
# nlp/extract_misdiagnosis.py: it never overrides a caption-keyword match,
# it only fires when classify_figure() returned "other". Requires the image
# file to exist on disk (--download-images) and the optional CV-classify
# deps (see cv/requirements-classify.txt) — both opt-in via --classify-images.
#
# MEASURED ACCURACY (manual validation against real "other"-bucket PMC
# figures, see docs/research_references.md): 10/13 correct (~77%) across two
# batches. Both misses were small, cropped, measurement-only figures (e.g.
# "lymph node measuring 12x5mm") with no anatomical context in the crop —
# the model reads them as histology/skin close-ups. One miss scored 0.97
# confidence, so raising CLASSIFY_CONFIDENCE_THRESHOLD does not reliably
# catch this failure mode; it only filters genuinely low-confidence calls.
# This is meaningfully worse than the NLP gazetteer's precision (which is
# ~4:1 good:bad) — treat --classify-images output as "probably right, spot
# check before trusting it downstream," not as a verified label.

BIOMEDCLIP_MODEL = "hf-hub:microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224"

# Confidence below this: leave figure_type as "other" rather than guess.
CLASSIFY_CONFIDENCE_THRESHOLD = 0.5

_ZERO_SHOT_LABELS = ["imaging", "histology", "lab_chart", "rash_image"]
_ZERO_SHOT_PROMPTS = {
    "imaging": "a radiology scan image such as a CT, MRI, X-ray, or ultrasound",
    "histology": "a histopathology microscopy image of stained tissue",
    "lab_chart": "a line graph or bar chart of laboratory values",
    "rash_image": "a clinical photograph of a patient skin lesion or physical exam finding",
}


class _ZeroShotClassifier:
    """Lazily loads BiomedCLIP once and reuses it across all figures in a run."""

    def __init__(self) -> None:
        import open_clip  # deferred: only required with --classify-images

        self._torch = __import__("torch")
        self._model, self._preprocess = open_clip.create_model_from_pretrained(BIOMEDCLIP_MODEL)
        self._model.eval()
        tokenizer = open_clip.get_tokenizer(BIOMEDCLIP_MODEL)
        texts = tokenizer([_ZERO_SHOT_PROMPTS[l] for l in _ZERO_SHOT_LABELS])
        with self._torch.no_grad():
            text_features = self._model.encode_text(texts)
            self._text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    def classify(self, image_path: str) -> tuple[str, float] | None:
        from PIL import Image

        try:
            img = Image.open(image_path).convert("RGB")
        except Exception:
            return None
        image = self._preprocess(img).unsqueeze(0)
        with self._torch.no_grad():
            image_features = self._model.encode_image(image)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            probs = (100 * image_features @ self._text_features.T).softmax(dim=-1)[0]
        label, confidence = max(zip(_ZERO_SHOT_LABELS, probs.tolist()), key=lambda x: x[1])
        return label, confidence


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
    ap.add_argument(
        "--download-images",
        action="store_true",
        help="Also fetch real image files via the PMC OA service (oa.fcgi)",
    )
    ap.add_argument(
        "--figures-dir",
        default="data/cv/figures",
        help="Directory to save downloaded images into (one subfolder per PMID)",
    )
    ap.add_argument(
        "--figures-out",
        default="data/cv/extracted_figures.jsonl",
        help="Output JSONL conforming to schemas/extracted_figure.py (only written with --download-images)",
    )
    ap.add_argument(
        "--classify-images",
        action="store_true",
        help=(
            "Zero-shot classify figures still 'other' after caption-keyword "
            "matching, using BiomedCLIP on the downloaded image. Requires "
            "--download-images and the deps in cv/requirements-classify.txt "
            "(see that file for venv setup — these are not in cv/requirements.txt "
            "since they pull in torch and a ~350MB model download)."
        ),
    )
    args = ap.parse_args()

    if args.classify_images and not args.download_images:
        ap.error("--classify-images requires --download-images (it classifies the downloaded image file)")

    paths = [Path(p) for p in args.jsonl]
    for p in paths:
        if not p.exists():
            print(f"ERROR: not found: {p}", file=sys.stderr)
            return 1

    classifier: _ZeroShotClassifier | None = None
    if args.classify_images:
        print("Loading BiomedCLIP for zero-shot classification (first run downloads ~350MB) ...")
        try:
            classifier = _ZeroShotClassifier()
        except ImportError as e:
            print(f"ERROR: --classify-images deps missing ({e}).", file=sys.stderr)
            print("Install via: pip install -r cv/requirements-classify.txt", file=sys.stderr)
            return 1

    records = load_records(paths)
    if args.limit:
        records = records[: args.limit]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    articles: list[dict] = []
    extracted_figures: list[dict] = []
    open_access = 0
    total_figures = 0
    images_saved = 0
    zero_shot_classified = 0

    figures_dir = Path(args.figures_dir)

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

        if args.download_images:
            img_refs = [fig["img_ref"] for fig in figures if fig["img_ref"]]
            saved = download_figure_images(pmcid, img_refs, figures_dir / pmid)
            time.sleep(SLEEP)
            for idx, fig in enumerate(figures):
                file_path = saved.get(fig["img_ref"], "")
                if not file_path:
                    continue
                images_saved += 1

                if classifier is not None and fig["figure_type"] == "other":
                    result = classifier.classify(file_path)
                    if result and result[1] >= CLASSIFY_CONFIDENCE_THRESHOLD:
                        fig["figure_type"] = result[0]
                        zero_shot_classified += 1

                extracted_figures.append(
                    {
                        "pubmed_id": pmid,
                        "disease": disease,
                        "figure_index": idx,
                        "figure_type": fig["figure_type"],
                        "file_path": file_path,
                        "caption": fig["caption"],
                        "clinical_relevance": "unknown",
                        "extracted_at": _iso_now(),
                        "source_pdf": f"pmc:{pmcid}",
                    }
                )
            print(f"    -> downloaded {len(saved)}/{len(img_refs)} images")

    with out_path.open("w", encoding="utf-8") as f:
        for a in articles:
            f.write(json.dumps(a, ensure_ascii=True) + "\n")

    if args.download_images:
        figures_out_path = Path(args.figures_out)
        figures_out_path.parent.mkdir(parents=True, exist_ok=True)
        with figures_out_path.open("w", encoding="utf-8") as f:
            for row in extracted_figures:
                f.write(json.dumps(row, ensure_ascii=True) + "\n")

    print(f"\n{'='*60}")
    print(f"CV figure fetch complete")
    print(f"{'='*60}")
    print(f"  Records scanned       : {len(records)}")
    print(f"  Open-access w/ figures : {open_access}")
    print(f"  Total figures          : {total_figures}")
    print(f"  Written                : {out_path}")
    if args.download_images:
        print(f"  Images downloaded      : {images_saved}/{total_figures}")
        print(f"  Extracted figures out  : {args.figures_out}")
    if args.classify_images:
        print(f"  Zero-shot reclassified : {zero_shot_classified} ('other' -> a confident modality)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
