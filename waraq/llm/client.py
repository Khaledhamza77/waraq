import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8001/v1")
_MODEL = os.getenv("VLLM_MODEL", "SILMA-AI/SILMA-9B-Instruct-v1")


class SILMAClient:
    def __init__(self, base_url: str = _BASE_URL, model: str = _MODEL) -> None:
        self._client = OpenAI(base_url=base_url, api_key="not-needed")
        self._model = model

    def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.1,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    def structured(
        self,
        prompt: str,
        system: str = "",
        schema: type[BaseModel] | dict[str, Any] | None = None,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Call SILMA with guided JSON decoding. schema can be a Pydantic model class or a raw JSON schema dict."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        if schema is None:
            json_schema = None
        elif isinstance(schema, dict):
            json_schema = schema
        else:
            json_schema = schema.model_json_schema()

        extra_body: dict[str, Any] = {}
        if json_schema is not None:
            extra_body["guided_json"] = json_schema

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            extra_body=extra_body or None,
        )
        content = response.choices[0].message.content or "{}"

        import json
        return json.loads(content)


_default_client: SILMAClient | None = None


def get_client() -> SILMAClient:
    global _default_client
    if _default_client is None:
        _default_client = SILMAClient()
    return _default_client
