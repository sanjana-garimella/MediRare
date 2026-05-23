"""
Interactive annotation script for extracted figures.

For each figure:
- Opens the image so you can see it
- Asks only for figure_type (or delete)
- Saves after every entry so you can quit and resume anytime

Usage:
    python cv/annotate_figures.py --meta data/cv/metadata/extracted_figures.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
from pathlib import Path

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

FIGURE_TYPES = ["rash_image", "lab_chart", "histology", "pathway_diagram", "other"]


def open_image(path: str) -> None:
    try:
        subprocess.Popen(["open", path])
    except Exception:
        print(f"  (Could not auto-open image: {path})")


def load_rows(meta_path: Path) -> list[dict]:
    with meta_path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_rows(meta_path: Path, rows: list[dict]) -> None:
    with meta_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def is_annotated(row: dict) -> bool:
    return row.get("figure_type", "unlabeled") != "unlabeled"


def prompt_figure_type() -> str | None:
    """Returns a figure_type string, or None if the user wants to delete."""
    options = FIGURE_TYPES + ["DELETE"]
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        raw = input(f"Select [1-{len(options)}]: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            chosen = options[int(raw) - 1]
            return None if chosen == "DELETE" else chosen
        print("  Invalid choice, try again.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", type=str, required=True)
    args = ap.parse_args()

    meta_path = Path(args.meta)
    rows = load_rows(meta_path)

    todo = [r for r in rows if not is_annotated(r)]
    done = len(rows) - len(todo)

    print(f"\n=== Figure Annotation ===")
    print(f"Total: {len(rows)} | Annotated: {done} | Remaining: {len(todo)}")
    print("Press Ctrl+C at any time to save and quit.\n")

    to_remove = []

    for i, row in enumerate(rows):
        if is_annotated(row):
            continue

        print(f"--- [{i + 1}/{len(rows)}] {Path(row['file_path']).name} | Disease: {row['disease']} ---")
        if row.get("caption"):
            print(f"  Caption: {row['caption'][:120]}")
        open_image(row["file_path"])

        try:
            figure_type = prompt_figure_type()
        except (KeyboardInterrupt, EOFError):
            print("\nSaving progress and quitting...")
            rows = [r for r in rows if r not in to_remove]
            save_rows(meta_path, rows)
            return 0

        if figure_type is None:
            print("  Deleted.\n")
            try:
                os.remove(row["file_path"])
            except FileNotFoundError:
                pass
            to_remove.append(row)
        else:
            row["figure_type"] = figure_type
            print(f"  Labeled as: {figure_type}\n")

        rows_to_save = [r for r in rows if r not in to_remove]
        save_rows(meta_path, rows_to_save)

    rows = [r for r in rows if r not in to_remove]
    save_rows(meta_path, rows)
    print(f"Done! {len(rows)} figures annotated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
