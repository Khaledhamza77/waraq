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

## Stage 4a — Hook Normalization ✅

**Status:** Complete  
**Files:** `scripts/normalize_hooks.py`, `waraq/llm/client.py` (extended)

---

### What was built

#### `scripts/normalize_hooks.py`
Programmatic (no LLM) cleanup pass over every hook in `data/index.json`. Fixes artifacts introduced during Stage 4 LLM generation.

Normalization rules applied in order:
1. **Bold stripping** — removes `**text**` and `__text__` markdown markers; runs first so paired tokens are matched before any leading `**` is consumed by the garbage stripper
2. **Leading garbage stripping** — skips any non-Arabic prefix characters until the first valid Arabic character, digit, quote, or open paren; handles:
   - Leaked `<think>` / `</think>` tags and `[]>` think artifacts
   - Tokenizer padding tokens (`[PAD151871]` style)
   - Stray Unicode characters (Korean, Cyrillic-like, Chinese)
3. **Arabic preamble stripping** — removes common model throat-clearing phrases (`بالطبع`, `إليك`, `الملخص:`, etc.) from the hook start
4. **Template artifact fix** — replaces `مصد={...}` with `المصداقية`

Key behaviours:
- **No LLM calls** — purely textual regex/string operations; fast and deterministic
- **`--dry-run` mode** — prints every BEFORE/AFTER pair without writing to disk; used for review before committing
- **Atomic saves** — writes to `data/index.json.tmp` then renames after each changed node
- **Idempotent** — safe to re-run; unchanged hooks produce no diff

#### `waraq/llm/client.py` — `think` parameter
Added optional `think: bool | None = None` parameter to `SILMAClient.complete()`. When set, passes `"think": think` into `extra_body`, enabling `think=False` for qwen3's non-thinking mode on generation calls where format precision matters (used by Stage 4b script).

---

### Artifacts fixed across `data/index.json`

| Type | Example | Nodes affected |
|------|---------|----------------|
| `**bold**` markers | `**ملخص القسم: العنوان**  \n` | ~60 |
| Leaked think tags | `[]> \n</think>\n\n` (section_7) | 2 |
| Stray Unicode prefix | `모습` Korean (section_6), `Ԉ` (section_9) | 3 |
| Tokenizer padding | `[PAD151871]` (section_6_25) | 1 |
| Template artifact | `مصد={...}` → `المصداقية` (section_3_4) | 1 |
| Chinese + think residue | `区委\n</think>` (section_4_9_4) | 1 |

Total: 98 nodes modified out of all nodes with hooks.

---

### Definition of done — Stage 4a

- [x] `scripts/normalize_hooks.py` implemented with `--dry-run` mode
- [x] `think` parameter added to `SILMAClient.complete()`
- [x] Dry-run reviewed and two bugs caught + fixed (ordering of bold strip, `_ARABIC_START_RE` regex)
- [ ] Script run without `--dry-run`; `data/index.json` updated
- [ ] Spot-check: previously garbage-prefixed hooks (`section_6`, `section_7`, `section_9`) now start with clean Arabic

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

---

## Stage 6 — Response Generation ✅

**Status:** Complete (code implemented; run `pytest tests/test_responder.py` once Ollama is serving)
**Files:** `waraq/generation/responder.py`, `waraq/navigation/prompts.py` (extended), `tests/test_responder.py`

---

### What was built

#### `waraq/generation/responder.py`
Final answer generation module. Three public exports:

- **`generate_answer(query, leaf_content, leaf_metadata) → dict`** — structured LLM call (`structured()` with Pydantic schema) that produces `{"answer": str, "citation": {"node_id", "title", "pages": {"start", "end"}}}`. Called by Stage 7 when `status == "found"`.
- **`generate_greeting(query) → str`** — free-text LLM call (`complete()`) that returns a friendly Arabic introduction explaining what the system does. Called by Stage 7 when `status == "greeting"`.
- **`NOT_FOUND_ANSWER: str`** — canned Arabic constant returned by Stage 7 when `status == "not_found"`. No LLM call.

**Pydantic schemas** (internal to module):
- `_Pages` — `start: int`, `end: int`
- `_Citation` — `node_id: str`, `title: str`, `pages: _Pages`
- `_AnswerResponse` — `answer: str`, `citation: _Citation`

