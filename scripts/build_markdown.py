"""
Merge all chunks from data/parsed/output.json into markdown files.
Chunks are sorted by page then by vertical position (grounding.box.top)
to preserve reading order.

Outputs:
  data/parsed/markdown/document.md        — full document, all pages
  data/parsed/markdown/pages/page_N.md   — one file per page
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
INPUT_PATH = ROOT / "data" / "parsed" / "output.json"
MARKDOWN_DIR = ROOT / "data" / "parsed" / "markdown"
PAGES_DIR = MARKDOWN_DIR / "pages"
DOCUMENT_PATH = MARKDOWN_DIR / "document.md"


def main() -> None:
    if not INPUT_PATH.exists():
        print(f"Error: {INPUT_PATH} not found — run run_ingestion.py first.", file=sys.stderr)
        sys.exit(1)

    data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    chunks = data.get("chunks") or []

    if not chunks:
        print("Warning: no chunks found in output.json.", file=sys.stderr)
        sys.exit(1)

    MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
    PAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Sort by page, then by vertical position within the page
    def sort_key(chunk: dict) -> tuple:
        grounding = chunk.get("grounding") or {}
        page = grounding.get("page") if grounding.get("page") is not None else float("inf")
        top = (grounding.get("box") or {}).get("top", float("inf"))
        return (page, top)

    chunks_sorted = sorted(chunks, key=sort_key)

    # Group chunks by page
    pages: dict[int, list[str]] = {}
    skipped_no_page = 0
    for chunk in chunks_sorted:
        grounding = chunk.get("grounding") or {}
        page = grounding.get("page")
        markdown = (chunk.get("markdown") or "").strip()
        if not markdown:
            continue
        if page is None:
            skipped_no_page += 1
            continue
        pages.setdefault(page, []).append(markdown)

    if skipped_no_page:
        print(f"Warning: skipped {skipped_no_page} chunk(s) with no page number.")

    # Write individual page files
    for page_num, page_chunks in sorted(pages.items()):
        page_path = PAGES_DIR / f"page_{page_num}.md"
        page_path.write_text("\n\n".join(page_chunks), encoding="utf-8")

    # Write full document
    doc_lines = []
    for page_num, page_chunks in sorted(pages.items()):
        if doc_lines:
            doc_lines.append("\n---\n")
        doc_lines.append(f"<!-- page {page_num} -->\n")
        doc_lines.append("\n\n".join(page_chunks))

    DOCUMENT_PATH.write_text("\n".join(doc_lines), encoding="utf-8")

    print(f"Pages written : {len(pages)} → {PAGES_DIR}")
    print(f"Full document : {DOCUMENT_PATH}")


if __name__ == "__main__":
    main()
