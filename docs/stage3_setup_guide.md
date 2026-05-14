# Stage 3 Setup Guide — SILMA-9B via Ollama

---

## Prerequisites

- Ollama installed on your machine ([ollama.com](https://ollama.com))
- The model already pulled (`ollama list` to confirm)

---

## Step 1 — Find your exact model name

```bash
ollama list
```

Copy the name from the `NAME` column exactly as shown (e.g. `silma-v1`, `qwen3:8b`). Set it in `.env`:

```
LLM_MODEL=<name from ollama list>
```

---

## Step 2 — Start Ollama

Ollama usually runs as a background service after install. Check if it's already up:

```bash
curl http://localhost:11434/api/tags
```

If you get a JSON response with your models listed, it's running. If not, start it:

```bash
ollama serve
```

---

## Step 3 — Install Python dependencies (Windows)

From the project root in PowerShell:

```powershell
uv sync
```

Or if not using uv:

```powershell
pip install -e .
```

---

## Step 4 — Run the smoke test

```powershell
python scripts/test_llm.py
```

Expected output:

```
=== test_free_text ===
الأصول الثابتة هي...
PASSED

=== test_structured_output ===
{
  "intent": "valid",
  "reason": "..."
}
PASSED

All Stage 3 tests passed.
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Connection refused` on port 11434 | Run `ollama serve` |
| `model not found` error | Check `LLM_MODEL` in `.env` matches `ollama list` exactly |
| `JSONDecodeError` from `structured()` | Model may not support `json_schema` format — try setting `LLM_MODEL=qwen3:8b` which has stronger instruction-following |
| Import error for `waraq` | Run `pip install -e .` from project root |

---

## Model choice

Both models available should work. `qwen3:8b` tends to have stronger structured output compliance. SILMA is the target for Arabic regulatory content.

You can switch models at any time by changing `LLM_MODEL` in `.env` — no code changes needed.