#### `waraq/navigation/prompts.py` (extended)
Added Stage 6 prompts:
- `answer_system()` — Arabic legal/accounting assistant system prompt enforcing source-only answers and JSON output
- `answer_prompt(query, leaf_metadata, leaf_content)` — assembles query + source list (with page ranges and ids) + full leaf markdown content
- `greeting_system()` — instructs the model to respond in the user's language and introduce the system's capabilities
- `greeting_prompt(query)` — passes the raw query through unchanged

#### `tests/test_responder.py`
7 tests: 1 pure unit test (no Ollama), 6 integration tests:
- `test_not_found_answer_is_nonempty_arabic` — unit, asserts the constant is a non-empty Arabic string
- `test_generate_answer_returns_dict` — asserts non-empty dict returned
- `test_generate_answer_has_answer_field` — asserts `answer` key is a non-trivial string
- `test_generate_answer_has_citation_field` — asserts `citation` key with `node_id`, `title`, `pages`
- `test_generate_answer_citation_pages_structure` — asserts `pages` has integer `start` and `end` keys
- `test_generate_greeting_returns_nonempty_string` — Arabic greeting input
- `test_generate_greeting_english_input` — English greeting input

---

### Bug fixed — `_clean_schema` in `waraq/llm/client.py`

The original `inline()` helper stripped all dict keys named `"title"` — including property *names* inside a JSON schema `properties` object. This silently removed any Pydantic field named `title` from the schema sent to Ollama. The `_Citation` schema has a `title` field, so this bug would have caused it to be omitted from the structured output contract.

Fix: when processing a `"properties"` key, iterate over property names without filtering, then strip `"title"` only from within each property's schema node. This correctly removes Pydantic's decorative title metadata while preserving fields whose name happens to be `title`.

---

### Design decisions

- **`structured()` over `complete()` for answer generation** — guarantees valid JSON; consistent with Stage 5 approach. The plan mentioned `complete()` but structured output is strictly more reliable here.
- **Greeting handled by responder, not_found is a constant** — greeting benefits from an LLM response that can adapt to the user's language; not_found is deterministic and needs no LLM call.
- **`generate_answer` takes individual params, not the full `NavigationState`** — keeps the responder decoupled from the graph's internal state shape; Stage 7 unpacks what it needs.
- **Full leaf content passed as-is** — no truncation. qwen3:8b via Ollama is configured with `num_ctx: 32768`; truncation deferred until it becomes a practical problem.
- **Model note** — active model is `qwen3:8b` (not `silma-v1` as originally planned); `LLM_MODEL` env var controls this with no code changes needed.

---

### Definition of done — Stage 6

- [x] `waraq/generation/responder.py` implemented with `generate_answer`, `generate_greeting`, `NOT_FOUND_ANSWER`
- [x] `waraq/navigation/prompts.py` extended with Stage 6 prompts
- [x] `_clean_schema` bug fixed in `waraq/llm/client.py`
- [x] `tests/test_responder.py` written with 7 tests (1 unit + 6 integration)
- [x] `tests/test_nav_responder.py` written with 6 end-to-end integration tests
- [ ] `pytest tests/test_responder.py` passes against a live Ollama server
- [ ] `pytest tests/test_nav_responder.py` passes against a live Ollama server

---

### End-to-end test — `tests/test_nav_responder.py`

Chains the full pipeline (navigate → respond) for each of the 5 known-answer queries from Stage 5, plus the greeting case. Each test asserts both navigation correctness (leaf lands in the expected section) and response quality (answer non-empty, citation shape valid, page numbers are integers with `start >= 1` and `end >= start`).

**`_run_full(graph_config, query)`** — the shared pipeline helper. Runs the graph, then branches on status:
- `found` → calls `generate_answer(nav["query"], nav["leaf_content"], nav["leaf_metadata"])`
- `greeting` → calls `generate_greeting(nav["original_query"])` (original phrasing, not normalized)
- `not_found` → returns `NOT_FOUND_ANSWER` constant, no LLM call
- `rejected` → returns empty answer, no LLM call

