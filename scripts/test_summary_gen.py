"""
Test for Stage 4 — Summary generation.

Runs the same bottom-up hook generation logic against data/index-test.json
(section_2, pages 8-13) instead of the real index.json.

After the run you can inspect the filled hooks and verify:
  - All 4 nodes (3 leaves + 1 rollup parent) have non-null hooks
  - Hooks are coherent Arabic paragraphs relevant to each section title
  - No Arabic preamble phrases leaked through (بالطبع, إليك, etc.)

index-test.json is reset to all-null hooks at the start of each run
so the test is always repeatable.

Usage:
    python scripts/test_summary_gen.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
TEST_INDEX_PATH = ROOT / "data" / "index-test.json"
TEST_OUTPUT_PATH = ROOT / "data" / "index-test-output.json"
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
            text = text[len(prefix):].lstrip(" :\n،,.")
            break
    return text


def _reset_hooks(node: dict) -> None:
    node["hook"] = None
    for child in node.get("children", []):
        _reset_hooks(child)


def _count_nodes(node: dict) -> int:
    return 1 + sum(_count_nodes(c) for c in node.get("children", []))


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


def process_node(node: dict, client, bar: tqdm, breadcrumb: list[str] | None = None) -> None:
    if breadcrumb is None:
        breadcrumb = []

    children = node.get("children", [])
    child_breadcrumb = breadcrumb + [node.get("title", "")]

    for child in children:
        process_node(child, client, bar, child_breadcrumb)

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
        bar.update(1)


def main() -> None:
    if not TEST_INDEX_PATH.exists():
        print(f"ERROR: {TEST_INDEX_PATH} not found")
        sys.exit(1)

    if not PAGES_DIR.exists():
        print(f"ERROR: {PAGES_DIR} not found")
        sys.exit(1)

    index_data = json.loads(TEST_INDEX_PATH.read_text(encoding="utf-8"))
    sections = index_data.get("sections", [])

    # Reset all hooks so each test run starts clean
    for s in sections:
        _reset_hooks(s)

    client = get_client()
    total_nodes = sum(_count_nodes(s) for s in sections)
    document_title = index_data.get("document", {}).get("title", "")
    root_breadcrumb = [document_title] if document_title else []

    print(f"TEST — running summary gen on index-test.json ({total_nodes} nodes)\n")

    with tqdm(total=total_nodes, unit="node", dynamic_ncols=True) as bar:
        for section in sections:
            bar.write(f"Section: {section.get('id')} — {section.get('title')}")
            process_node(section, client, bar, root_breadcrumb)

    # Write filled hooks to disk for inspection
    TEST_OUTPUT_PATH.write_text(
        json.dumps(index_data, ensure_ascii=False, indent=4), encoding="utf-8"
    )
    print(f"\nOutput written to {TEST_OUTPUT_PATH.relative_to(ROOT)}\n")

    # Assertions
    print("--- Results ---\n")
    passed = 0
    failed = 0

    def check_node(node):
        nonlocal passed, failed
        node_id = node.get("id", "?")
        hook = node.get("hook")
        if hook and len(hook.strip()) > 10:
            print(f"  PASS  {node_id}")
            print(f"        {hook[:120]}{'...' if len(hook) > 120 else ''}\n")
            passed += 1
        else:
            print(f"  FAIL  {node_id} — hook is null or too short: {hook!r}\n")
            failed += 1
        for child in node.get("children", []):
            check_node(child)

    for s in sections:
        check_node(s)

    print(f"Passed: {passed} / {passed + failed}")
    if failed:
        print(f"Failed: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
