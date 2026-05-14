import json
import logging
import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

log = logging.getLogger(__name__)

_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
_MODEL = os.getenv("LLM_MODEL", "silma-v1")

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _clean_llm_output(raw: str) -> str:
    # Strip complete <think>...</think> blocks
    s = _THINK_RE.sub("", raw)
    # Strip anything before a stray </think> (opening tag was missing)
    if "</think>" in s:
        s = s.split("</think>", 1)[-1]
    return s.strip()


def _clean_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Strip Pydantic-generated metadata that confuses Ollama's grammar engine.

    Ollama resolves $defs inline and rejects unknown top-level keys like 'title'.
    We inline any $defs and drop decorative-only keys before sending.
    """
    schema = dict(schema)
    defs = schema.pop("$defs", {})

    def inline(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref_name = node["$ref"].split("/")[-1]
                return inline(defs.get(ref_name, node))
            result = {}
            for k, v in node.items():
                if k == "title":
                    continue  # strip schema-level title metadata
                if k == "properties":
                    # preserve property names — they are field names, not metadata
                    result[k] = {pk: inline(pv) for pk, pv in v.items()}
                else:
                    result[k] = inline(v)
            return result
        if isinstance(node, list):
            return [inline(i) for i in node]
        return node

    return inline(schema)


class SILMAClient:
    def __init__(self, base_url: str = _BASE_URL, model: str = _MODEL) -> None:
        # Ollama's OpenAI-compatible endpoint; api_key is required by the client but unused
        self._client = OpenAI(base_url=base_url, api_key="ollama")
        self._model = model

    def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body={"num_ctx": 32768},
        )
        raw = response.choices[0].message.content or ""
        return _clean_llm_output(raw)

    def structured(
        self,
        prompt: str,
        system: str = "",
        schema: type[BaseModel] | dict[str, Any] | None = None,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Call the model with structured JSON output.

        Uses Ollama's json_schema response_format when a schema is provided,
        otherwise falls back to json_object mode.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        if schema is None:
            response_format: dict[str, Any] = {"type": "json_object"}
        else:
            raw_schema = (
                schema.model_json_schema() if not isinstance(schema, dict) else dict(schema)
            )
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "result",
                    "schema": _clean_schema(raw_schema),
                },
            }

        for attempt in range(2):
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                response_format=response_format,
                extra_body={"num_ctx": 32768},
            )
            raw = response.choices[0].message.content or "{}"
            content = _clean_llm_output(raw)
            # Strip any garbage bytes before the opening brace
            brace = content.find("{")
            if brace > 0:
                content = content[brace:]
            try:
                return json.loads(content)
            except json.JSONDecodeError as exc:
                log.warning(
                    "structured(): JSON decode error on attempt %d/2: %s | raw: %.200s",
                    attempt + 1, exc, raw,
                )
        log.error("structured(): failed to decode JSON after 2 attempts, returning {}")
        return {}


_default_client: SILMAClient | None = None


def get_client() -> SILMAClient:
    global _default_client
    if _default_client is None:
        _default_client = SILMAClient()
    return _default_client
