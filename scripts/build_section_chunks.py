"""
Build data/section_chunks.json

Source of truth: data/bbox_map.json — only sections with non-null start_box/end_box
get entries.  start_box.chunk_id and end_box.chunk_id are the first and last chunks
belonging to that section in document order.

output.json preserves document order, so we build a flat ordered list once and slice
[start_idx : end_idx + 1] for each section — no page-range approximation.

data/index.json is used solely to enrich each section with its title and hook.

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
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

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

    # Flat ordered list of chunks in document order (output.json preserves this).
    # Also build a chunk_id → position index for O(1) lookup.
    all_chunks: list[dict] = []
    chunk_id_to_index: dict[str, int] = {}
    for i, chunk in enumerate(output["chunks"]):
        all_chunks.append({
            "chunk_id": chunk["id"],
            "page":     chunk["grounding"]["page"],
            "box":      chunk["grounding"]["box"],
            "markdown": chunk.get("markdown", ""),
            "type":     chunk["type"],
        })
        chunk_id_to_index[chunk["id"]] = i

    # Build section_chunks by slicing the ordered chunk list between start and end IDs.
    result: dict[str, dict] = {}
    skipped_null    = 0
    skipped_missing = 0

    for section_id, bbox_entry in bbox_map.items():
        start_box = bbox_entry.get("start_box")
        end_box   = bbox_entry.get("end_box")

        if start_box is None or end_box is None:
            skipped_null += 1
            continue

        start_chunk_id = start_box["chunk_id"]
        end_chunk_id   = end_box["chunk_id"]

        start_idx = chunk_id_to_index.get(start_chunk_id)
        end_idx   = chunk_id_to_index.get(end_chunk_id)

        if start_idx is None or end_idx is None:
            print(f"  WARNING: chunk not found for section {section_id} "
                  f"(start={start_chunk_id}, end={end_chunk_id})")
            skipped_missing += 1
            continue

        if start_idx > end_idx:
            print(f"  WARNING: start_idx > end_idx for section {section_id}, swapping")
            start_idx, end_idx = end_idx, start_idx

        meta = id_to_meta.get(section_id, {"title": section_id, "hook": ""})
        result[section_id] = {
            "title":      meta["title"],
            "hook":       meta["hook"],
            "start_page": start_box["page"],
            "end_page":   end_box["page"],
            "chunks":     all_chunks[start_idx : end_idx + 1],
        }

    print(f"Skipped {skipped_null} sections with null bbox entries.")
    if skipped_missing:
        print(f"Skipped {skipped_missing} sections with missing chunk IDs.")
    print(f"Built data for {len(result)} sections …")
    OUT_FILE.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    total_chunks = sum(len(v["chunks"]) for v in result.values())
    print(f"Done. {len(result)} sections / {total_chunks} chunk-section pairs -> {OUT_FILE}")


if __name__ == "__main__":
    main()
