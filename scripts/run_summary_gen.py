"""
Stage 4 — Summary generation (bottom-up).

Reads data/index.json and data/parsed/markdown/pages/page_N.md.
Writes Arabic hook summaries into every node in index.json.

Idempotent: nodes with an existing non-null hook are skipped.
Atomic saves: index.json is written via a .tmp sibling to prevent corruption
on interruption. Re-running resumes from where it stopped.

Usage:
    python scripts/run_summary_gen.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
INDEX_PATH = ROOT / "data" / "index.json"
PAGES_DIR = ROOT / "data" / "parsed" / "markdown" / "pages"

sys.path.insert(0, str(ROOT))

from waraq.llm.client import get_client
from waraq.navigation.prompts import (
    rollup_prompt,
    rollup_system,
    summarize_leaf_prompt,
    summarize_leaf_system,
)


def load_index() -> dict:
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def save_index(data: dict) -> None:
    tmp = INDEX_PATH.with_name(INDEX_PATH.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
    tmp.replace(INDEX_PATH)


def read_pages(start: int, end: int) -> str:
    parts = []
    for n in range(start, end + 1):
        page_file = PAGES_DIR / f"page_{n}.md"
        if page_file.exists():
            text = page_file.read_text(encoding="utf-8").strip()
            if text:
                parts.append(text)
    return "\n\n".join(parts)


def is_leaf(node: dict) -> bool:
    return "children" not in node or not node["children"]


# Common Arabic preamble phrases models sometimes emit before the actual content
_PREAMBLE_PREFIXES = (
    "بالطبع",
    "بكل سرور",
    "إليك",
    "فيما يلي",
    "يمكنني",
    "سأقوم",
    "الملخص:",
    "الإجابة:",
)


def _clean_hook(text: str) -> str:
    text = text.strip()
    for prefix in _PREAMBLE_PREFIXES:
        if text.startswith(prefix):
            # Strip the prefix itself, then any immediately following punctuation/whitespace
            text = text[len(prefix):].lstrip(" :\n،,.")
            break
    return text


def process_node(node: dict, index_data: dict, client) -> None:
    """Post-order: process children first, then this node."""
    children = node.get("children", [])

    for child in children:
        process_node(child, index_data, client)

    node_id = node.get("id", "?")

    if node.get("hook") is not None:
        print(f"  skip (already done): {node_id}")
        return

    if is_leaf(node):
        start = node.get("start_page")
        end = node.get("end_page")
        if start is None or end is None:
            print(f"  skip (no page range): {node_id}")
            return

        content = read_pages(start, end)
        if not content:
            print(f"  skip (no content found for pages {start}-{end}): {node_id}")
            return

        print(f"  leaf [{start}-{end}]: {node_id} ...", end=" ", flush=True)
        try:
            hook = client.complete(
                prompt=summarize_leaf_prompt(node.get("title", ""), content),
                system=summarize_leaf_system(),
            )
        except Exception as exc:
            print(f"\nERROR on {node_id}: {exc}")
            sys.exit(1)
        node["hook"] = _clean_hook(hook)
        save_index(index_data)
        print("done")

    else:
        child_hooks = [c["hook"] for c in children if c.get("hook")]
        if not child_hooks:
            print(f"  skip (no child hooks available): {node_id}")
            return

        print(f"  rollup ({len(child_hooks)} children): {node_id} ...", end=" ", flush=True)
        try:
            hook = client.complete(
                prompt=rollup_prompt(node.get("title", ""), child_hooks),
                system=rollup_system(),
            )
        except Exception as exc:
            print(f"\nERROR on {node_id}: {exc}")
            sys.exit(1)
        node["hook"] = _clean_hook(hook)
        save_index(index_data)
        print("done")


def main() -> None:
    if not INDEX_PATH.exists():
        print(f"ERROR: {INDEX_PATH} not found")
        sys.exit(1)

    if not PAGES_DIR.exists():
        print(f"ERROR: {PAGES_DIR} not found")
        sys.exit(1)

    client = get_client()
    index_data = load_index()
    sections = index_data.get("sections", [])

    print(f"Starting summary generation for {len(sections)} top-level sections...\n")

    for section in sections:
        print(f"Section: {section.get('id')} — {section.get('title')}")
        process_node(section, index_data, client)
        print()

    nulls = []

    def count_nulls(node):
        if node.get("hook") is None:
            nulls.append(node.get("id"))
        for child in node.get("children", []):
            count_nulls(child)

    for s in sections:
        count_nulls(s)

    print(f"\nDone. Nodes still without a hook: {len(nulls)}")
    if nulls:
        print("  " + "\n  ".join(nulls))


if __name__ == "__main__":
    main()
