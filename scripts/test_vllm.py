"""
Stage 3 smoke test — verifies the vLLM/SILMA endpoint is reachable
and returns valid structured JSON output.

Run after starting the vLLM server:
    python scripts/test_vllm.py
"""
import json
import sys

from pydantic import BaseModel

from waraq.llm.client import SILMAClient


class IntentResult(BaseModel):
    intent: str
    reason: str


def test_free_text(client: SILMAClient) -> None:
    print("=== test_free_text ===")
    result = client.complete(
        prompt="ما هو تعريف الأصول الثابتة في معايير المحاسبة المصرية؟",
        system="أنت مساعد محاسبي متخصص في المعايير المصرية. أجب بإيجاز.",
    )
    print(result)
    assert result and len(result) > 10, "Response is empty or too short"
    print("PASSED\n")


def test_structured_output(client: SILMAClient) -> None:
    print("=== test_structured_output ===")
    result = client.structured(
        prompt="هل السؤال التالي يتعلق باللوائح المحاسبية المصرية؟ السؤال: ما هو مفهوم الاستمرارية؟",
        system="أجب بـ JSON فقط.",
        schema=IntentResult,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert "intent" in result, "Missing 'intent' key in response"
    assert "reason" in result, "Missing 'reason' key in response"
    print("PASSED\n")


def main() -> None:
    client = SILMAClient()
    try:
        test_free_text(client)
        test_structured_output(client)
        print("All Stage 3 tests passed.")
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
