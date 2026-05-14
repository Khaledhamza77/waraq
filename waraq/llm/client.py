import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
_MODEL = os.getenv("LLM_MODEL", "silma-v1")


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
        """Call the model with structured JSON output.

        Uses Ollama's json_schema response_format (0.5+) when a schema is
        provided, otherwise falls back to json_object mode.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        if schema is None:
            response_format: dict[str, Any] = {"type": "json_object"}
        else:
            json_schema = (
                schema.model_json_schema() if not isinstance(schema, dict) else schema
            )
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "result",
                    "schema": json_schema,
                    "strict": True,
                },
            }

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            response_format=response_format,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)


_default_client: SILMAClient | None = None


def get_client() -> SILMAClient:
    global _default_client
    if _default_client is None:
        _default_client = SILMAClient()
    return _default_client
