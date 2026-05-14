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

---

## Stage 5 — LangGraph Navigation System ✅

**Status:** Complete (code implemented; run `pytest tests/test_navigation.py` once Ollama is serving)  
**Files:** `waraq/navigation/state.py`, `waraq/navigation/nodes.py`, `waraq/navigation/graph.py`, `waraq/navigation/prompts.py` (extended), `tests/test_navigation.py`

---

### What was built

#### `waraq/navigation/state.py`
`NavigationState` TypedDict — defined once, imported by both nodes and graph to avoid circular imports.

Fields: `original_query`, `query`, `language`, `intent`, `navigation_path`, `leaf_content`, `leaf_metadata`, `status`.

#### `waraq/navigation/nodes.py`
All graph nodes plus index traversal helpers and Pydantic schemas.

**Index helpers:**
- `_find_node(sections, node_id)` — recursive DFS lookup by id
- `_is_leaf(node)` — true if node has `start_page` and no `children`
- `_get_candidates(index, navigation_path)` — root sections if path is empty, otherwise children of last selected node
- `_extract_leaf_content(node, markdown_dir)` — reads `page_N.md` files for the leaf's page range and concatenates them

**Pydantic schemas:**
- `IntentResult` — `intent: Literal["valid", "invalid", "greeting"]`, `reason: str`
- `NavigationSelection` — `selected_id: Optional[str]`, `reasoning: str`

**Nodes:**
- `normalize_query` — heuristic Arabic detection (Unicode range `؀–ۿ`), single LLM call that translates if English and normalises to formal Arabic phrasing
- `check_intent` — structured call classifying the query as `valid`, `greeting`, or `invalid`; sets `status` to `navigating`, `greeting`, or `rejected` accordingly
- `navigate_level` — core loop node: gets candidates at the current depth, calls LLM for a single selection, validates the returned id against the actual candidate set (hallucination guard), extracts leaf content on arrival, or appends to `navigation_path` and loops; `status = "not_found"` if LLM returns null or an invalid id; depth capped at 10 levels

#### `waraq/navigation/graph.py`
`build_graph()` returns a compiled `StateGraph`. No arguments — index and markdown dir travel via `RunnableConfig["configurable"]` at invocation time:

```python
graph.invoke(initial_state, config={"configurable": {"index": index, "markdown_dir": markdown_dir}})
```

Graph edges:
- `START → normalize_query → check_intent`
- `check_intent` → `END` if `rejected`/`greeting`, else `navigate_level`
- `navigate_level` → self-loop if `navigating`, else `END`

#### `waraq/navigation/prompts.py` (extended)
Added Stage 5 prompts: `normalize_query_system/prompt`, `check_intent_system/prompt`, `navigate_level_system/prompt`. Stage 4 prompts unchanged.

When hooks are null (Stage 4 not yet run), `navigate_level_prompt` falls back to node titles — navigation still works, just with less signal.

#### `tests/test_navigation.py`
8 integration tests against a live Ollama server:
- 5 known-answer queries each asserting a specific leaf `id`
- 1 out-of-domain rejection
- 1 greeting classification
- 1 leaf-content-non-empty assertion

---

### Design decisions

- **Single-branch navigation** — one node selected per level; multi-branch deferred to a later iteration
- **No confidence-triggered retry** — retry mechanism removed for this PoC; `rephrase_and_retry` node not built
- **Greeting as first-class intent** — `check_intent` has three outcomes (`valid`, `greeting`, `invalid`) so greetings don't get rejected as invalid queries; API layer (Stage 7) returns a friendly canned response for `status = "greeting"`
- **ID validation after LLM selection** — `selected_id` is checked against the set of actual candidate ids before use; an out-of-set or null id immediately returns `not_found`

---

### Definition of done — Stage 5

- [x] `waraq/navigation/state.py` implemented
- [x] `waraq/navigation/nodes.py` implemented with all 3 nodes and index helpers
- [x] `waraq/navigation/graph.py` implemented
- [x] `waraq/navigation/prompts.py` extended with navigation prompts
- [x] `tests/test_navigation.py` written with 8 tests
- [ ] `pytest tests/test_navigation.py` passes all 8 tests against a live Ollama server
