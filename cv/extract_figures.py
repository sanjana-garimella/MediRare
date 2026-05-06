"""
Week 1 CV starter script (beginner-friendly).

Goal:
- Iterate over PDFs in a folder
- Extract embedded images to PNGs
- Write a JSONL metadata file mapping each extracted image to its source PDF

Week 1 note:
- This will extract many images (including small icons). That's OK for Week 1.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def guess_pubmed_id(pdf_path: Path) -> str:
    # Best-effort: pull digits from filename.
    digits = "".join(ch for ch in pdf_path.stem if ch.isdigit())
    return digits if digits else pdf_path.stem


def extract_images(pdf_path: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    saved: list[Path] = []

    idx = 0
    for page in doc:
        for img in page.get_images(full=True):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)
            if pix.n > 4:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            out_path = out_dir / f"{pdf_path.stem}_img{idx}.png"
            pix.save(str(out_path))
            saved.append(out_path)
            idx += 1
    return saved


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

    rows = []
    for pdf_path in sorted(pdf_dir.glob("*.pdf")):
        pubmed_id = guess_pubmed_id(pdf_path)
        extracted = extract_images(pdf_path, out_dir=out_dir)
        for i, img_path in enumerate(extracted):
            rows.append(
                {
                    "pubmed_id": pubmed_id,
                    "disease": "",  # fill later or leave blank in Week 1
                    "figure_index": i,
                    "figure_type": "other",
                    "file_path": str(img_path.as_posix()),
                    "caption": "",
                    "clinical_relevance": "unknown",
                    "extracted_at": _iso_now(),
                    "source_pdf": str(pdf_path.as_posix()),
                }
            )

    with meta_out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=True) + "\n")

    print(f"Processed PDFs: {len(list(pdf_dir.glob('*.pdf')))}")
    print(f"Wrote images to: {out_dir}")
    print(f"Wrote metadata: {meta_out} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

