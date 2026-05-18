# waraq — Repository Overview Checkpoint
**Date:** 2026-05-18  
**Branch:** main  
**Last commit:** cloud models + prompt improvements + fixing some bugs

---

## What waraq is

waraq is an Arabic-language RAG (Retrieval-Augmented Generation) system that answers questions about Egyptian Accounting Standards (معايير المحاسبة المصرية). It navigates a hierarchical document index using an LLM-driven tree traversal rather than vector similarity search, then generates grounded answers with page-level citations.

---

## Tech stack

| Layer | Technology |
|---|---|
| LLM (local) | Ollama — `qwen3:8b` (OpenAI-compatible API at `localhost:11434/v1`) |
| LLM (cloud) | OpenAI API — `gpt-5.4-mini` (or any model via `OPENAI_MODEL`) |
| Navigation graph | LangGraph `StateGraph` |
| Application server | FastAPI + Chainlit (mounted via `mount_chainlit`) |
| Frontend | React + TypeScript (Vite) |
| Observability | Langfuse (self-hosted via Docker Compose) |
| PDF parsing | LandingAI ADE + PyMuPDF |
| Config | `python-dotenv` — `.env` at repo root |

---

## Repository structure

```
waraq/
├── app/
│   ├── server.py              # FastAPI entry point; mounts Chainlit + explorer router
│   ├── chainlit_app.py        # @cl.on_chat_start / @cl.on_message handlers
│   └── explorer_router.py     # /explorer endpoints (index, page render, section chunks)
├── waraq/
│   ├── llm/
│   │   └── client.py          # SILMAClient — complete() + structured(), Ollama/OpenAI switch
│   ├── navigation/
│   │   ├── state.py           # NavigationState TypedDict
│   │   ├── nodes.py           # classify_and_normalize, navigate_level nodes + helpers
│   │   ├── graph.py           # build_graph() — 2-node LangGraph StateGraph
│   │   └── prompts.py         # All LLM prompt functions (navigation + generation + scripts)
│   ├── generation/
│   │   └── responder.py       # generate_answer(), generate_greeting(), NOT_FOUND_ANSWER
│   └── observability/
│       └── tracer.py          # Langfuse wrapper — safe_span, safe_generation, ContextVar parent
├── data/
│   ├── index.json             # Master document index (hierarchical, with hooks)
│   ├── parsed/output.json     # LandingAI ADE parse output
│   └── parsed/markdown/pages/ # page_N.md — one file per PDF page
├── scripts/
│   ├── run_ingestion.py       # PDF → output.json (LandingAI, idempotent, checkpointed)
│   ├── build_markdown.py      # output.json → markdown files
│   ├── run_summary_gen.py     # Fills index.json hooks via bottom-up LLM summarisation
│   ├── normalize_hooks.py     # Programmatic cleanup of hook text artifacts
│   ├── rebuild_section_hooks.py  # Targeted hook rebuild for specific sections
│   └── build_section_chunks.py   # Builds data/section_chunks.json for explorer
├── tests/
│   ├── test_chainlit_app.py   # Unit + integration tests for chainlit handlers
│   ├── test_navigation.py     # Integration tests for navigation graph
│   ├── test_nav_responder.py  # End-to-end integration: navigate → respond
│   └── test_responder.py      # Unit + integration tests for responder
├── frontend/                  # React/TypeScript Vite app
└── docs/                      # Progress log, setup guides, design docs
```

---

## Configuration (`.env`)

| Variable | Purpose | Default |
|---|---|---|
| `LOCAL_INFERENCE` | `true` = Ollama, `false` = OpenAI | `true` |
| `LLM_BASE_URL` | Ollama endpoint | `http://localhost:11434/v1` |
| `LLM_MODEL` | Ollama model name | `qwen3:8b` |
| `OPENAI_API_KEY` | Required when `LOCAL_INFERENCE=false` | — |
| `OPENAI_MODEL` | OpenAI model name | `gpt-5.4-mini` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse project public key | — |
| `LANGFUSE_SECRET_KEY` | Langfuse project secret key | — |
| `LANGFUSE_HOST` | Langfuse server URL | `http://localhost:3000` |

---

## How to run

```bash
# Switch inference provider
# LOCAL_INFERENCE=true   → Ollama (start Ollama first)
# LOCAL_INFERENCE=false  → OpenAI (set OPENAI_API_KEY)

# Backend
uvicorn app.server:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd frontend && npm install && npm run dev

# Tests (unit only, no Ollama/OpenAI needed)
pytest tests/test_chainlit_app.py -v -m "not integration"

# Tests (integration, with timing output)
pytest tests/test_navigation.py tests/test_nav_responder.py -v --log-cli-level=INFO
```

---

## End-to-end request flow

