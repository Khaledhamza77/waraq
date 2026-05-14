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

Key behaviours:
- Reconstructs the same page ranges as `run_ingestion.py` from the PDF's page count
- Auto-detects the current page base in each checkpoint and shifts to the correct 1-indexed full-document position
- Checkpoint files are **never modified** — read-only
- Atomic write for `output.json`
- Corrupt checkpoint exits with a clear message
- Safe to re-run (idempotent)

#### `scripts/build_markdown.py`
Converts `output.json` into human-readable markdown files for inspection.

Key behaviours:
- Sorts chunks by `(page, grounding.box.top)` — page order, then top-to-bottom within each page
- Writes `data/parsed/markdown/document.md` — full document with `---` page separators and `<!-- page N -->` comments
- Writes `data/parsed/markdown/pages/page_N.md` — one file per page
- Chunks with no page number are skipped with a warning rather than crashing
- `output.json` and all `part_N.json` files are never modified

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

## Stage 3 — SILMA-9B via vLLM ✅

**Status:** Complete (code implemented; server startup requires WSL2 + GPU)  
**Files:** `waraq/llm/client.py`, `scripts/start_vllm.sh`, `scripts/test_vllm.py`

---

### What was built

#### `waraq/llm/client.py`
Shared SILMA client used by every stage downstream.

Key design decisions:
- **`SILMAClient` class** wraps the OpenAI-compatible client pointed at `VLLM_BASE_URL` (default `http://localhost:8001/v1`)
- **`complete(prompt, system, temperature) → str`** — free-text generation; standard chat completion
- **`structured(prompt, system, schema, temperature) → dict`** — passes `guided_json` in `extra_body` to vLLM, guaranteeing valid JSON output without parsing fragility. `schema` accepts either a Pydantic model class or a raw JSON schema dict
- **`get_client()`** — module-level singleton factory; all other modules import and call this rather than instantiating directly
- Config loaded from `.env` via `python-dotenv`; no hardcoded URLs or model names

#### `scripts/start_vllm.sh`
Bash script for WSL2; starts vLLM on port 8001 with bfloat16, 8192 token context, 90% GPU memory utilisation. Accepts passthrough flags.

#### `scripts/test_vllm.py`
Smoke test that:
1. Sends a free-text Arabic prompt and asserts a non-empty response
2. Sends a structured prompt with `IntentResult` (Pydantic) schema and asserts `intent` + `reason` keys are present in the JSON response

#### `pyproject.toml` update
Added `[project.optional-dependencies] server = ["vllm>=0.4.0"]` — vLLM is installed on the WSL2/Linux side only, not bundled into the main project dependencies.

---

### Definition of done — Stage 3

- [x] `waraq/llm/client.py` implemented with `complete()` and `structured()` methods
- [x] `scripts/start_vllm.sh` written for WSL2 deployment
- [x] `scripts/test_vllm.py` written (run once vLLM server is live)
- [ ] Live test: `python scripts/test_vllm.py` passes against a running vLLM server

See `docs/stage3_setup_guide.md` for full WSL2 setup and test instructions.
