# waraq — Progress Log

---

## Stage 1 — Ingestion Pipeline ✅

**Status:** Complete  
**Output:** `data/parsed/output.json`, `data/parsed/markdown/`

---

### What was built

#### Project scaffold
- `pyproject.toml` with all project dependencies (`landingai-ade`, `openai`, `fastapi`, `langgraph`, `langfuse`, `pymupdf`, `pydantic`, `python-dotenv`, `uvicorn`)
- `.env.example` with all required environment variables
- Full `waraq/` package structure with `__init__.py` files in every subpackage (`ingestion`, `index`, `navigation`, `generation`, `llm`, `observability`, `api`)
- `data/raw/`, `data/parsed/` directories

#### `scripts/run_ingestion.py`
Parses the regulatory PDF using LandingAI ADE and saves structured output to `data/parsed/output.json`.

Key behaviours:
- **Idempotent** — exits early if `output.json` already exists
- **100-page chunking** — LandingAI free tier caps at 100 pages per request; the PDF is split into chunks using `pymupdf`, each chunk parsed separately
- **Per-chunk checkpoints** — each part saved to `data/parsed/part_N.json` immediately after a successful API response; a failed or interrupted run resumes from the last saved checkpoint without re-burning credits
- **Atomic writes** — all file writes go to a `.tmp` sibling first, then renamed into place; a partial write can never be mistaken for a valid checkpoint
- **Corrupt checkpoint detection** — `JSONDecodeError` on load exits with a clear message rather than silently re-parsing
- **Page number normalisation** — LandingAI numbers pages relative to each chunk (0 or 1-indexed); the script auto-detects the base from `min(grounding.page)` per chunk and shifts all pages to 1-indexed full-document positions
- **Page numbers live at `chunk.grounding.page`**, not `chunk.page`

#### `scripts/remerge_parts.py`
One-time utility to remerge existing `part_N.json` checkpoints into `output.json` with correct full-document page numbers, without re-calling the API.

#### `scripts/build_markdown.py`
Converts `output.json` into human-readable markdown files for inspection.

---

### Discovered facts about the LandingAI ADE response structure

- Page number is at `chunk["grounding"]["page"]`, **not** `chunk["page"]`
- Bounding box is at `chunk["grounding"]["box"]` with keys `top`, `bottom`, `left`, `right` (normalised 0–1, top-down coordinates)
- `chunk["markdown"]` holds the text/figure content
- `chunk["type"]` holds the chunk type (`text`, `figure`, `attestation`, etc.)
- LandingAI uses **0-indexed** page numbers within each parsed chunk

---

### Definition of done — Stage 1

- [x] `data/parsed/output.json` exists with all pages parsed and correct full-document page numbers
- [x] `data/parsed/markdown/document.md` exists for human inspection
- [x] `data/parsed/markdown/pages/page_N.md` exists for each page
- [x] Spot-check: verify page numbers in `output.json` are 1-indexed and continuous across chunk boundaries

---

## Stage 2 — Document Mapping ✅

**Status:** Complete (human-authored)  
**Output:** `data/index.json`

---

### What was built

`data/index.json` — master document index covering all 208 pages of "معايير المحاسبة المصرية". Structure includes:
- **section_1**: الصفحات التمهيدية (pp. 1–7)
- **section_2**: المقدمة — with 3 leaf children
- **section_3**: إطار إعداد وعرض القوائم المالية — deeply nested across 5 sub-parts and ~40 leaf nodes (pp. 14–54)
- **section_4** through **section_9**: Individual Egyptian Accounting Standards (معايير 1, 2, 4, 5, 7, 10)

All `hook` fields are `null` — to be filled by Stage 4 (summary generation).

---

### Definition of done — Stage 2

- [x] `data/index.json` exists with full hierarchical structure
- [x] All leaf nodes have `start_page` / `end_page` fields
- [x] All `hook` fields are `null` (ready for Stage 4)
- [x] Structure reflects actual document organisation