```
User message
    │
    ▼
@cl.on_message (chainlit_app.py)
    │  Creates Langfuse trace
    │  Streams graph via graph.astream()
    │
    ▼
classify_and_normalize (nodes.py)
    │  Arabic detection (regex)
    │  structured() → { intent, normalized_query, language }
    │  intent=valid    → status="navigating"
    │  intent=greeting → status="greeting" → END
    │  intent=invalid  → status="rejected"  → END
    │
    ▼
navigate_level (nodes.py) — loops until leaf reached
    │  Gets candidates from index at current depth
    │  structured() → { selected_ids }  (1 id for intermediate, ≤3 for final)
    │  Validates selected ids against actual candidate set (hallucination guard)
    │  On leaf arrival: reads page_N.md files → leaf_content, leaf_metadata
    │  status="navigating" → loop | status="found"/"not_found" → END
    │
    ▼
Response generation (responder.py)
    │  found     → generate_answer()   → complete() with max_tokens=4096
    │  greeting  → generate_greeting() → complete()
    │  not_found → NOT_FOUND_ANSWER constant (no LLM call)
    │  rejected  → canned Arabic rejection (no LLM call)
    │
    ▼
_format_response() → answer + **المصادر** section with page-linked citations
    │
    ▼
msg.update() → rendered in Chainlit UI
```

---

## Supported features

### Core Q&A
- Arabic and English input — English queries are translated to Arabic before navigation
- Spelling/grammar normalisation of Arabic queries before navigation
- Grounded answers citing specific sections and page ranges
- Two-tier answer format: direct answer to the question + brief **مواضيع ذات صلة** for related content not asked about
- Citation links in the response navigate to `/explorer?section=...&page=...`

### Intent handling
- **Valid accounting query** → full navigate + answer pipeline
- **Greeting/conversational** → friendly Arabic introduction (LLM-generated, language-adaptive)
- **Off-topic / rejected** → canned Arabic rejection, no navigation
- **Section not found** → canned Arabic not-found message

### Navigation
- Tree traversal over `data/index.json` — ~156 leaf nodes across 208 pages
- Intermediate levels: single branch selected per level
- Final level: up to 3 most-relevant sections, ranked by relevance
- Leaf content assembled from `data/parsed/markdown/pages/page_N.md`
- Depth capped at 10 levels

### Document Explorer (`/explorer`)
- Full 208-page PDF viewer with per-section bounding-box overlays
- Hierarchical TOC sidebar with colour-coding by top-level section
- Content panel showing Arabic markdown for any clicked chunk
- Endpoints: `GET /explorer/index`, `GET /explorer/page/{n}`, `GET /explorer/section/{id}/chunks`

### Observability
- Per-request Langfuse trace with spans for every graph node and LLM call
- Per-call timing logged at INFO: duration, model, prompt + completion tokens
- Phase timing in integration tests: navigation / generation / total
- Tracing never affects UX — all Langfuse calls are wrapped in try/except

### Provider flexibility
- `LOCAL_INFERENCE=true` → Ollama (any OpenAI-compatible local model)
- `LOCAL_INFERENCE=false` → OpenAI cloud (`OPENAI_MODEL` selects the model)
- `extra_body` (Ollama-specific: `num_ctx`, `think`) sent only on local path
- `max_completion_tokens` used for OpenAI; `max_tokens` used for Ollama

---

## LLM call budget per request (typical)

| Call | Node / function | max_tokens | num_ctx (Ollama) |
|---|---|---|---|
| `structured()` | `classify_and_normalize` | 300 | 4096 |
| `structured()` | `navigate_level` × N | 300 | 8192 |
| `complete()` | `generate_answer` | 4096 | 32768 |
| `complete()` | `generate_greeting` | 2048 | 32768 |

Typical depth: 2–4 navigate_level calls. Total calls: 3–5.

---

## Key design decisions

| Decision | Rationale |
|---|---|
| Tree traversal over vector search | Document is a regulatory standard with explicit hierarchical structure; section titles + hooks are precise enough for LLM selection without embeddings |
| `classify_and_normalize` merged node | Eliminates one full round-trip; two sequential steps in one structured call are reliable with no cross-field dependency risk (normalisation always runs regardless of intent) |
| `json_schema` for Ollama, `json_object` for OpenAI | Ollama needs schema enforcement; GPT models follow instruction-based JSON schemas reliably without strict enforcement overhead |
| `num_ctx` + `max_tokens` kept for both providers | `num_ctx` is Ollama-only (in `extra_body`), `max_completion_tokens`/`max_tokens` is standard — same parameters, provider-aware key names |
| `ContextVar` for Langfuse trace parent | Propagates automatically into `asyncio.to_thread` workers without touching any function signatures |
| Leaf content from markdown files | Plain text is cheaper in tokens than structured JSON; markdown preserves tables and lists which matter for accounting standards |
| Per-session graph + index load | Simple and safe; avoids shared mutable state between concurrent Chainlit sessions |

---

## Known limitations / not yet implemented

- No retry / rephrase on navigation failure (`rephrase_and_retry` node planned but not built)
- No multi-turn conversation memory — each message is independent
- `data/index.json` covers sections 1–9 only (208 pages); additional standards would require extending the index and re-running summary generation
- Explorer section overlays depend on `data/bbox_map.json` — 12 of 156 leaf sections have no bounding box data and are dimmed in the UI
- Langfuse tracing requires the self-hosted Docker stack to be running; silently disabled if keys are absent