**Log output per test** (visible with `--log-cli-level=DEBUG`):
1. Query header
2. Navigation graph's own DEBUG lines (candidates, LLM selections, depth)
3. Navigation result block: status, intent, language, normalized query, navigation path, leaf titles + page ranges, content length
4. Responder handoff block: normalized query, number of sources
5. Responder output block: first 300 chars of answer, citation node_id, title, pages

**Run with:**
```
pytest tests/test_nav_responder.py -v --log-cli-level=DEBUG
```

---

## Stage 7 — Chainlit Application ✅

**Status:** Complete (code implemented; install dependencies then run)
**Files:** `app/server.py` (new), `app/chainlit_app.py` (moved from root), `waraq/observability/tracer.py`, `pyproject.toml` (updated)

---

### What was built

#### `waraq/observability/tracer.py`
Thin, fail-safe Langfuse wrapper. Never raises — all exceptions are caught and logged.

- **`get_langfuse()`** — lazy singleton. Returns `None` silently if `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` are absent or if `langfuse` is not installed. Sets `_disabled = True` on first failure to avoid repeated retry overhead.
- **`safe_span(parent, name, input, output)`** — creates a Langfuse span on a trace or parent span. If `output` is provided, closes the span immediately (single-shot pattern). Returns `None` on any failure.
- **`safe_end(span, output)`** — closes an open span. No-op if span is `None`.
- **`flush()`** — flushes buffered Langfuse events. Reads `_langfuse` directly (no init trigger).

#### `app/server.py`
FastAPI entry point. Mounts Chainlit at `/chainlit`, exposes `GET /custom-auth` and `GET /documents/{path}`, and sets CORS for Vite dev (`5173`) and preview (`4173`) ports. `_ROOT` and `_DOCUMENTS_DIR` are anchored to `Path(__file__).parent.parent` (repo root) — safe regardless of working directory.

#### `app/chainlit_app.py`
Chainlit handlers. Loaded by `app/server.py` via `mount_chainlit`.

**`@cl.on_chat_start`**: Reads `data/index.json`, calls `build_graph()`, stores both in the Chainlit user session. Index and graph are per-session (one load per connected client). `_ROOT` anchored to `Path(__file__).parent.parent` (repo root).

**`@cl.on_message`**: Full pipeline handler.
1. Creates a Langfuse trace (`waraq_query`) with the raw user query as input.
2. Sends an initial Chainlit message bubble with "جاري تحليل نية السؤال..."
3. Streams `graph.astream(initial, config, stream_mode="updates")` — **async, per-node**. Each yielded chunk fires:
   - A Chainlit message update with a human-readable Arabic status string
   - A closed Langfuse span for that node (input = query + current navigation path; output = all state updates except `leaf_content`)
4. Accumulates full navigation state via `nav.update(updates)` across all chunks.
5. Branches on `pipeline_status`:
   - **`found`** → updates status to "جاري صياغة الإجابة...", opens a `generate_answer` Langfuse span, calls `generate_answer()` in `asyncio.to_thread`, closes the span, formats answer + citations as markdown.
   - **`greeting`** → calls `generate_greeting()` in `asyncio.to_thread`, logs a `generate_greeting` span.
   - **`not_found`** → returns `NOT_FOUND_ANSWER` constant; no LLM call.
   - **`rejected`** → returns a canned Arabic rejection; no LLM call.
6. Sets `msg.content` to the final markdown and calls `await msg.update()`.
7. Updates the Langfuse trace output with `{status, navigation_path, navigation_levels, answer_chars}` and flushes.

**Error handling**: a top-level `try/except` around `graph.astream` shows a user-facing Arabic error message, updates the trace with `{"error": "graph_stream_failed"}`, and returns cleanly.

#### `pyproject.toml`
- Added `chainlit>=2.0.0`, `fastapi`, `uvicorn` (FastAPI + Chainlit together via `mount_chainlit`)

---

### Langfuse trace shape

```
trace: waraq_query  {input: {query}}
  ├── span: check_intent         {input: {query, path:[]}, output: {intent, status}}
  ├── span: normalize_query      {input: {query, path:[]}, output: {query, language}}
  ├── span: navigate_level_1     {input: {normalized_query, path:[...]}, output: {navigation_path, status}}
  ├── span: navigate_level_N     {input: {normalized_query, path:[...]}, output: {leaf_metadata, status}}
  └── span: generate_answer      {input: {query, sources, content_chars, leaf_count}, output: {answer_chars, citations}}
  [output: {status, navigation_path, navigation_levels, answer_chars}]
```