---

## Stage 3 — SILMA-9B via Ollama ✅

**Status:** Complete (code implemented; run `scripts/test_llm.py` once Ollama is serving)  
**Files:** `waraq/llm/client.py`, `scripts/test_llm.py`

---

### What was built

#### `waraq/llm/client.py`
Shared LLM client used by every stage downstream.

Key design decisions:
- **`SILMAClient` class** wraps the OpenAI-compatible client pointed at `LLM_BASE_URL` (default `http://localhost:11434/v1`)
- **`complete(prompt, system, temperature) → str`** — free-text generation; standard chat completion
- **`structured(prompt, system, schema, temperature) → dict`** — uses Ollama's `response_format` with `json_schema` type to guarantee valid JSON output. When no schema is given, falls back to `json_object` mode. `schema` accepts a Pydantic model class or a raw JSON schema dict
- **`get_client()`** — module-level singleton factory; all other modules import and call this
- Config loaded from `.env` via `python-dotenv`

#### `scripts/test_llm.py`
Smoke test with two assertions:
1. Free-text Arabic prompt returns a non-empty response
2. Structured prompt with `IntentResult` Pydantic schema returns a dict with `intent` and `reason` keys

#### Environment variable change
Renamed `VLLM_BASE_URL` / `VLLM_MODEL` → `LLM_BASE_URL` / `LLM_MODEL` throughout `.env`, `.env.example`, and `client.py`.

---

### Why Ollama instead of vLLM

vLLM was the original plan but was dropped — it requires a full Linux CUDA environment and is very heavyweight to set up. Ollama is already running with the same SILMA model and exposes an identical OpenAI-compatible API at `http://localhost:11434/v1`, so no application code changes were needed beyond the base URL and structured output mechanism (`response_format` instead of `extra_body.guided_json`).

---

### Definition of done — Stage 3

- [x] `waraq/llm/client.py` implemented with `complete()` and `structured()` methods
- [x] `scripts/test_llm.py` written
- [x] Live test: `python scripts/test_llm.py` passes against a running Ollama server

See `docs/stage3_setup_guide.md` for setup and test instructions.

---

## Stage 4 — Summary Generation (Bottom-Up) ✅

**Status:** Complete (code implemented; run script once to fill hooks)
**Files:** `scripts/run_summary_gen.py`, `waraq/navigation/prompts.py`

---

### What was built

#### `waraq/navigation/prompts.py`
Centralised prompt functions used by both Stage 4 and Stage 5:
- `summarize_leaf_prompt(title, content)` + `summarize_leaf_system()` — asks the model what regulatory/accounting questions this section answers, in a retrieval-friendly style
- `rollup_prompt(title, child_hooks)` + `rollup_system()` — synthesises child summaries into a unified parent hook

#### `scripts/run_summary_gen.py`
Fills every `hook` field in `data/index.json` via bottom-up LLM calls.

Key behaviours:
- **Text source** — reads `data/parsed/markdown/pages/page_N.md` directly; does not touch `output.json`
- **Post-order traversal** — leaf nodes are processed before their parents; parent hooks are rolled up from child hooks
- **Idempotent** — nodes with an existing non-null hook are skipped; safe to interrupt and re-run
- **Atomic saves** — writes to `data/index.json.tmp` then renames; a crashed run never corrupts the file
- **Empty content handling** — if a leaf's page range yields no markdown text, the node is skipped and logged; hook stays null
- **Null child handling** — a non-leaf node is skipped if none of its children have hooks yet

---

### Definition of done — Stage 4

- [x] `scripts/run_summary_gen.py` implemented
- [x] `waraq/navigation/prompts.py` created
- [ ] `python scripts/run_summary_gen.py` completes with all (or near-all) hooks filled
- [ ] Spot-check: 5 hooks read as accurate Arabic summaries relevant to the section content
