from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from waraq.llm.client import get_client
from waraq.navigation.prompts import (
    check_intent_prompt,
    check_intent_system,
    navigate_level_prompt,
    navigate_level_system,
    normalize_query_prompt,
    normalize_query_system,
)
from waraq.navigation.state import NavigationState

log = logging.getLogger(__name__)

_ARABIC_RE = re.compile(r"[؀-ۿ]")
_MAX_DEPTH = 10


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class IntentResult(BaseModel):
    intent: Literal["valid", "invalid", "greeting"]
    reason: str


class NavigationSelection(BaseModel):
    selected_ids: list[str]
    reasoning: str


# ── Index helpers ─────────────────────────────────────────────────────────────

def _find_node(sections: list[dict], node_id: str) -> dict | None:
    for node in sections:
        if node.get("id") == node_id:
            return node
        if "children" in node:
            result = _find_node(node["children"], node_id)
            if result is not None:
                return result
    return None


def _is_leaf(node: dict) -> bool:
    return "start_page" in node and "children" not in node


def _get_candidates(index: dict, navigation_path: list[str]) -> list[dict]:
    if not navigation_path:
        return index["sections"]
    parent = _find_node(index["sections"], navigation_path[-1])
    if parent is None:
        return []
    return parent.get("children", [])


def _extract_leaf_content(node: dict, markdown_dir: Path) -> str:
    parts: list[str] = []
    for page_num in range(node["start_page"], node["end_page"] + 1):
        page_file = markdown_dir / f"page_{page_num}.md"
        if not page_file.exists():
            log.debug("  page file missing: %s", page_file)
            continue
        text = page_file.read_text(encoding="utf-8").strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


# ── Graph nodes ───────────────────────────────────────────────────────────────

def normalize_query(state: NavigationState) -> dict[str, Any]:
    query = state["original_query"]
    language = "ar" if _ARABIC_RE.search(query) else "en"

    normalized = get_client().complete(
        prompt=normalize_query_prompt(query, language),
        system=normalize_query_system(),
    )
    return {"query": normalized.strip(), "language": language}


def check_intent(state: NavigationState) -> dict[str, Any]:
    result = get_client().structured(
        prompt=check_intent_prompt(state["original_query"]),
        system=check_intent_system(),
        schema=IntentResult,
    )
    intent = result.get("intent", "invalid")
    if intent == "valid":
        status = "navigating"
    elif intent == "greeting":
        status = "greeting"
    else:  # "invalid" or any unexpected value
        status = "rejected"
    return {"intent": intent, "status": status}


def navigate_level(state: NavigationState, config: RunnableConfig) -> dict[str, Any]:
    cfg = config.get("configurable", {})
    index: dict = cfg["index"]
    markdown_dir: Path = cfg["markdown_dir"]

    navigation_path: list[str] = state.get("navigation_path") or []

    log.debug("── navigate_level ──────────────────────────")
    log.debug("  path so far : %s", navigation_path or "[root]")

    if len(navigation_path) >= _MAX_DEPTH:
        log.debug("  → depth limit reached, not_found")
        return {"status": "not_found"}

    candidates = _get_candidates(index, navigation_path)
    if not candidates:
        log.debug("  → no candidates at this level, not_found")
        return {"status": "not_found"}

    log.debug("  candidates  : %s", [f"{c['id']} ({c['title']})" for c in candidates])

    candidate_map: dict[str, dict] = {}
    for c in candidates:
        candidate_map[c["id"]] = c
        short = c["id"].removeprefix("section_")
        if short != c["id"]:
            candidate_map[short] = c
    all_leaves = all(_is_leaf(c) for c in candidates)

    result = get_client().structured(
        prompt=navigate_level_prompt(state["query"], candidates, multi_select=all_leaves),
        system=navigate_level_system(),
        schema=NavigationSelection,
    )
    selected_ids: list[str] = result.get("selected_ids") or []
    reasoning: str = result.get("reasoning", "")

    log.debug("  llm selected: %s", selected_ids)
    log.debug("  reasoning   : %s", reasoning)

    if not selected_ids:
        log.debug("  → selected_ids is empty, not_found")
        return {"status": "not_found"}

    # Filter to valid candidates, preserving order; always use the canonical node ID
    resolved: list[tuple[str, dict]] = [
        (candidate_map[sid]["id"], candidate_map[sid])
        for sid in selected_ids if sid in candidate_map
    ]
    if not resolved:
        log.debug("  → none of %s are valid candidates, not_found", selected_ids)
        return {"status": "not_found"}

    leaf_nodes = [(sid, n) for sid, n in resolved if _is_leaf(n)]
    non_leaf_nodes = [(sid, n) for sid, n in resolved if not _is_leaf(n)]

    log.debug("  node types  : %d leaf(s), %d non-leaf(s)", len(leaf_nodes), len(non_leaf_nodes))

    # Intermediate navigation: descend into the first non-leaf
    if non_leaf_nodes:
        sid, node = non_leaf_nodes[0]
        if len(non_leaf_nodes) > 1:
            ignored = [s for s, _ in non_leaf_nodes[1:]]
            log.warning("  LLM returned %d non-leaf selections; ignoring %s", len(non_leaf_nodes), ignored)
        new_path = navigation_path + [sid]
        log.debug("  → descending into '%s' (%s)", sid, node["title"])
        return {"navigation_path": new_path, "status": "navigating"}

    # Leaf level: collect content from all selected leaves
    all_content: list[str] = []
    all_metadata: list[dict] = []
    for sid, node in leaf_nodes:
        content = _extract_leaf_content(node, markdown_dir)
        if content:
            all_content.append(content)
        all_metadata.append({
            "id": node["id"],
            "title": node["title"],
            "start_page": node["start_page"],
            "end_page": node["end_page"],
            "chunk_ids": node.get("chunk_ids", []),
        })

    if not all_content:
        log.warning("  → no readable page files for any selected leaf, not_found")
        return {"status": "not_found"}

    new_path = navigation_path + [sid for sid, _ in leaf_nodes]
    log.debug("  → found %d leaf(s): %s", len(leaf_nodes), [sid for sid, _ in leaf_nodes])
    return {
        "navigation_path": new_path,
        "leaf_content": "\n\n---\n\n".join(all_content),
        "leaf_metadata": all_metadata,
        "status": "found",
    }
