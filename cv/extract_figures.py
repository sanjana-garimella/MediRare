"""
Week 1 CV starter script (beginner-friendly).

Goal:
- Iterate over PDFs in a folder
- Extract embedded images to PNGs organized by pubmed_id
- Attempt to extract figure captions from surrounding PDF text
- Write a CSV metadata file conforming to the ExtractedFigure schema

Week 1 note:
- This will extract many images (including small icons). That's OK for Week 1.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF


FIELDS = [
    "pubmed_id",
    "disease",
    "figure_index",
    "figure_type",
    "file_path",
    "caption",
    "clinical_relevance",
    "extracted_at",
    "source_pdf",
]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


PMID_DISEASE = {
    "10853674": "SLE",
    "8943239":  "SLE",
    "10965447": "SLE",
    "11668484": "SLE",
    "9053354":  "SLE",
    "10375769": "Sjogrens",
    "9941144":  "Sjogrens",
    "10115472": "Sjogrens",
    "7607335":  "Sjogrens",
    "10224699": "MCTD",
}


def guess_pubmed_id(pdf_path: Path) -> str:
    digits = "".join(ch for ch in pdf_path.stem if ch.isdigit())
    return digits if digits else pdf_path.stem


def extract_caption(page: fitz.Page, xref: int) -> str:
    rects = page.get_image_rects(xref)
    if not rects:
        return ""
    img_rect = rects[0]
    blocks = page.get_text("blocks")
    candidates = []
    for block in blocks:
        x0, y0, x1, y1, text, *_ = block
        text = text.strip()
        if y0 >= img_rect.y1 - 5 and text.lower().startswith(("fig", "figure")):
            candidates.append((y0, text))
    if candidates:
        candidates.sort()
        return candidates[0][1].replace("\n", " ").strip()
    return ""


def extract_images(pdf_path: Path, out_dir: Path) -> list[dict]:
    pubmed_id = guess_pubmed_id(pdf_path)
    figure_dir = out_dir / pubmed_id
    figure_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    results = []
    idx = 0

    for page in doc:
        for img in page.get_images(full=True):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)
            if pix.colorspace is None:
                continue
            if pix.colorspace.name not in ("DeviceRGB", "DeviceGray"):
                pix = fitz.Pixmap(fitz.csRGB, pix)

            out_path = figure_dir / f"{idx}.png"
            pix.save(str(out_path))

            caption = extract_caption(page, xref)

            results.append({
                "pubmed_id": pubmed_id,
                "disease": PMID_DISEASE.get(pubmed_id, ""),
                "figure_index": idx,
                "figure_type": "other",
                "file_path": str(out_path.as_posix()),
                "caption": caption,
                "clinical_relevance": "unknown",
                "extracted_at": _iso_now(),
                "source_pdf": str(pdf_path.as_posix()),
            })
            idx += 1

    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf_dir", type=str, required=True)
    ap.add_argument("--out_dir", type=str, required=True)
    ap.add_argument("--meta_out", type=str, required=True)
    args = ap.parse_args()

    pdf_dir = Path(args.pdf_dir)
    out_dir = Path(args.out_dir)
    meta_out = Path(args.meta_out)
    meta_out.parent.mkdir(parents=True, exist_ok=True)

    all_rows = []
    for pdf_path in sorted(pdf_dir.glob("*.pdf")):
        rows = extract_images(pdf_path, out_dir=out_dir)
        all_rows.extend(rows)
        print(f"  {pdf_path.name}: {len(rows)} figures")

    with meta_out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nProcessed PDFs : {len(list(pdf_dir.glob('*.pdf')))}")
    print(f"Figures written: {out_dir}")
    print(f"Metadata CSV   : {meta_out} ({len(all_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
