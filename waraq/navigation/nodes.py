from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Literal, Optional

from langchain_core.runnables import RunnableConfig  # used by navigate_level
from pydantic import BaseModel

log = logging.getLogger(__name__)

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

_ARABIC_RE = re.compile(r"[؀-ۿ]")
_MAX_DEPTH = 10


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class IntentResult(BaseModel):
    intent: Literal["valid", "invalid", "greeting"]
    reason: str


class NavigationSelection(BaseModel):
    selected_id: Optional[str]
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
        if page_file.exists():
            parts.append(page_file.read_text(encoding="utf-8"))
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
        prompt=check_intent_prompt(state["query"]),
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

    valid_ids = {c["id"] for c in candidates}

    result = get_client().structured(
        prompt=navigate_level_prompt(state["query"], candidates),
        system=navigate_level_system(),
        schema=NavigationSelection,
    )
    selected_id: str | None = result.get("selected_id")
    reasoning: str = result.get("reasoning", "")

    log.debug("  llm selected: %s", selected_id)
    log.debug("  reasoning   : %s", reasoning)

    if not selected_id:
        log.debug("  → selected_id is null/empty, not_found")
        return {"status": "not_found"}

    if selected_id not in valid_ids:
        log.debug("  → '%s' not in valid_ids %s, not_found", selected_id, valid_ids)
        return {"status": "not_found"}

    node = _find_node(index["sections"], selected_id)
    if node is None:
        log.debug("  → node '%s' not found in index, not_found", selected_id)
        return {"status": "not_found"}

    new_path = navigation_path + [selected_id]
    log.debug("  node type   : %s", "leaf" if _is_leaf(node) else "non-leaf")

    if _is_leaf(node):
        content = _extract_leaf_content(node, markdown_dir)
        log.debug("  → found leaf '%s', content length: %d chars", selected_id, len(content))
        return {
            "navigation_path": new_path,
            "leaf_content": content,
            "leaf_metadata": {
                "id": node["id"],
                "title": node["title"],
                "start_page": node["start_page"],
                "end_page": node["end_page"],
                "chunk_ids": node.get("chunk_ids", []),
            },
            "status": "found",
        }

    log.debug("  → descending into '%s'", selected_id)
    return {"navigation_path": new_path, "status": "navigating"}
