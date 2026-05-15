"""
Script 2 — LLM-assisted section hook rebuild.

Targets all non-leaf nodes in sections 3–9 of data/index.json and regenerates
their hooks using the section's table-of-contents page, introduction pages, and
the current hooks of its direct children.

Leaves (nodes without children) are never touched.

Processing order is post-order (children before parents) so that when a parent
node is rebuilt, its direct children already have their freshly rebuilt hooks.

Idempotent in the sense that it always overwrites — run it again to regenerate.
Atomic saves: index.json is written via a .tmp sibling after each node.

Usage:
    python scripts/rebuild_section_hooks.py [--dry-run]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
INDEX_PATH = ROOT / "data" / "index.json"
PAGES_DIR = ROOT / "data" / "parsed" / "markdown" / "pages"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

from tqdm import tqdm

from normalize_hooks import normalize_hook
from waraq.llm.client import get_client
from waraq.navigation.prompts import rebuild_section_prompt, rebuild_section_system

# Only these top-level sections are in scope.
REBUILD_SECTION_IDS = {
    "section_3",
    "section_4",
    "section_5",
    "section_6",
    "section_7",
    "section_8",
    "section_9",
}


# ── Index I/O ─────────────────────────────────────────────────────────────────

def load_index() -> dict:
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def save_index(data: dict) -> None:
    tmp = INDEX_PATH.with_name(INDEX_PATH.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
    tmp.replace(INDEX_PATH)


# ── Page reading ──────────────────────────────────────────────────────────────

def read_page_list(pages: list) -> str:
    """Read and join content from a list of page numbers (int or str)."""
    parts = []
    for p in pages:
        page_file = PAGES_DIR / f"page_{int(p)}.md"
        if page_file.exists():
            text = page_file.read_text(encoding="utf-8").strip()
            if text:
                parts.append(text)
    return "\n\n".join(parts)


# ── Node counting ─────────────────────────────────────────────────────────────

def _count_non_leaves(node: dict) -> int:
    children = node.get("children", [])
    if not children:
        return 0
    return 1 + sum(_count_non_leaves(c) for c in children)


# ── Core traversal ────────────────────────────────────────────────────────────

def process_node(
    node: dict,
    index_data: dict,
    client,
    bar: tqdm,
    dry_run: bool,
) -> None:
    """Post-order: recurse into children first, then rebuild this node."""
    children = node.get("children", [])

    for child in children:
        process_node(child, index_data, client, bar, dry_run)

    if not children:
        return  # leaf — skip

    node_id = node.get("id", "?")

    # Collect TOC page content
    toc_page = node.get("contents_page")
    toc_content = read_page_list([toc_page]) if toc_page else None

    # Collect introduction pages content
    intro_pages = node.get("introduction_pages") or []
    intro_content = read_page_list(intro_pages) if intro_pages else None

    # Collect direct children hooks (skip any child without a hook)
    child_hooks = [c["hook"] for c in children if c.get("hook")]

    bar.set_postfix_str(f"rebuilding: {node_id}", refresh=True)

    if dry_run:
        old_hook = node.get("hook", "")
        bar.write(f"\n[{node_id}]")
        bar.write(f"  toc_page={toc_page}  intro_pages={intro_pages}  children={len(child_hooks)}")
        bar.write(f"  CURRENT: {str(old_hook)[:120]!r}")
        bar.update(1)
        return

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

    node["hook"] = normalize_hook(hook)
    save_index(index_data)
    bar.update(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    dry_run = "--dry-run" in sys.argv

    if not INDEX_PATH.exists():
        print(f"ERROR: {INDEX_PATH} not found")
        sys.exit(1)
    if not PAGES_DIR.exists():
        print(f"ERROR: {PAGES_DIR} not found")
        sys.exit(1)

    index_data = load_index()
    sections = index_data.get("sections", [])

    target_sections = [s for s in sections if s.get("id") in REBUILD_SECTION_IDS]
    total = sum(_count_non_leaves(s) for s in target_sections)

    mode = " (DRY RUN)" if dry_run else ""
    print(f"Rebuilding section hooks{mode} — {total} non-leaf nodes across {len(target_sections)} sections\n")

    client = None if dry_run else get_client()

    with tqdm(total=total, unit="node", dynamic_ncols=True) as bar:
        for section in target_sections:
            bar.write(f"Section: {section.get('id')} — {section.get('title')}")
            process_node(section, index_data, client, bar, dry_run)

    print(f"\nDone{mode}.")


if __name__ == "__main__":
    main()
