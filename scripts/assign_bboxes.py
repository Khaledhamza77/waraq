"""
Assign bounding boxes from output.json to leaf sections in index.json.
Writes data/bbox_map.json keyed by leaf section id.

Detection units are built from the index tree:
- Any leaf node becomes its own unit.
- Exception: in sections 4-9, a depth-2 node whose children are all leaves
  AND whose page span is <= 2 is aggregated into one unit (parent title,
  all children ids share the same bounding boxes).
- Depth-2 nodes in sections 4-9 with span > 2 are NOT aggregated; each
  level-3 child becomes its own individual unit.

Matching strategy (two passes):
  Pass 1 — line-anchored regex on normalised Arabic text: title must occupy
            its own line in the chunk (Option B).
  Pass 2 — flattened substring fallback: collapse all whitespace in both
            title and chunk, then check for substring. Catches multi-line
            split titles.
Unmatched units are flagged at the end for manual review.
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
INDEX_FILE = ROOT / "data" / "index.json"
OUTPUT_FILE = ROOT / "data" / "parsed" / "output.json"
MAP_FILE = ROOT / "data" / "bbox_map.json"

GAZETTE_MARKER = "الوقائع المصرية"  # الوقائع المصرية
AGGREGATION_PAGE_SPAN_LIMIT = 2


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def normalize_ar(text: str) -> str:
    """Normalise for matching: NFC, strip tashkeel, unify hamza on alef,
    collapse horizontal whitespace — but preserve newlines."""
    text = unicodedata.normalize("NFC", text)
    # Strip tashkeel (U+064B..U+065F and U+0670)
    text = re.sub(r"[ً-ٰٟ]", "", text)
    # Unify hamza variants on alef to bare alef
    text = text.replace("أ", "ا")  # أ -> ا
    text = text.replace("إ", "ا")  # إ -> ا
    text = text.replace("آ", "ا")  # آ -> ا
    # Collapse horizontal whitespace but keep newlines
    text = re.sub(r"[^\S\n]+", " ", text)
    # Collapse spaces inside parentheses: ( أ ) -> (أ)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    return text.strip()


def normalize_ar_flat(text: str) -> str:
    """Like normalize_ar but also collapses newlines to a single space.
    Used for the fallback substring match."""
    text = normalize_ar(text)
    return re.sub(r"\s+", " ", text).strip()


def clean_chunk(markdown: str) -> str:
    """Remove anchor tags, heading markers, and bold markers."""
    text = re.sub(r"<a id='[^']*'></a>", "", markdown)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = text.replace("**", "")
    return text.strip()


def match_pass1(title_norm: str, chunk_markdown: str) -> int:
    """Line-anchored match. Returns match start position or -1."""
    cleaned = normalize_ar(clean_chunk(chunk_markdown))
    pattern = r"(?:^|\n)\s*" + re.escape(title_norm) + r"\s*(?:\n|$)"
    m = re.search(pattern, cleaned)
    return m.start() if m else -1


def match_pass2(title_flat: str, chunk_markdown: str) -> bool:
    """Flattened substring fallback. Returns True if title found."""
    cleaned_flat = normalize_ar_flat(clean_chunk(chunk_markdown))
    return title_flat in cleaned_flat


# ---------------------------------------------------------------------------
# Detection unit builder
# ---------------------------------------------------------------------------

def build_detection_units(sections: list) -> list:
    """
    Returns an ordered list of detection units. Each unit is a dict:
        ids        : list of leaf section ids mapped to this unit
        title      : title used for chunk matching
        start_page : int
        end_page   : int
    """
    units = []

    def walk(node: dict, depth: int):
        sid = node.get("id", "")
        parts = sid.split("_")
        sec_num = int(parts[1]) if len(parts) > 1 else 0
        has_children = "children" in node

        if not has_children:
            if "start_page" not in node:
                return
            units.append({
                "ids": [sid],
                "title": node["title"],
                "start_page": node["start_page"],
                "end_page": node["end_page"],
            })

        else:
            # Check aggregation eligibility for sections 4-9 at depth 2
            if sec_num >= 4 and depth == 2:
                children = node["children"]
                leaf_children = [c for c in children if "children" not in c and "start_page" in c]
                non_leaf_children = [c for c in children if "children" in c]

                if leaf_children and not non_leaf_children:
                    span_start = min(c["start_page"] for c in leaf_children)
                    span_end = max(c["end_page"] for c in leaf_children)
                    span = span_end - span_start

                    if span <= AGGREGATION_PAGE_SPAN_LIMIT:
                        units.append({
                            "ids": [c["id"] for c in leaf_children],
                            "title": node["title"],
                            "start_page": span_start,
                            "end_page": span_end,
                        })
                        return

            for child in node["children"]:
                walk(child, depth + 1)

    for section in sections:
        walk(section, 1)

    return units


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    output = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))

    chunks = sorted(
        output["chunks"],
        key=lambda c: (c["grounding"]["page"], c["grounding"]["box"]["top"]),
    )

    units = build_detection_units(index["sections"])
    units.sort(key=lambda u: u["start_page"])

    print(f"Total detection units : {len(units)}")
    print(f"Total chunks          : {len(chunks)}")

    # ------------------------------------------------------------------
    # Step 1: find start chunk index for each unit
    # ------------------------------------------------------------------
    for unit in units:
        title_norm = normalize_ar(unit["title"])
        title_flat = normalize_ar_flat(unit["title"])
        matched_idx = None
        matched_via = None

        for i, chunk in enumerate(chunks):
            page = chunk["grounding"]["page"]
            if page < unit["start_page"]:
                continue
            if page > unit["end_page"]:
                break
            if GAZETTE_MARKER in chunk["markdown"]:
                continue

            # Pass 1: line-anchored
            if match_pass1(title_norm, chunk["markdown"]) >= 0:
                matched_idx = i
                matched_via = "line"
                break

        # Pass 2 fallback: flattened substring (only if pass 1 found nothing)
        if matched_idx is None:
            for i, chunk in enumerate(chunks):
                page = chunk["grounding"]["page"]
                if page < unit["start_page"]:
                    continue
                if page > unit["end_page"]:
                    break
                if GAZETTE_MARKER in chunk["markdown"]:
                    continue

                if match_pass2(title_flat, chunk["markdown"]):
                    matched_idx = i
                    matched_via = "flat"
                    break

        unit["start_idx"] = matched_idx
        unit["match_via"] = matched_via

    # ------------------------------------------------------------------
    # Step 2: assign bounding boxes
    # ------------------------------------------------------------------
    bbox_map = {}
    unmatched = []
    flat_matches = []

    for i, unit in enumerate(units):
        if unit["start_idx"] is None:
            unmatched.append(unit)
            entry = {"start_box": None, "end_box": None}
        else:
            if unit["match_via"] == "flat":
                flat_matches.append(unit)

            start_chunk = chunks[unit["start_idx"]]
            start_box = {
                "chunk_id": start_chunk["id"],
                "page": start_chunk["grounding"]["page"],
                "box": start_chunk["grounding"]["box"],
            }

            # End box = chunk just before next matched unit's start chunk.
            next_start_idx = None
            for j in range(i + 1, len(units)):
                if units[j]["start_idx"] is not None:
                    next_start_idx = units[j]["start_idx"]
                    break

            if next_start_idx is not None and next_start_idx > 0:
                # Walk back from the chunk before next unit's start, skipping gazette headers
                end_idx = next_start_idx - 1
                while end_idx > unit["start_idx"] and GAZETTE_MARKER in chunks[end_idx]["markdown"]:
                    end_idx -= 1
                end_chunk = chunks[end_idx]
            else:
                end_page = unit["end_page"]
                candidates = [
                    c for c in chunks
                    if c["grounding"]["page"] <= end_page and GAZETTE_MARKER not in c["markdown"]
                ]
                end_chunk = candidates[-1] if candidates else start_chunk

            end_box = {
                "chunk_id": end_chunk["id"],
                "page": end_chunk["grounding"]["page"],
                "box": end_chunk["grounding"]["box"],
            }

            entry = {"start_box": start_box, "end_box": end_box}

        for leaf_id in unit["ids"]:
            bbox_map[leaf_id] = entry

    # ------------------------------------------------------------------
    # Step 3: write output
    # ------------------------------------------------------------------
    MAP_FILE.write_text(
        json.dumps(bbox_map, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    matched = len(units) - len(unmatched)
    print(f"\nMatched   : {matched}/{len(units)} units")
    print(f"  via line-anchor : {matched - len(flat_matches)}")
    print(f"  via flat-substr : {len(flat_matches)}")
    print(f"Unmatched : {len(unmatched)}/{len(units)} units")
    print(f"Leaf entries written : {len(bbox_map)}")
    print(f"Output : {MAP_FILE}")

    if flat_matches:
        print("\n--- FLAT-SUBSTRING MATCHES (verify these) ---")
        for u in flat_matches:
            print(f"  {u['ids'][0] if len(u['ids'])==1 else u['ids']} | {u['title']!r} | pages {u['start_page']}-{u['end_page']}")

    if unmatched:
        print("\n--- UNMATCHED UNITS (require manual bbox entry) ---")
        for u in unmatched:
            print(f"  ids={u['ids']}")
            print(f"  title={u['title']!r}")
            print(f"  pages={u['start_page']}-{u['end_page']}")
            print()
    else:
        print("\nAll units matched successfully.")


if __name__ == "__main__":
    main()