---

### Run instructions

```bash
# Terminal 1 — backend
uvicorn app.server:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — frontend
cd frontend && npm install && npm run dev
```

---

### Design decisions

- **`graph.astream()` over `graph.invoke()`** — native async generator yields after each node, enabling real-time status updates in Chainlit and per-node Langfuse spans without threads or queues.
- **`asyncio.to_thread` for LLM generation calls** — `generate_answer` and `generate_greeting` make blocking HTTP calls to Ollama; running them in a thread pool prevents blocking the Chainlit event loop.
- **`leaf_content` excluded from Langfuse spans** — can be tens of thousands of characters; metadata (titles, page ranges, char count) captures the same signal without bloating traces.
- **Tracing never touches UX** — every Langfuse call is inside `try/except`; a Langfuse outage is invisible to the user.
- **Per-session graph/index load** — simple and safe; avoids shared mutable state between sessions.

---

### Test — `tests/test_chainlit_app.py`

Mixed unit + integration test file. 7 unit tests (no Ollama), 4 integration tests (Ollama required).

**Strategy:** The entire `chainlit` package is replaced in `sys.modules` with a `MagicMock` before `app.chainlit_app` is imported (`import app.chainlit_app as chainlit_app`). This makes `@cl.on_chat_start` and `@cl.on_message` transparent pass-through decorators, leaving the handler functions directly callable as plain async coroutines. `cl.Message` is replaced with `_FakeMessage`, a minimal class that appends every instance to a class-level list so tests can inspect the final `.content` sent to the user.

**`_FakeMessage` tracking:** `on_message` creates exactly one `cl.Message` object per turn (the AI response bubble) and mutates its `.content` through the streaming process. `_FakeMessage._instances[-1]` after the call always holds the final message state.

**Unit tests:**
- `test_on_chat_start_populates_session` — verifies the session receives a non-None graph and a config dict with `index` (dict with `sections`) and `markdown_dir`
- `test_format_response_no_citations` — answer with empty citations returns the answer string unchanged
- `test_format_response_single_page_citation` — `start == end` → `"صفحة N"` (singular), no `"صفحات"`
- `test_format_response_multi_page_citation` — `start != end` → `"صفحات N–M"` form
- `test_format_response_multiple_citations` — two citations produce two `"- "` list items
- `test_span_output_excludes_leaf_content` — `_span_output_from_updates` strips `leaf_content` but preserves all other fields
- `test_graph_stream_failure_shows_arabic_error` — replaces the session graph with a mock whose `astream` raises `RuntimeError` immediately; verifies the final message contains "خطأ" (Arabic for "error")

**Integration tests:**
- `test_on_message_greeting` — "مرحباً" → non-trivial string, no "المصادر"
- `test_on_message_valid_accounting_query` — known-answer query → substantive answer with "المصادر" section
- `test_on_message_rejected_query` — off-topic (cooking) → short rejection, no citations
- `test_langfuse_disabled_does_not_affect_response` — patches `get_langfuse` to return None; answer quality identical to normal path

**Run:**
```
pytest tests/test_chainlit_app.py -v -m "not integration"   # unit only, no Ollama
pytest tests/test_chainlit_app.py -v --log-cli-level=DEBUG  # all tests
```

---

### Definition of done — Stage 7

- [x] `app/server.py` — FastAPI app with `mount_chainlit`, CORS, `/custom-auth`, `/documents/{path}`
- [x] `app/chainlit_app.py` — `@cl.on_chat_start` and `@cl.on_message` handlers
- [x] `waraq/observability/tracer.py` implemented with `get_langfuse`, `safe_span`, `safe_end`, `flush`
- [x] `pyproject.toml` updated — `chainlit`, `fastapi`, `uvicorn` added
- [x] `_ROOT` anchored to `Path(__file__).parent.parent` in both `app/` files (CWD-safe)
- [x] `_NODE_STATUS` covers all graph nodes including `rephrase_and_retry`
- [x] CORS includes `5173` (dev) and `4173` (preview)
- [x] `tests/test_chainlit_app.py` written — 7 unit tests + 4 integration tests; import updated to `app.chainlit_app`
- [ ] `npm install` in `frontend/`
- [ ] End-to-end smoke test: send a query through the Vite frontend, verify response appears and Langfuse trace is recorded

