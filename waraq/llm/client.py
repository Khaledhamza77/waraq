import json
import logging
import os
import re
import time
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

from waraq.observability.tracer import safe_generation

load_dotenv()

log = logging.getLogger(__name__)

_LOCAL = os.getenv("LOCAL_INFERENCE", "").strip().lower() in ("1", "true", "t", "yes")
_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
_MODEL = os.getenv("LLM_MODEL", "qwen3:8b")
_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _clean_llm_output(raw: str) -> str:
    # Strip complete <think>...</think> blocks
    s = _THINK_RE.sub("", raw)
    # Strip everything up to and including a stray </think> (opening tag was eaten by the regex)
    if "</think>" in s:
        s = s.split("</think>", 1)[-1]
    # Strip from a stray <think> to end-of-string (model stopped mid-thought, no closing tag)
    if "<think>" in s:
        s = s.split("<think>", 1)[0]
    return s.strip()


def _extract_json(text: str) -> str:
    """Return the first complete JSON object slice from *text*.

    Finds the first '{' and the last '}' and returns the substring between them
    (inclusive). Falls back to the original string if no braces are found, so
    json.loads can produce its own descriptive error.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return text
    return text[start : end + 1]


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
    def __init__(self) -> None:
        if _LOCAL:
            self._client = OpenAI(base_url=_BASE_URL, api_key="ollama")
            self._model = _MODEL
        else:
            if not _OPENAI_API_KEY:
                raise EnvironmentError(
                    "LOCAL_INFERENCE is not set but OPENAI_API_KEY is missing. "
                    "Set OPENAI_API_KEY in .env or switch to LOCAL_INFERENCE=true."
                )
            self._client = OpenAI(api_key=_OPENAI_API_KEY)
            self._model = _OPENAI_MODEL
        self._is_local = _LOCAL

    def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int = 2048,
        num_ctx: int = 32768,
        think: bool = False,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        tokens_key = "max_tokens" if self._is_local else "max_completion_tokens"
        kwargs: dict[str, Any] = dict(
            model=self._model,
            messages=messages,
            temperature=temperature,
            **{tokens_key: max_tokens},
        )
        if self._is_local:
            kwargs["extra_body"] = {"num_ctx": num_ctx, "think": think}

        t0 = time.perf_counter()
        response = self._client.chat.completions.create(**kwargs)
        elapsed = time.perf_counter() - t0

        raw = response.choices[0].message.content or ""
        usage = response.usage
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        log.info(
            "complete() %.2fs | model=%s | tokens=%d+%d",
            elapsed, self._model, prompt_tokens, completion_tokens,
        )
        safe_generation(
            name="complete",
            model=self._model,
            messages=messages,
            completion=raw,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return _clean_llm_output(raw)

    def structured(
        self,
        prompt: str,
        system: str = "",
        schema: type[BaseModel] | dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
        num_ctx: int = 32768,
    ) -> dict[str, Any]:
        """Call the model with structured JSON output.

        Uses Ollama's json_schema response_format when a schema is provided,
        otherwise falls back to json_object mode. OpenAI always uses json_object.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        if self._is_local:
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
        else:
            response_format = {"type": "json_object"}

        tokens_key = "max_tokens" if self._is_local else "max_completion_tokens"
        for attempt in range(2):
            kwargs: dict[str, Any] = dict(
                model=self._model,
                messages=messages,
                temperature=temperature,
                **{tokens_key: max_tokens},
                response_format=response_format,
            )
            if self._is_local:
                kwargs["extra_body"] = {"num_ctx": num_ctx, "think": False}

            t0 = time.perf_counter()
            response = self._client.chat.completions.create(**kwargs)
            elapsed = time.perf_counter() - t0

            raw = response.choices[0].message.content or "{}"
            usage = response.usage
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            log.info(
                "structured() attempt=%d %.2fs | model=%s | tokens=%d+%d",
                attempt + 1, elapsed, self._model, prompt_tokens, completion_tokens,
            )
            safe_generation(
                name="structured",
                model=self._model,
                messages=messages,
                completion=raw,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            content = _extract_json(_clean_llm_output(raw))
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
