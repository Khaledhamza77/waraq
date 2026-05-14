"""
One-time utility: remerge part_N.json checkpoints into output.json with
correct full-document page numbers.

Use this if output.json is missing or has wrong page numbers while the
per-chunk checkpoints (data/parsed/part_N.json) are intact. Safe to re-run.
"""

import json
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).parent.parent
PDF_PATH = ROOT / "data" / "عينة_من_معايير_المحاسبة_المصرية_2020.pdf"
PARSED_DIR = ROOT / "data" / "parsed"
OUTPUT_PATH = PARSED_DIR / "output.json"
MAX_PAGES = 100


def main() -> None:
    if not PDF_PATH.exists():
        print(f"Error: PDF not found at {PDF_PATH}", file=sys.stderr)
        sys.exit(1)

    doc = fitz.open(PDF_PATH)
    try:
        total_pages = doc.page_count
    finally:
        doc.close()

    # Reconstruct the same ranges as run_ingestion.py
    ranges = []
    start = 0
    while start < total_pages:
        end = min(start + MAX_PAGES - 1, total_pages - 1)
        ranges.append((start, end))
        start = end + 1

    all_chunks = []

    for part_idx, (part_start, part_end) in enumerate(ranges):
        checkpoint = PARSED_DIR / f"part_{part_idx}.json"
        if not checkpoint.exists():
            print(f"Error: {checkpoint.name} not found — cannot merge.", file=sys.stderr)
            sys.exit(1)

        try:
            part_data = json.loads(checkpoint.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(
                f"Error: {checkpoint.name} is corrupt (partial write). "
                f"Delete it and re-run run_ingestion.py to re-parse this chunk.",
                file=sys.stderr,
            )
            sys.exit(1)
        chunks = part_data.get("chunks") or []

        raw_pages = [
            c["grounding"]["page"]
            for c in chunks
            if c.get("grounding") and c["grounding"].get("page") is not None
        ]
        if not raw_pages:
            print(f"Warning: no page numbers in {checkpoint.name}, including as-is.")
            all_chunks.extend(chunks)
            continue

        min_raw = min(raw_pages)
        # Target: 1-indexed position of this chunk's first page in the full document
        target_start = part_start + 1
        shift = target_start - min_raw

        if shift != 0:
            print(f"Part {part_idx} (pages {part_start + 1}–{part_end + 1}): shifting by {shift:+d}  (was {min_raw}, now {target_start})")
            for chunk in chunks:
                if chunk.get("grounding") and chunk["grounding"].get("page") is not None:
                    chunk["grounding"]["page"] += shift
        else:
            print(f"Part {part_idx} (pages {part_start + 1}–{part_end + 1}): pages already correct (start={min_raw})")

        all_chunks.extend(chunks)

    merged = {"chunks": all_chunks}
    _atomic_write(OUTPUT_PATH, json.dumps(merged, ensure_ascii=False, indent=2))
    print(f"\nMerged {len(all_chunks)} chunks → {OUTPUT_PATH}")


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


if __name__ == "__main__":
    main()