---

## Stage 10 — Document Explorer 🚧

**Status:** Code complete + code-reviewed — pending run of build script and browser smoke-test
**Files:** `scripts/build_section_chunks.py` (new), `app/explorer_router.py` (new), `app/server.py` (updated), `pyproject.toml` (updated), `frontend/src/pages/ExplorerPage.tsx` (complete rewrite)

---

### What was built

#### `scripts/build_section_chunks.py`
One-shot pre-processing script.  `data/bbox_map.json` is the source of truth: only sections with non-null `start_box`/`end_box` get entries (144 sections out of 156 index leaves).  For each such section, the page range is `start_box.page`→`end_box.page`; every chunk from `data/parsed/output.json` whose `grounding.page` falls in that range is collected.  `data/index.json` enriches each entry with `title` and `hook` for sidebar display.

Output schema: `data/section_chunks.json` — `{ section_id: { title, hook, start_page, end_page, chunks: [{chunk_id, page, box, markdown, type}] } }`

Run once (idempotent — overwrites):
```bash
python scripts/build_section_chunks.py
```

#### `app/explorer_router.py`
FastAPI `APIRouter` (prefix `/explorer`, tags `["explorer"]`) with three endpoints:

| Endpoint | Behaviour |
|----------|-----------|
| `GET /explorer/index` | Returns `data/index.json` section tree |
| `GET /explorer/page/{page_num}` | Renders PDF page as PNG via PyMuPDF at 1.5× zoom (≈108 DPI); results cached in `_page_cache` dict |
| `GET /explorer/section/{section_id}/chunks` | Returns the full entry from `section_chunks.json` |

PDF, index, and section_chunks are loaded lazily as module-level singletons on first request.  PyMuPDF import is guarded: `import pymupdf as fitz` falls back to `import fitz` for older package versions.  All three `FileNotFoundError` cases (missing PDF, missing index, missing section_chunks.json) are caught and re-raised as `HTTPException(503)` with actionable messages.

#### `app/server.py` — change
Added `from app.explorer_router import router as explorer_router` and `app.include_router(explorer_router)` before the Chainlit mount.

#### `pyproject.toml` — change
Added `fastapi>=0.100.0` and `uvicorn[standard]>=0.23.0` as explicit top-level dependencies (they were previously only transitive via chainlit). `pymupdf>=1.24.0` was already present. After this change, `uv sync` installs all backend requirements including the PDF renderer.

#### `frontend/src/pages/ExplorerPage.tsx` — complete rewrite
Full document explorer replacing the "coming soon" placeholder.

**Layout:** 3-zone dark-theme layout — fixed 52px header, flex body (document viewer left + 290px TOC sidebar right), `position:fixed` content panel (bottom drawer).

**Document Viewer:** Renders all 208 pages stacked vertically using `<img loading="lazy" decoding="async">`. Each page container has `aspectRatio: "210 / 297"` (A4) so it holds correct height before the image loads — this makes `scrollIntoView` land on the right page. When a section is selected, bbox overlays are absolutely-positioned `<div>` elements using normalised 0–1 coordinates from `chunk.box`. Boxes are semi-transparent with a coloured border; hover brightens; the active (clicked) box gets a stronger fill. `React.memo` on `PageView` plus a stable `EMPTY_CHUNKS` constant prevent re-renders for pages that have no chunks.

**TOC Sidebar (290px, RTL-native):** Recursive `TocNode` tree with expand/collapse. Right-side border indicator on selected node; right padding grows with depth (correct RTL-start-side indentation). Sections are colour-coded by top-level parent (`section_1`→slate, `section_2`→cyan, `section_3`→violet, `section_4`→blue, `section_5`→purple, `section_6`→emerald, `section_7`→amber, `section_8`→red, `section_9`→green). Sections without bbox data are dimmed. Re-clicking the selected section deselects it. "إلغاء التحديد" button at bottom when something is selected.

**Content Panel:** `position:fixed` drawer (42vh) slides up with `slideUp` CSS animation when a bbox is clicked. Header shows chunk type badge + page number; body is `ReactMarkdown`-rendered Arabic content with `dir="rtl"`. Closes on ✕ button or selecting a new section.

