"""
End-to-end integration: Navigation → Response generation.

For each known-answer query, runs the full pipeline:
  normalize → intent check → navigate → generate_answer / generate_greeting
and asserts both navigation correctness and response quality (answer text +
citation shape).

Run with: pytest tests/test_nav_responder.py -v --log-cli-level=DEBUG
Skip without Ollama: pytest -m "not integration"
"""
import json
import logging
from pathlib import Path

import pytest

from waraq.generation.responder import NOT_FOUND_ANSWER, generate_answer, generate_greeting
from waraq.navigation.graph import build_graph
from waraq.navigation.state import NavigationState

log = logging.getLogger(__name__)

INDEX_PATH = Path(__file__).parent.parent / "data" / "index.json"
MARKDOWN_DIR = Path(__file__).parent.parent / "data" / "parsed" / "markdown" / "pages"

pytestmark = pytest.mark.integration


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def graph_config():
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    graph = build_graph()
    config = {"configurable": {"index": index, "markdown_dir": MARKDOWN_DIR}}
    return graph, config


# ── Pipeline helper ───────────────────────────────────────────────────────────

def _found_in(nav: NavigationState, section_prefix: str) -> bool:
    return any(
        m["id"].startswith(section_prefix)
        for m in nav.get("leaf_metadata", [])
    )


def _run_full(graph_config, query: str) -> dict:
    """Run navigate → respond and return {"nav": NavigationState, "response": dict}."""
    graph, config = graph_config

    log.debug("")
    log.debug("╔══════════════════════════════════════════════════════════╗")
    log.debug("  QUERY: %s", query)
    log.debug("╚══════════════════════════════════════════════════════════╝")

    initial: NavigationState = {
        "original_query": query,
        "query": "",
        "language": "",
        "intent": "",
        "navigation_path": [],
        "leaf_content": "",
        "leaf_metadata": [],
        "status": "",
    }

    nav = graph.invoke(initial, config=config)

    log.debug("── Navigation result ──────────────────────────────────────")
    log.debug("  status          : %s", nav["status"])
    log.debug("  intent          : %s", nav.get("intent"))
    log.debug("  language        : %s", nav.get("language"))
    log.debug("  normalized query: %s", nav.get("query"))
    log.debug("  navigation path : %s", nav.get("navigation_path"))
    for m in nav.get("leaf_metadata", []):
        log.debug(
            "  leaf            : [%s] %s  (pp. %s–%s)",
            m["id"], m["title"], m["start_page"], m["end_page"],
        )
    log.debug("  content length  : %d chars", len(nav.get("leaf_content", "")))

    status = nav["status"]

    if status == "found":
        log.debug("── Sending to responder ───────────────────────────────────")
        log.debug("  query (normalized): %s", nav["query"])
        log.debug("  sources passed    : %d leaf(s)", len(nav["leaf_metadata"]))

        response = generate_answer(
            query=nav["query"],
            leaf_content=nav["leaf_content"],
            leaf_metadata=nav["leaf_metadata"],
        )

        log.debug("── Responder output ───────────────────────────────────────")
        log.debug("  answer (first 300 chars):")
        log.debug("    %s", str(response.get("answer", ""))[:300])
        for cit in response.get("citations") or []:
            log.debug(
                "  citation : [%s] %s  (pp. %s–%s)",
                cit.get("node_id"), cit.get("title"),
                cit.get("pages", {}).get("start"), cit.get("pages", {}).get("end"),
            )

    elif status == "greeting":
        log.debug("── Greeting → responder ───────────────────────────────────")
        greeting_text = generate_greeting(nav["original_query"])
        response = {"answer": greeting_text, "citations": []}
        log.debug("  greeting (first 300 chars):")
        log.debug("    %s", greeting_text[:300])

    elif status == "not_found":
        response = {"answer": NOT_FOUND_ANSWER, "citations": []}
        log.debug("── not_found: canned response returned, no LLM call")

    else:  # rejected
        response = {"answer": "", "citations": []}
        log.debug("── rejected: pipeline stopped at intent check, no response")

    return {"nav": nav, "response": response}


def _assert_answer_quality(result: dict) -> None:
    """Assert response shape and basic quality for a 'found' result."""
    response = result["response"]

    assert isinstance(response.get("answer"), str), "answer must be a string"
    assert len(response["answer"]) > 20, "answer must be non-trivial"

    cits = response.get("citations")
    assert isinstance(cits, list), "citations must be a list"
    assert len(cits) >= 1, "citations must have at least one entry"

    for cit in cits:
        assert cit.get("node_id"), "citation.node_id must be non-empty"
        assert cit.get("title"), "citation.title must be non-empty"
        pages = cit.get("pages", {})
        assert isinstance(pages, dict), "citation.pages must be a dict"
        assert isinstance(pages.get("start"), int), "pages.start must be an int"
        assert isinstance(pages.get("end"), int), "pages.end must be an int"
        assert pages["start"] >= 1, "pages.start must be a valid page number"
        assert pages["end"] >= pages["start"], "pages.end must be >= pages.start"


# ── Known-answer end-to-end tests ─────────────────────────────────────────────

def test_qualitative_characteristics_e2e(graph_config):
    """Qualitative characteristics → section_3_4, with Arabic answer + citation."""
    result = _run_full(graph_config, "ما هي الخصائص النوعية الأساسية للمعلومات المالية المفيدة؟")
    assert result["nav"]["status"] == "found"
    assert _found_in(result["nav"], "section_3_4")
    _assert_answer_quality(result)


def test_inventory_measurement_e2e(graph_config):
    """Inventory measurement → section_5, with Arabic answer + citation."""
    result = _run_full(graph_config, "كيف يتم قياس المخزون وفق معايير المحاسبة المصرية؟")
    assert result["nav"]["status"] == "found"
    assert _found_in(result["nav"], "section_5")
    _assert_answer_quality(result)


def test_balance_sheet_requirements_e2e(graph_config):
    """Statement of financial position → section_4, with Arabic answer + citation."""
    result = _run_full(graph_config, "ما هي متطلبات قائمة المركز المالي وفق المعيار الأول؟")
    assert result["nav"]["status"] == "found"
    assert _found_in(result["nav"], "section_4")
    _assert_answer_quality(result)


def test_income_recognition_e2e(graph_config):
    """Income recognition → section_3_5 or section_4, with Arabic answer + citation."""
    result = _run_full(graph_config, "متى يتم الاعتراف بالدخل في القوائم المالية؟")
    assert result["nav"]["status"] == "found"
    assert _found_in(result["nav"], "section_3_5") or _found_in(result["nav"], "section_4")
    _assert_answer_quality(result)


def test_inventory_standard_objective_e2e(graph_config):
    """Inventory standard objective → section_5, with Arabic answer + citation."""
    result = _run_full(graph_config, "ما هو هدف معيار المحاسبة المصري رقم 2 الخاص بالمخزون؟")
    assert result["nav"]["status"] == "found"
    assert _found_in(result["nav"], "section_5")
    _assert_answer_quality(result)


def test_greeting_e2e(graph_config):
    """Greeting is handled by responder with a friendly Arabic introduction."""
    result = _run_full(graph_config, "مرحبا، كيف يمكنك مساعدتي؟")
    assert result["nav"]["status"] == "greeting"
    assert isinstance(result["response"]["answer"], str)
    assert len(result["response"]["answer"]) > 10
