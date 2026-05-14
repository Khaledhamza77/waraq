"""
Integration smoke tests for Stage 6 response generation.

Requires a running Ollama server (LLM_BASE_URL / LLM_MODEL set in .env).
Run with: pytest tests/test_responder.py -v --log-cli-level=DEBUG
Skip in environments without Ollama: pytest -m "not integration"
"""
import pytest

from waraq.generation.responder import (
    NOT_FOUND_ANSWER,
    generate_answer,
    generate_greeting,
)

SAMPLE_METADATA = [
    {
        "id": "section_4_standard_1_para_1",
        "title": "الفقرة 1 — الهدف",
        "start_page": 55,
        "end_page": 56,
        "chunk_ids": [],
    }
]

SAMPLE_CONTENT = (
    "الهدف من هذا المعيار هو تحديد السياسة المحاسبية للمخزون. "
    "يُعالج هذا المعيار تحديد التكلفة والاعتراف بها كمصروف، بما في ذلك أي تخفيض "
    "في القيمة الدفترية إلى صافي القيمة القابلة للتحقق. كما يُوضح صيغ التكلفة "
    "المستخدمة لتحديد تكلفة المخزون."
)

SAMPLE_QUERY = "ما هو هدف معيار المحاسبة الخاص بالمخزون؟"


# ── Unit tests (no Ollama needed) ─────────────────────────────────────────────

def test_not_found_answer_is_nonempty_arabic():
    assert isinstance(NOT_FOUND_ANSWER, str)
    assert len(NOT_FOUND_ANSWER) > 20
    assert any("؀" <= ch <= "ۿ" for ch in NOT_FOUND_ANSWER)


# ── Integration tests ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def answer_result():
    """Call generate_answer once and share the result across all answer tests."""
    return generate_answer(SAMPLE_QUERY, SAMPLE_CONTENT, SAMPLE_METADATA)


@pytest.mark.integration
def test_generate_answer_returns_dict(answer_result):
    assert isinstance(answer_result, dict), "generate_answer must return a dict"
    assert answer_result, "generate_answer must not return an empty dict"


@pytest.mark.integration
def test_generate_answer_has_answer_field(answer_result):
    assert "answer" in answer_result, "result must have 'answer' key"
    assert isinstance(answer_result["answer"], str)
    assert len(answer_result["answer"]) > 10, "answer must be a non-trivial string"


@pytest.mark.integration
def test_generate_answer_has_citation_field(answer_result):
    assert "citation" in answer_result, "result must have 'citation' key"
    cit = answer_result["citation"]
    assert isinstance(cit, dict)
    assert "node_id" in cit
    assert "title" in cit
    assert "pages" in cit


@pytest.mark.integration
def test_generate_answer_citation_pages_structure(answer_result):
    assert "citation" in answer_result, "result must have 'citation' key"
    pages = answer_result["citation"].get("pages", {})
    assert isinstance(pages, dict), "pages must be a dict"
    assert "start" in pages and "end" in pages
    assert isinstance(pages["start"], int)
    assert isinstance(pages["end"], int)


@pytest.mark.integration
def test_generate_greeting_returns_nonempty_string():
    result = generate_greeting("مرحباً")
    assert isinstance(result, str)
    assert len(result) > 10, "greeting response must be a non-trivial string"


@pytest.mark.integration
def test_generate_greeting_english_input():
    result = generate_greeting("Hello!")
    assert isinstance(result, str)
    assert len(result) > 10