**State flow:**
1. Mount → `GET /explorer/index` → populate TOC
2. TOC click → `GET /explorer/section/{id}/chunks` → build `page→Chunk[]` map → set bbox overlays → `scrollIntoView` first chunk page (80ms delay to let React flush)
3. Bbox click → set `activeChunk` → open content panel
4. Re-click selected section / "إلغاء التحديد" / ✕ → clear state

---

### Code review — bugs found and fixed

Six issues were caught and fixed after initial implementation:

| # | Severity | Location | Bug | Fix |
|---|----------|----------|-----|-----|
| 1 | Critical | `pyproject.toml` | `fastapi` and `uvicorn` missing as explicit deps; only transitive via chainlit | Added both with version bounds |
| 2 | Critical | `ExplorerPage.tsx` | `scrollIntoView` always jumped to page 1 — pages had `height: 0` before lazy images loaded, so all 208 page divs were stacked at the top | Added `aspectRatio: "210 / 297"` to page container |
| 3 | Bug | `ExplorerPage.tsx` | RTL indentation broken — left padding increased with depth but text is right-aligned, so no visual hierarchy appeared | Swapped to right padding: `padding: 5px ${14+depth*14}px 5px 12px` |
| 4 | Bug | `explorer_router.py` | `FileNotFoundError` (missing PDF / `section_chunks.json`) propagated as unhandled 500 | Wrapped `_get_pdf()` and `_get_section_chunks()` calls in `try/except FileNotFoundError` → `HTTPException(503)` with action message |
| 5 | Minor | `ExplorerPage.tsx` | `viewerRef` declared and attached but never read — dead code | Removed ref and unused `useRef` import |
| 6 | Minor | `ExplorerPage.tsx` | `pageChunks.get(pageNum) ?? []` created a new array reference every render, defeating `React.memo` on `PageView` for all pages with no chunks | Introduced module-level `EMPTY_CHUNKS: Chunk[] = []` stable constant |

---

### Definition of done — Stage 10

- [x] `scripts/build_section_chunks.py` written and reviewed
- [x] `app/explorer_router.py` written and reviewed (3 endpoints, `FileNotFoundError` handled)
- [x] `app/server.py` updated — explorer router included
- [x] `pyproject.toml` updated — `fastapi` and `uvicorn` declared explicitly
- [x] `frontend/src/pages/ExplorerPage.tsx` complete rewrite, all review bugs fixed
- [ ] `uv sync` — installs all deps including PyMuPDF, FastAPI, uvicorn
- [ ] `python scripts/build_section_chunks.py` — generates `data/section_chunks.json`
- [ ] Backend: `uvicorn app.server:app --host 0.0.0.0 --port 8000 --reload`
- [ ] Frontend: `cd frontend && npm run dev`
- [ ] Smoke test: `/explorer` loads → TOC renders → click a section → bboxes appear on correct page → click a bbox → content panel shows Arabic markdown → deselect clears all highlights

---

## Stage 8 — Per-LLM-call Langfuse Generation Tracing ✅

**Status:** Complete (code implemented; requires Langfuse stack running — see `docs/langfuse_setup.md`)
**Files:** `waraq/observability/tracer.py` (extended), `waraq/llm/client.py` (extended), `app/chainlit_app.py` (updated), `docker-compose.yml` (cleaned), `.env.example` (updated), `docs/langfuse_setup.md` (new)

---

### What was built

#### `waraq/observability/tracer.py` — additions

- **`ContextVar[Any] _trace_parent`** — holds the current Langfuse trace for the active async context. Python 3.7+ copies `ContextVar` values into threads spawned via `asyncio.to_thread()`, so the same parent is visible both inside LangGraph node coroutines and in the thread-pool workers that run `generate_answer` / `generate_greeting`.
- **`set_trace_parent(parent) → Token`** — sets the parent for the current context; returns a reset token.
- **`reset_trace_parent(token)`** — restores the previous value; called in the `finally` block of `on_message`.
- **`safe_generation(name, model, messages, completion, prompt_tokens, completion_tokens)`** — logs one Langfuse `generation` object under the current parent. Records the full prompt messages list, the raw completion string, and token counts from the OpenAI response. No-op when tracing is disabled or no parent is set.

