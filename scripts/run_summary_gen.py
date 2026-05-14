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

from tqdm import tqdm

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


def _count_nodes(node: dict) -> int:
    return 1 + sum(_count_nodes(c) for c in node.get("children", []))


def process_node(
    node: dict,
    index_data: dict,
    client,
    bar: tqdm,
    breadcrumb: list[str] | None = None,
) -> None:
    """Post-order: process children first, then this node."""
    if breadcrumb is None:
        breadcrumb = []

    children = node.get("children", [])
    child_breadcrumb = breadcrumb + [node.get("title", "")]

    for child in children:
        process_node(child, index_data, client, bar, child_breadcrumb)

    node_id = node.get("id", "?")

    if node.get("hook") is not None:
        bar.set_postfix_str(f"skip: {node_id}", refresh=True)
        bar.update(1)
        return

    if is_leaf(node):
        start = node.get("start_page")
        end = node.get("end_page")
        if start is None or end is None:
            bar.set_postfix_str(f"skip (no pages): {node_id}", refresh=True)
            bar.update(1)
            return

        content = read_pages(start, end)
        if not content:
            bar.set_postfix_str(f"skip (empty): {node_id}", refresh=True)
            bar.update(1)
            return

        bar.set_postfix_str(f"leaf [{start}-{end}]: {node_id}", refresh=True)
        try:
            hook = client.complete(
                prompt=summarize_leaf_prompt(node.get("title", ""), content, breadcrumb),
                system=summarize_leaf_system(),
            )
        except Exception as exc:
            bar.write(f"\nERROR on {node_id}: {exc}")
            sys.exit(1)
        node["hook"] = _clean_hook(hook)
        save_index(index_data)
        bar.update(1)

    else:
        child_hooks = [c["hook"] for c in children if c.get("hook")]
        if not child_hooks:
            bar.set_postfix_str(f"skip (no child hooks): {node_id}", refresh=True)
            bar.update(1)
            return

        bar.set_postfix_str(f"rollup ({len(child_hooks)} children): {node_id}", refresh=True)
        try:
            hook = client.complete(
                prompt=rollup_prompt(node.get("title", ""), child_hooks, breadcrumb),
                system=rollup_system(),
            )
        except Exception as exc:
            bar.write(f"\nERROR on {node_id}: {exc}")
            sys.exit(1)
        node["hook"] = _clean_hook(hook)
        save_index(index_data)
        bar.update(1)


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
    document_title = index_data.get("document", {}).get("title", "")

    total_nodes = sum(_count_nodes(s) for s in sections)
    print(f"Starting summary generation — {total_nodes} nodes across {len(sections)} top-level sections\n")

    root_breadcrumb = [document_title] if document_title else []

    with tqdm(total=total_nodes, unit="node", dynamic_ncols=True) as bar:
        for section in sections:
            bar.write(f"Section: {section.get('id')} — {section.get('title')}")
            process_node(section, index_data, client, bar, root_breadcrumb)

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
