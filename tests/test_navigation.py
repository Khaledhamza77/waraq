"""
Integration smoke tests for the Stage 5 navigation graph.

Requires a running Ollama server (LLM_BASE_URL / LLM_MODEL set in .env).
Run with: pytest tests/test_navigation.py -v --log-cli-level=DEBUG
Skip in environments without Ollama: pytest -m "not integration"
"""
import json
import logging
import time
from pathlib import Path

import pytest

log = logging.getLogger(__name__)

from waraq.navigation.graph import build_graph
from waraq.navigation.state import NavigationState

INDEX_PATH = Path(__file__).parent.parent / "data" / "index.json"
MARKDOWN_DIR = Path(__file__).parent.parent / "data" / "parsed" / "markdown" / "pages"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def graph_config():
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    graph = build_graph()
    config = {"configurable": {"index": index, "markdown_dir": MARKDOWN_DIR}}
    return graph, config


def _run(graph_config, query: str) -> NavigationState:
    graph, config = graph_config
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
    t0 = time.perf_counter()
    result = graph.invoke(initial, config=config)
    elapsed = time.perf_counter() - t0
    log.info("⏱  navigation=%.2fs | status=%s", elapsed, result.get("status"))
    return result


def _found_in(result: NavigationState, section_prefix: str) -> bool:
    """True if any returned leaf falls within the expected section subtree."""
    return any(
        m["id"].startswith(section_prefix)
        for m in result.get("leaf_metadata", [])
    )


# ── Known-answer queries ──────────────────────────────────────────────────────

def test_qualitative_characteristics(graph_config):
    """Qualitative characteristics → anywhere in section_3_4."""
    result = _run(graph_config, "ما هي الخصائص النوعية الأساسية للمعلومات المالية المفيدة؟")
    assert result["status"] == "found"
    assert result["leaf_metadata"]
    assert len(result["leaf_content"]) > 0
    assert _found_in(result, "section_3_4")


def test_inventory_measurement(graph_config):
    """Inventory measurement → anywhere in section_5."""
    result = _run(graph_config, "كيف يتم قياس المخزون وفق معايير المحاسبة المصرية؟")
    assert result["status"] == "found"
    assert result["leaf_metadata"]
    assert _found_in(result, "section_5")


def test_balance_sheet_requirements(graph_config):
    """Statement of financial position requirements → anywhere in section_4."""
    result = _run(graph_config, "ما هي متطلبات قائمة المركز المالي وفق المعيار الأول؟")
    assert result["status"] == "found"
    assert result["leaf_metadata"]
    assert _found_in(result, "section_4")


def test_income_recognition(graph_config):
    """Income recognition → section_3_5 or section_4."""
    result = _run(graph_config, "متى يتم الاعتراف بالدخل في القوائم المالية؟")
    assert result["status"] == "found"
    assert result["leaf_metadata"]
    assert _found_in(result, "section_3_5") or _found_in(result, "section_4")


def test_inventory_standard_objective(graph_config):
    """Objective of inventory standard → anywhere in section_5."""
    result = _run(graph_config, "ما هو هدف معيار المحاسبة المصري رقم 2 الخاص بالمخزون؟")
    assert result["status"] == "found"
    assert result["leaf_metadata"]
    assert _found_in(result, "section_5")


# ── classify_and_normalize contract ──────────────────────────────────────────

def test_classify_and_normalize_populates_all_state_fields(graph_config):
    """classify_and_normalize must set query, language, intent, and status in one pass."""
    result = _run(graph_config, "ما هي الخصائص النوعية الأساسية للمعلومات المالية المفيدة؟")
    assert result.get("intent") == "valid", "intent must be 'valid' for an accounting query"
    assert result.get("language") in ("ar", "en"), "language must be detected"
    assert result.get("query"), "normalized query must be non-empty"
    assert result.get("status") != "", "status must be set"


# ── Rejection ─────────────────────────────────────────────────────────────────

def test_out_of_domain_rejected(graph_config):
    """Off-topic query should be rejected."""
    result = _run(graph_config, "ما هو سعر البترول اليوم في مصر؟")
    assert result["status"] == "rejected"


# ── Greeting ──────────────────────────────────────────────────────────────────

def test_greeting_handled(graph_config):
    """Greeting should be classified as greeting, not rejected or navigated."""
    result = _run(graph_config, "مرحبا، كيف يمكنك مساعدتي؟")
    assert result["status"] == "greeting"