#### `waraq/llm/client.py` — additions

`SILMAClient.complete()` and `SILMAClient.structured()` each call `safe_generation()` immediately after the Ollama API call returns. Token counts come from `response.usage` (`prompt_tokens`, `completion_tokens`). `structured()` retries up to twice on JSON decode errors — each API attempt is logged separately, so retry attempts are visible in Langfuse.

#### `app/chainlit_app.py` — changes

- Imports `set_trace_parent`, `reset_trace_parent` from `tracer`.
- After creating the Langfuse trace (or `None`), calls `token = set_trace_parent(trace)`.
- Wraps the entire graph-stream + response-generation block in `try/finally`. The `finally` calls `reset_trace_parent(token)` and `flush()` — guarantees cleanup on both the happy path and the error path (the inner `graph.astream` except block uses `return`, not `raise`, so `finally` still fires).

#### `docker-compose.yml` — cleaned

Stripped to the two services waraq actually needs — `postgres` and `langfuse`. Removed: `app`, `qdrant`, `redis` services and their volumes and networks. The `observability` network is the only one remaining.

#### `docs/langfuse_setup.md` — new

Step-by-step setup guide: create data directories, start the stack, create a Langfuse account and API keys, add keys to `.env`, verify a trace, stop the stack, and a troubleshooting table.

---

### Langfuse trace shape (Stage 8 — complete)

```
trace: waraq_query  {input: {query: "..."}}
  ├── span: normalize_query
  │     └── generation: structured  {model, prompt, completion, prompt_tokens, completion_tokens}
  ├── span: check_intent
  │     └── generation: structured  {model, prompt, completion, prompt_tokens, completion_tokens}
  ├── span: navigate_level_1
  │     └── generation: structured  {model, prompt, completion, prompt_tokens, completion_tokens}
  ├── span: navigate_level_N
  │     └── generation: structured  {model, prompt, completion, prompt_tokens, completion_tokens}
  └── span: generate_answer
        └── generation: structured  {model, prompt, completion, prompt_tokens, completion_tokens}
  [output: {status, navigation_path, navigation_levels, answer_chars}]
```

Greeting path replaces the last span with `generate_greeting` and a `generation: complete` child.

---

### Design decisions

- **`ContextVar` over explicit param threading** — passing a `span` argument through every LangGraph node, every prompt function, and both responder functions would require touching ~10 files and changing all function signatures. `ContextVar` gives automatic propagation with zero signature changes and correct async task + thread isolation.
- **Raw completion logged (not cleaned)** — `safe_generation` logs `raw` (before `_clean_llm_output`), so thinking blocks and any JSON decode issues are visible in Langfuse exactly as the model produced them.
- **One generation per API call** — `structured()` logs each retry attempt separately. If a JSON decode fails and a second attempt is made, both appear in the trace, which surfaces model reliability issues.
- **Token counts via `response.usage`** — Ollama reports token counts in the OpenAI-compatible response; `getattr(..., 0) or 0` guards against `None` from servers that omit usage.

---

### Run instructions

```bash
# 1 — Start Langfuse (first time: mkdir -p data/postgres data/langfuse)
docker compose up -d

# 2 — Create account + project at http://localhost:3000, copy API keys to .env

# 3 — Run waraq
uvicorn app.server:app --host 0.0.0.0 --port 8000 --reload

# 4 — Verify traces at http://localhost:3000
```

Full setup walkthrough: `docs/langfuse_setup.md`

---

### Definition of done — Stage 8

- [x] `waraq/observability/tracer.py` extended with `set_trace_parent`, `reset_trace_parent`, `safe_generation`
- [x] `waraq/llm/client.py` extended — `complete()` and `structured()` call `safe_generation()` per API call
- [x] `app/chainlit_app.py` updated — trace parent set/reset via `ContextVar` in `try/finally`
- [x] `docker-compose.yml` cleaned to postgres + langfuse only
- [x] `.env.example` updated with docker-compose vars
- [x] `docs/langfuse_setup.md` written
- [ ] `docker compose up -d` on target machine
- [ ] Langfuse account + API keys created at `http://localhost:3000`
- [ ] Keys added to `.env`, `chainlit run` restarted
- [ ] Trace verified in Langfuse UI after a live query
