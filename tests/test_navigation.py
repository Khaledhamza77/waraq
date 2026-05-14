"""
Integration smoke tests for the Stage 5 navigation graph.

Requires a running Ollama server (LLM_BASE_URL / LLM_MODEL set in .env).
Run with: pytest tests/test_navigation.py -v
Skip in environments without Ollama: pytest -m "not integration"
"""
import json
from pathlib import Path

import pytest

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
        "leaf_metadata": {},
        "status": "",
    }
    return graph.invoke(initial, config=config)


# ── Known-answer queries ──────────────────────────────────────────────────────

def test_qualitative_characteristics(graph_config):
    """Query about fundamental qualitative characteristics → section_3_4_3."""
    result = _run(graph_config, "ما هي الخصائص النوعية الأساسية للمعلومات المالية المفيدة؟")
    assert result["status"] == "found"
    assert result["leaf_metadata"]["id"] == "section_3_4_3"
    assert len(result["leaf_content"]) > 0


def test_inventory_measurement(graph_config):
    """Query about inventory measurement → section_5_5."""
    result = _run(graph_config, "كيف يتم قياس المخزون وفق معايير المحاسبة المصرية؟")
    assert result["status"] == "found"
    assert result["leaf_metadata"]["id"] == "section_5_5"


def test_balance_sheet_requirements(graph_config):
    """Query about statement of financial position → section_4_9_3."""
    result = _run(graph_config, "ما هي متطلبات قائمة المركز المالي وفق المعيار الأول؟")
    assert result["status"] == "found"
    assert result["leaf_metadata"]["id"] == "section_4_9_3"


def test_income_recognition(graph_config):
    """Query about income recognition → section_3_5_17."""
    result = _run(graph_config, "متى يتم الاعتراف بالدخل في القوائم المالية؟")
    assert result["status"] == "found"
    assert result["leaf_metadata"]["id"] == "section_3_5_17"


def test_inventory_standard_objective(graph_config):
    """Query about objective of inventory standard → section_5_2."""
    result = _run(graph_config, "ما هو هدف معيار المحاسبة المصري رقم 2 الخاص بالمخزون؟")
    assert result["status"] == "found"
    assert result["leaf_metadata"]["id"] == "section_5_2"


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
