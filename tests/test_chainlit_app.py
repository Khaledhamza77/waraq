"""
Tests for chainlit_app.py.

Unit tests: no external services required (no Ollama, no Langfuse).
Integration tests: require a running Ollama server.
    pytest tests/test_chainlit_app.py -v --log-cli-level=DEBUG
    pytest tests/test_chainlit_app.py -v -m "not integration"   # unit only

Strategy: mock the entire `chainlit` package in sys.modules before the app is
imported so @cl.on_chat_start and @cl.on_message become transparent decorators
and the handlers can be called as plain async functions.
"""

import asyncio
import sys
from unittest.mock import MagicMock, patch

import pytest


# ── Mock Chainlit runtime ─────────────────────────────────────────────────────
# Must happen before `import chainlit_app`.

_session: dict = {}


class _FakeMessage:
    """Minimal stand-in for cl.Message. Tracks all instances created."""

    _instances: list["_FakeMessage"] = []

    def __init__(self, content: str = ""):
        self.content = content
        _FakeMessage._instances.append(self)

    async def send(self) -> None:
        pass

    async def update(self) -> None:
        pass

    @classmethod
    def clear(cls) -> None:
        cls._instances.clear()


_cl = MagicMock()
_cl.on_chat_start = lambda f: f   # pass-through decorator
_cl.on_message = lambda f: f      # pass-through decorator
_cl.Message = _FakeMessage
_cl.user_session.get = lambda key: _session.get(key)
_cl.user_session.set = lambda key, val: _session.update({key: val})

sys.modules["chainlit"] = _cl

import app.chainlit_app as chainlit_app  # noqa: E402  (must come after sys.modules patch)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset():
    """Fresh session and message list before each test."""
    _session.clear()
    _FakeMessage.clear()
    yield
    _session.clear()
    _FakeMessage.clear()


# ── Pipeline helper ───────────────────────────────────────────────────────────

async def _invoke(text: str) -> _FakeMessage:
    """Run on_chat_start (if not already done) + on_message for one turn.

    Returns the cl.Message instance that on_message created — its `.content`
    holds the final text sent to the user after all updates.
    """
    if not _session.get("graph"):
        await chainlit_app.on_chat_start()
    _FakeMessage.clear()  # only track messages from this turn
    await chainlit_app.on_message(MagicMock(content=text))
    assert _FakeMessage._instances, "on_message must create at least one cl.Message"
    return _FakeMessage._instances[-1]


# ── Unit tests (no Ollama) ────────────────────────────────────────────────────

def test_on_chat_start_populates_session():
    asyncio.run(chainlit_app.on_chat_start())
    graph = _session.get("graph")
    config = _session.get("config")

    assert graph is not None, "graph must be stored in session"
    assert config is not None, "config must be stored in session"

    cfg = config.get("configurable", {})
    assert "index" in cfg, "config must carry the index"
    assert "markdown_dir" in cfg, "config must carry markdown_dir"
    assert isinstance(cfg["index"], dict)
    assert cfg["index"].get("sections"), "index must have a non-empty sections list"


def test_format_response_no_citations():
    assert chainlit_app._format_response("إجابة", []) == "إجابة"


def test_format_response_single_page_citation():
    result = chainlit_app._format_response("إجابة", [
        {"title": "القسم أ", "pages": {"start": 10, "end": 10}},
    ])
    assert "القسم أ" in result
    assert "صفحة 10" in result
    assert "صفحات" not in result
    assert "المصادر" in result


def test_format_response_multi_page_citation():
    result = chainlit_app._format_response("إجابة", [
        {"title": "التعريفات", "pages": {"start": 60, "end": 62}},
    ])
    assert "التعريفات" in result
    assert "صفحات 60" in result
    assert "62" in result


def test_format_response_multiple_citations():
    result = chainlit_app._format_response("إجابة", [
        {"title": "التعريفات", "pages": {"start": 60, "end": 62}},
        {"title": "الأهداف", "pages": {"start": 55, "end": 55}},
    ])
    assert "التعريفات" in result
    assert "الأهداف" in result
    assert result.count("- ") >= 2


def test_span_output_excludes_leaf_content():
    updates = {
        "leaf_content": "x" * 10_000,
        "leaf_metadata": [{"id": "section_3_4", "title": "الخصائص"}],
        "status": "found",
        "navigation_path": ["section_3", "section_3_4"],
    }
    out = chainlit_app._span_output_from_updates(updates)
    assert "leaf_content" not in out
    assert out["status"] == "found"
    assert out["leaf_metadata"] == [{"id": "section_3_4", "title": "الخصائص"}]
    assert out["navigation_path"] == ["section_3", "section_3_4"]


def test_node_status_reflects_merged_node():
    """_NODE_STATUS must have the merged node key and not the two removed ones."""
    assert "classify_and_normalize" in chainlit_app._NODE_STATUS
    assert "check_intent" not in chainlit_app._NODE_STATUS
    assert "normalize_query" not in chainlit_app._NODE_STATUS


def test_graph_stream_failure_shows_arabic_error():
    """graph.astream raising must produce a user-facing Arabic error, not a crash."""

    async def _bad_astream(*_args, **_kwargs):
        raise RuntimeError("simulated Ollama failure")
        yield  # pragma: no cover  — makes this an async generator

    async def _test():
        await chainlit_app.on_chat_start()
        bad_graph = MagicMock()
        bad_graph.astream = _bad_astream
        _session["graph"] = bad_graph
        _FakeMessage.clear()
        await chainlit_app.on_message(MagicMock(content="سؤال"))
        return _FakeMessage._instances[-1]

    ai_msg = asyncio.run(_test())
    assert "خطأ" in ai_msg.content, "error path must surface Arabic خطأ to the user"


# ── Integration tests (require Ollama) ────────────────────────────────────────

@pytest.mark.integration
def test_on_message_greeting():
    ai_msg = asyncio.run(_invoke("مرحباً، كيف يمكنك مساعدتي؟"))
    assert len(ai_msg.content) > 20, "greeting must be non-trivial"
    assert "المصادر" not in ai_msg.content, "greeting must not include citations"


@pytest.mark.integration
def test_on_message_valid_accounting_query():
    """Known-answer query must return a substantive answer with a sources section."""
    ai_msg = asyncio.run(_invoke("ما هي الخصائص النوعية الأساسية للمعلومات المالية المفيدة؟"))
    assert len(ai_msg.content) > 50, "answer must be substantive"
    assert "المصادر" in ai_msg.content, "answer must include a sources section"


@pytest.mark.integration
def test_on_message_rejected_query():
    """Off-topic query must be rejected without citations."""
    ai_msg = asyncio.run(_invoke("كيف أطبخ المكرونة؟"))
    assert isinstance(ai_msg.content, str)
    assert len(ai_msg.content) > 10
    assert "المصادر" not in ai_msg.content


@pytest.mark.integration
def test_langfuse_disabled_does_not_affect_response():
    """Response must be identical quality whether Langfuse is on or off."""
    with patch.object(chainlit_app, "get_langfuse", return_value=None):
        ai_msg = asyncio.run(_invoke("ما هو هدف معيار المحاسبة المصري رقم 2 الخاص بالمخزون؟"))
    assert len(ai_msg.content) > 20
    assert "المصادر" in ai_msg.content
