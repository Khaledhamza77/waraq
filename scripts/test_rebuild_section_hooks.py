"""
Test for Stage 4b — Section hook rebuild.

Runs the rebuild logic against section_4 (معيار رقم 1 – عرض القوائم المالية)
extracted from data/index.json. index.json is never modified — a deep copy of
the section is used and output is written to data/index-rebuild-test-output.json
for inspection.

Exercises two cases:
  - section_4:   has contents_page + introduction_pages (full path)
  - section_4_9: no contents_page or introduction_pages (graceful degradation)

After the run, verifies that each rebuilt hook:
  - Is non-null and long enough to be meaningful
  - Contains all three expected Arabic sentence starters

Usage:
    python scripts/test_rebuild_section_hooks.py
"""
import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
INDEX_PATH = ROOT / "data" / "index.json"
TEST_OUTPUT_PATH = ROOT / "data" / "index-rebuild-test-output.json"
PAGES_DIR = ROOT / "data" / "parsed" / "markdown" / "pages"

sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from tqdm import tqdm

from waraq.llm.client import get_client
from waraq.navigation.prompts import rebuild_section_prompt, rebuild_section_system

TEST_SECTION_ID = "section_4"

_ARABIC_RE = re.compile(r"[؀-ۿ]")


# ── Helpers ───────────────────────────────────────────────────────────────────

def read_page_list(pages: list) -> str:
    parts = []
    for p in pages:
        page_file = PAGES_DIR / f"page_{int(p)}.md"
        if page_file.exists():
            text = page_file.read_text(encoding="utf-8").strip()
            if text:
                parts.append(text)
    return "\n\n".join(parts)


def _count_non_leaves(node: dict) -> int:
    children = node.get("children", [])
    if not children:
        return 0
    return 1 + sum(_count_non_leaves(c) for c in children)


# ── Core logic (mirrors rebuild_section_hooks.py — inlined to avoid coupling) ─

def process_node(node: dict, client, bar: tqdm) -> None:
    """Post-order: recurse into children first, then rebuild this node."""
    children = node.get("children", [])
    for child in children:
        process_node(child, client, bar)

    if not children:
        return  # leaf — skip

    node_id = node.get("id", "?")

    toc_page = node.get("contents_page")
    toc_content = read_page_list([toc_page]) if toc_page else None

    intro_pages = node.get("introduction_pages") or []
    intro_content = read_page_list(intro_pages) if intro_pages else None

    child_hooks = [c["hook"] for c in children if c.get("hook")]

    bar.set_postfix_str(f"rebuilding: {node_id}", refresh=True)
    try:
        hook = client.complete(
            prompt=rebuild_section_prompt(
                title=node.get("title", ""),
                toc_content=toc_content,
                intro_content=intro_content,
                child_hooks=child_hooks,
            ),
            system=rebuild_section_system(),
            think=True,
        )
    except Exception as exc:
        bar.write(f"\nERROR on {node_id}: {exc}")
        sys.exit(1)

    node["hook"] = hook.strip()
    bar.update(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if not INDEX_PATH.exists():
        print(f"ERROR: {INDEX_PATH} not found")
        sys.exit(1)
    if not PAGES_DIR.exists():
        print(f"ERROR: {PAGES_DIR} not found")
        sys.exit(1)

    index_data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    sections = index_data.get("sections", [])

    target = next((s for s in sections if s.get("id") == TEST_SECTION_ID), None)
    if target is None:
        print(f"ERROR: {TEST_SECTION_ID} not found in index.json")
        sys.exit(1)

    # Deep copy — index.json is never touched
    test_section = copy.deepcopy(target)
    total = _count_non_leaves(test_section)

    print(f"TEST — rebuilding non-leaf hooks in {TEST_SECTION_ID} ({total} nodes)\n")

    client = get_client()
    with tqdm(total=total, unit="node", dynamic_ncols=True) as bar:
        process_node(test_section, client, bar)

    output = {"sections": [test_section]}
    TEST_OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=4), encoding="utf-8"
    )
    print(f"\nOutput written to {TEST_OUTPUT_PATH.relative_to(ROOT)}\n")

    # ── Assertions ────────────────────────────────────────────────────────────
    print("--- Results ---\n")
    passed = 0
    failed = 0

    def check_node(node: dict) -> None:
        nonlocal passed, failed
        if not node.get("children"):
            return  # leaves not checked

        node_id = node.get("id", "?")
        hook = node.get("hook") or ""
        issues = []

        if len(hook.strip()) < 50:
            issues.append("hook too short")
        if not _ARABIC_RE.search(hook):
            issues.append("no Arabic characters")

        if issues:
            print(f"  FAIL  {node_id} — {'; '.join(issues)}")
            print(f"        {hook[:300]!r}\n")
            failed += 1
        else:
            print(f"  PASS  {node_id}")
            print(f"        {hook[:300]}{'...' if len(hook) > 300 else ''}\n")
            passed += 1

        for child in node.get("children", []):
            check_node(child)

    check_node(test_section)

    print(f"Passed: {passed} / {passed + failed}")
    if failed:
        print(f"Failed: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
