import logging
from typing import Any

from pydantic import BaseModel

from waraq.llm.client import get_client
from waraq.navigation.prompts import (
    answer_prompt,
    answer_system,
    greeting_prompt,
    greeting_system,
)

log = logging.getLogger(__name__)

NOT_FOUND_ANSWER = (
    "لم أتمكن من العثور على معلومات تتعلق باستفسارك في وثيقة معايير المحاسبة المصرية. "
    "يُرجى إعادة صياغة سؤالك أو التحقق من أنه يتعلق بالمعايير المحاسبية المصرية."
)


class _Pages(BaseModel):
    start: int
    end: int


class _Citation(BaseModel):
    node_id: str
    title: str
    pages: _Pages


class _AnswerResponse(BaseModel):
    answer: str
    citation: _Citation


def generate_answer(
    query: str,
    leaf_content: str,
    leaf_metadata: list[dict],
) -> dict[str, Any]:
    """Return {"answer": str, "citation": {"node_id", "title", "pages": {"start", "end"}}}."""
    result = get_client().structured(
        prompt=answer_prompt(query, leaf_metadata, leaf_content),
        system=answer_system(),
        schema=_AnswerResponse,
    )
    if not result:
        log.error("generate_answer: structured() returned empty dict")
    return result


def generate_greeting(query: str) -> str:
    """Return a friendly Arabic greeting/introduction response."""
    return get_client().complete(
        prompt=greeting_prompt(query),
        system=greeting_system(),
    )
