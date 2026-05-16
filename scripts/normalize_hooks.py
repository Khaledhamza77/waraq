"""
Script 1 — Programmatic hook normalization.

Walks every node in data/index.json and applies purely textual fixes:
  - Strip leading garbage characters (non-Arabic, non-letter bytes before real content)
  - Strip **bold** markdown markers
  - Fix the known template artifact  مصد={...} → المصداقية
  - Strip common Arabic preamble phrases (same list as run_summary_gen.py)

No LLM is called. Saves atomically after each changed node.
Idempotent: safe to re-run.

Usage:
    python scripts/normalize_hooks.py [--dry-run]
"""
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
INDEX_PATH = ROOT / "data" / "index.json"

# ── Normalization rules ───────────────────────────────────────────────────────

# Strip **word** or __word__ bold markers
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*|__(.+?)__", re.DOTALL)

# Template artifact: مصد={anything} → المصداقية
_TEMPLATE_RE = re.compile(r"مصد=\{[^}]*\}", re.UNICODE)

# Characters considered "valid Arabic content starters": Arabic letters/marks, digits, quotes, parens
_ARABIC_START_RE = re.compile(r'[؀-ۿ\d("«]')

# Common Arabic preamble phrases to strip from the start
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

# Leaked think-tag artifacts at the very start
_THINK_LEAK_RE = re.compile(r"^(\[\]>?\s*\n?</think>\s*|</?think>\s*)+", re.UNICODE)

# Tokenizer padding tokens like [PAD151871] at the very start
_BRACKET_ARTIFACT_RE = re.compile(r"^\[[A-Za-z0-9]+\]\s*", re.UNICODE)


def _strip_leading_garbage(text: str) -> str:
    """Remove non-Arabic/non-meaningful characters that precede actual content."""
    # Strip leaked think tags first
    text = _THINK_LEAK_RE.sub("", text)
    # Strip tokenizer padding tokens like [PAD151871]
    text = _BRACKET_ARTIFACT_RE.sub("", text)
    # Find the first position that looks like a real content character
    for i, ch in enumerate(text):
        if _ARABIC_START_RE.match(ch):
            return text[i:]
    return text


def _strip_preamble(text: str) -> str:
    for prefix in _PREAMBLE_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):].lstrip(" :\n،,.")
            break
    return text


def normalize_hook(hook: str) -> str:
    text = hook.strip()
    # Bold stripping must run before garbage stripping so paired **Title** tokens
    # are removed as a unit rather than having the opening ** eaten first.
    text = _BOLD_RE.sub(lambda m: m.group(1) or m.group(2), text)
    text = _strip_leading_garbage(text)
    text = _strip_preamble(text)
    text = _TEMPLATE_RE.sub("المصداقية", text)
    return text.strip()


# ── Index traversal ───────────────────────────────────────────────────────────

def walk_nodes(node: dict) -> Iterator[dict]:
    yield node
    for child in node.get("children", []):
        yield from walk_nodes(child)


def load_index() -> dict:
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def save_index(data: dict) -> None:
    tmp = INDEX_PATH.with_name(INDEX_PATH.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
    tmp.replace(INDEX_PATH)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    dry_run = "--dry-run" in sys.argv

    if not INDEX_PATH.exists():
        print(f"ERROR: {INDEX_PATH} not found")
        sys.exit(1)

    index_data = load_index()
    sections = index_data.get("sections", [])

    changed = 0
    skipped = 0

    for section in sections:
        for node in walk_nodes(section):
            hook = node.get("hook")
            if hook is None:
                skipped += 1
                continue

            normalized = normalize_hook(hook)
            if normalized == hook:
                continue

            node_id = node.get("id", "?")
            print(f"\n[{node_id}]")
            print(f"  BEFORE: {hook[:120]!r}")
            print(f"  AFTER : {normalized[:120]!r}")

            if not dry_run:
                node["hook"] = normalized
                save_index(index_data)

            changed += 1

    mode = " (DRY RUN)" if dry_run else ""
    print(f"\nDone{mode}. Changed: {changed}  |  Skipped (no hook): {skipped}")


if __name__ == "__main__":
    main()
