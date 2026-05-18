import logging
from typing import Any

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


def _build_citations(leaf_metadata: list[dict]) -> list[dict[str, Any]]:
    return [
        {
            "node_id": m["id"],
            "title": m["title"],
            "pages": {"start": m["start_page"], "end": m["end_page"]},
        }
        for m in leaf_metadata
    ]


def generate_answer(
    query: str,
    leaf_content: str,
    leaf_metadata: list[dict],
) -> dict[str, Any]:
    """Return {"answer": str, "citations": [{"node_id", "title", "pages": {"start", "end"}}, ...]}."""
    answer = get_client().complete(
        prompt=answer_prompt(query, leaf_metadata, leaf_content),
        system=answer_system(),
        max_tokens=4096,
    )
    if not answer:
        log.error("generate_answer: complete() returned empty string")
        return {}
    return {
        "answer": answer,
        "citations": _build_citations(leaf_metadata),
    }


def generate_greeting(query: str) -> str:
    """Return a friendly Arabic greeting/introduction response."""
    return get_client().complete(
        prompt=greeting_prompt(query),
        system=greeting_system(),
    )
