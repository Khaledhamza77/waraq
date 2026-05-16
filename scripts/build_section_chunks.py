"""
Build data/section_chunks.json

Source of truth: data/bbox_map.json — only sections with non-null start_box/end_box
get entries.  For each such section the page range is [start_box.page, end_box.page].

All output.json chunks whose grounding.page falls in that range are collected as the
section's chunks.  data/index.json is used solely to enrich each section with its
title and hook (for display in the explorer sidebar).

Output schema:
{
  "section_id": {
    "title": "...",
    "hook": "...",
    "start_page": N,
    "end_page": M,
    "chunks": [
      {
        "chunk_id": "...",
        "page": N,
        "box": {"top": 0.x, "bottom": 0.x, "left": 0.x, "right": 0.x},
        "markdown": "...",
        "type": "text|figure|..."
      },
      ...
    ]
  },
  ...
}

Run once (idempotent — overwrites on re-run):
    python scripts/build_section_chunks.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
BBOX_MAP_FILE = ROOT / "data" / "bbox_map.json"
INDEX_FILE    = ROOT / "data" / "index.json"
OUTPUT_FILE   = ROOT / "data" / "parsed" / "output.json"
OUT_FILE      = ROOT / "data" / "section_chunks.json"


def _build_id_to_section(nodes: list[dict], acc: dict[str, dict] | None = None) -> dict[str, dict]:
    """Flatten index.json sections tree into {id: {title, hook}} lookup."""
    if acc is None:
        acc = {}
    for node in nodes:
        acc[node["id"]] = {"title": node.get("title", ""), "hook": node.get("hook", "")}
        _build_id_to_section(node.get("children", []), acc)
    return acc


def main() -> None:
    print("Loading bbox_map.json …")
    bbox_map: dict[str, dict] = json.loads(BBOX_MAP_FILE.read_text(encoding="utf-8"))

    print("Loading index.json …")
    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    id_to_meta = _build_id_to_section(index["sections"])

    print("Loading output.json …")
    output = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))

    # Build page → ordered list of chunks
    page_to_chunks: dict[int, list[dict]] = {}
    for chunk in output["chunks"]:
        page: int = chunk["grounding"]["page"]
        page_to_chunks.setdefault(page, []).append(
            {
                "chunk_id": chunk["id"],
                "page": page,
                "box": chunk["grounding"]["box"],
                "markdown": chunk.get("markdown", ""),
                "type": chunk["type"],
            }
        )

    # Build section_chunks from bbox_map as source of truth
    result: dict[str, dict] = {}
    skipped_null = 0
    for section_id, bbox_entry in bbox_map.items():
        start_box = bbox_entry.get("start_box")
        end_box   = bbox_entry.get("end_box")

        if start_box is None or end_box is None:
            skipped_null += 1
            continue  # no page info for this section

        start_page: int = start_box["page"]
        end_page: int   = end_box["page"]

        # Collect every chunk on pages in [start_page, end_page]
        chunks: list[dict] = []
        for p in range(start_page, end_page + 1):
            chunks.extend(page_to_chunks.get(p, []))

        meta = id_to_meta.get(section_id, {"title": section_id, "hook": ""})
        result[section_id] = {
            "title":      meta["title"],
            "hook":       meta["hook"],
            "start_page": start_page,
            "end_page":   end_page,
            "chunks":     chunks,
        }

    print(f"Skipped {skipped_null} sections with null bbox entries.")
    print(f"Built data for {len(result)} sections …")
    OUT_FILE.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    total_chunks = sum(len(v["chunks"]) for v in result.values())
    print(f"Done. {len(result)} sections / {total_chunks} chunk-section pairs → {OUT_FILE}")


if __name__ == "__main__":
    main()
