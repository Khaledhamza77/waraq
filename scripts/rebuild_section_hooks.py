"""
Script 2 — LLM-assisted section hook rebuild.

Targets all non-leaf nodes in sections 3–9 of data/index.json and regenerates
their hooks using the section's table-of-contents page, introduction pages, and
the current hooks of its direct children.

TOC items are parsed directly from the raw page markdown (parse_toc_from_page)
and injected verbatim into the hook — the LLM only summarises the introduction
and child hooks, eliminating hallucinated table-of-contents entries.

Leaves (nodes without children) are never touched. Non-leaf nodes that have
neither a contents_page nor introduction_pages are also skipped — they lack
the document anchors needed for a quality rebuild.

Processing order is post-order (children before parents) so that when a parent
node is rebuilt, its direct children already have their freshly rebuilt hooks.

Idempotent in the sense that it always overwrites — run it again to regenerate.
Atomic saves: index.json is written via a .tmp sibling after each node.

Usage:
    python scripts/rebuild_section_hooks.py [--dry-run]
"""
import json
import re
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
from waraq.navigation.prompts import rebuild_intro_children_prompt, rebuild_intro_children_system

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


# ── TOC page parsing ──────────────────────────────────────────────────────────

# HTML: turn cell/row endings into newlines so parallel columns become separate lines
_HTML_CELL_END_RE = re.compile(r'</t[dh]>|</tr>', re.IGNORECASE)
# Strip proper HTML tags (must start with letter or /) — avoids matching <:: markers
_HTML_TAG_RE = re.compile(r'<[a-zA-Z/][^>]*>', re.DOTALL)
# Strip custom table open/close markers (<:: <::table: ::> : table::>)
# Use [ \t]* (not \s*) so the match stays on a single line and never consumes table content
_TABLE_MARKER_RE = re.compile(r'<::[a-z:]*[ \t]*\n?|:?[ \t]*(?:table[ \t]*)?::>[ \t]*\n?', re.IGNORECASE)
# Markdown table separator rows (| :--- | :--- |)
_MD_SEP_RE = re.compile(r'^[\|:>\s-]+$')
# Leading paragraph ref: optional 1-2 Arabic letter abbreviation + number + optional
# letter suffix (e.g. "٣٩-٤٢ ب") + 2+ spaces
# Covers: "هـ د ۱-۱۱  topic", "م م ٢-٦  topic", "٣-١  topic", "٣٩-٤٢ ب  topic"
_LEADING_REF_RE = re.compile(
    r'^(?:[ء-يهـ]{1,2}\s+)*'
    r'[٠-٩۰-۹\d][٠-٩۰-۹\d\-–/ء-يهـ]*'
    r'(?:\s+[ء-يهـ]{1,2})?'
    r'\s{2,}',
    re.UNICODE,
)
# Trailing paragraph ref: 2+ spaces then a contiguous number/code at end of line
# Covers: "هدف المعيار                ١", "نطاق المعيار    ٥-٢"
# No \s inside the code class — avoids accidentally stripping Arabic words after a number
_TRAILING_REF_RE = re.compile(
    r'\s{2,}[٠-٩۰-۹\d][٠-٩۰-۹\d\-–/ء-يهـ]*\s*$',
    re.UNICODE,
)
# A valid TOC item must contain at least one real Arabic word (3+ letters)
_ARABIC_WORD_RE = re.compile(r'[ء-يهـ]{3,}', re.UNICODE)


def parse_toc_from_page(raw_page: str) -> list[str]:
    """Return the list of TOC topic names from a raw page, stripping paragraph refs.

    Handles all TOC formats found in the Egyptian Accounting Standards PDF:
    plain text, HTML tables, custom <:: tables, Markdown tables, and
    mixed-alignment columns.
    """
    # Preserve HTML table cell structure — turn cell/row endings into newlines
    text = _HTML_CELL_END_RE.sub('\n', raw_page)
    # Strip remaining HTML tags
    text = _HTML_TAG_RE.sub('', text)
    # Strip custom table markers while keeping the content between them
    text = _TABLE_MARKER_RE.sub('', text)

    pos = text.find('المحتويات')
    if pos == -1:
        return []
    text = text[pos + len('المحتويات'):]

    items: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Skip Markdown table separator rows (| :--- | :--- |)
        if _MD_SEP_RE.match(line):
            continue

        # Markdown/custom table row — take the first non-empty cell (topic column)
        if '|' in line:
            cells = [c.strip() for c in line.split('|') if c.strip()]
            line = cells[0] if cells else ''

        # Skip noise keywords
        if line in ('فقرات', 'المحتويات'):
            continue
        if 'الوقائع' in line:
            continue

        # Strip leading paragraph ref codes (e.g. "٣-١      " or "هـ د ۱-۱۱  ")
        line = _LEADING_REF_RE.sub('', line).strip()
        # Strip trailing paragraph refs (e.g. "هدف المعيار       ١")
        line = _TRAILING_REF_RE.sub('', line).strip()

        # Keep only lines that contain at least one real Arabic word
        if not _ARABIC_WORD_RE.search(line):
            continue

        items.append(line)

    return items


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

def _count_to_rebuild(node: dict) -> int:
    children = node.get("children", [])
    if not children:
        return 0
    skip = not node.get("contents_page") and not node.get("introduction_pages")
    return (0 if skip else 1) + sum(_count_to_rebuild(c) for c in children)


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

    if not node.get("contents_page") and not node.get("introduction_pages"):
        return  # no document pages — skip

    node_id = node.get("id", "?")

    # Read raw page content
    toc_page = node.get("contents_page")
    toc_raw = read_page_list([toc_page]) if toc_page else ""

    intro_pages = node.get("introduction_pages") or []
    intro_content = read_page_list(intro_pages) if intro_pages else None

    child_hooks = [c["hook"] for c in children if c.get("hook")]

    bar.set_postfix_str(f"rebuilding: {node_id}", refresh=True)

    if dry_run:
        toc_items = parse_toc_from_page(toc_raw) if toc_raw else []
        old_hook = node.get("hook", "")
        bar.write(f"\n[{node_id}]")
        bar.write(f"  toc_page={toc_page}  intro_pages={intro_pages}  children={len(child_hooks)}")
        bar.write(f"  toc_items parsed: {toc_items}")
        bar.write(f"  CURRENT: {str(old_hook)[:120]!r}")
        bar.update(1)
        return

    # Parse TOC items directly — no LLM involved
    toc_items = parse_toc_from_page(toc_raw) if toc_raw else []

    for attempt in range(2):
        llm_output = ""
        if intro_content or child_hooks:
            try:
                llm_output = client.complete(
                    prompt=rebuild_intro_children_prompt(
                        title=node.get("title", ""),
                        intro_content=intro_content,
                        child_hooks=child_hooks,
                    ),
                    system=rebuild_intro_children_system(),
                    think=True,
                )
            except Exception as exc:
                bar.write(f"\nERROR on {node_id} (attempt {attempt + 1}): {exc}")
                sys.exit(1)

        # Assemble: parsed TOC topics line + LLM summaries
        hook_parts: list[str] = []
        if toc_items:
            hook_parts.append("الموضوعات: " + " | ".join(toc_items))
        if llm_output.strip():
            hook_parts.append(llm_output.strip())

        hook = normalize_hook("\n".join(hook_parts))
        if hook:
            break
        bar.write(f"\nWARN: empty hook for {node_id} (attempt {attempt + 1}) — {'retrying' if attempt == 0 else 'giving up'}")

    node["hook"] = hook if hook else None
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
    total = sum(_count_to_rebuild(s) for s in target_sections)

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
