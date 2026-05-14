# waraq — Project Plan
> Navigating Egypt's accounting standards and regulations with surgical precision. No embeddings and no guesswork..

---

## Project Overview

**waraq** is an agentic Arabic document navigation system built for Egyptian accounting regulation. It uses hierarchical index traversal powered by SILMA-9B to navigate a structured regulatory document and return precise, cited answers without embeddings or vector search.

**Stack:** Python · FastAPI · LangGraph · Ollama · SILMA-9B · LandingAI ADE · Langfuse · uv

---

## Repository Structure

```
waraq/
├── data/
│   ├── raw/                    # original PDF
│   ├── parsed/                 # Landing AI raw JSON output
│   └── index.json              # master document index (hand-mapped + enriched)
├── waraq/
│   ├── ingestion/
│   │   └── parser.py           # Stage 1: Landing AI ingestion pipeline
│   ├── index/
│   │   └── builder.py          # Stage 4: summary generation, index enrichment
│   ├── navigation/
│   │   ├── graph.py            # Stage 5: LangGraph navigation system
│   │   ├── nodes.py            # individual graph nodes
│   │   └── prompts.py          # all prompts in one place
│   ├── generation/
│   │   └── responder.py        # Stage 6: final answer generation
│   ├── llm/
│   │   └── client.py           # shared Ollama client, structured output helpers
│   ├── observability/
│   │   └── tracer.py           # Stage 8: Langfuse integration
│   └── api/
│       ├── main.py             # Stage 7: FastAPI app
│       └── schemas.py          # request/response models
├── scripts/
│   ├── run_ingestion.py        # one-shot: parse PDF → save JSON
│   ├── run_summary_gen.py      # one-shot: enrich index.json with summaries
│   └── test_llm.py             # Stage 3 smoke test
├── tests/
│   └── test_navigation.py      # Stage 5 smoke tests
├── pyproject.toml              # uv project file
├── .env.example
└── README.md
```

---

## index.json Schema (Stage 2 — Human-authored)

This is the master document. Every other stage reads from or writes to this file. You author the skeleton; the summary generation stage enriches it in-place.

```json
{
  "document": {
    "title": "...",
    "total_pages": 245,
    "language": "ar"
  },
  "sections": [
    {
      "id": "intro",
      "title": "المقدمة",
      "type": "introduction",
      "hook": null,
      "children": [
        {
          "id": "intro_introduction",
          "title": "مقدمة",
          "type": "leaf",
          "pages": { "start": 1, "end": 3 },
          "hook": null,
          "chunk_ids": []
        },
        {
          "id": "intro_preface",
          "title": "ديباجة",
          "type": "leaf",
          "pages": { "start": 4, "end": 6 },
          "hook": null,
          "chunk_ids": []
        },
        {
          "id": "intro_preface_appendix",
          "title": "ملحق الديباجة",
          "type": "leaf",
          "pages": { "start": 7, "end": 9 },
          "hook": null,
          "chunk_ids": []
        }
      ]
    },
    {
      "id": "frameworks",
      "title": "الأطر",
      "type": "frameworks",
      "hook": null,
      "children": [
        {
          "id": "framework_1",
          "title": "الإطار الأول: ...",
          "type": "part",
          "hook": null,
          "children": [
            {
              "id": "framework_1_para_1",
              "title": "الفقرة 1.1",
              "type": "leaf",
              "pages": { "start": 10, "end": 12 },
              "hook": null,
              "chunk_ids": []
            }
          ]
        }
      ]
    },
    {
      "id": "regulatory",
      "title": "المعايير التنظيمية",
      "type": "regulatory",
      "hook": null,
      "children": [
        {
          "id": "criterion_1",
          "title": "المعيار الأول: ...",
          "type": "criterion",
          "hook": null,
          "children": [
            {
              "id": "criterion_1_para_1",
              "title": "الفقرة 1.1",
              "type": "leaf",
              "pages": { "start": 80, "end": 82 },
              "hook": null,
              "chunk_ids": []
            }
          ]
        }
      ]
    }
  ]
}
```

**Rules:**
- `hook` is `null` until Stage 4 fills it in
- `chunk_ids` are `null` until Stage 1 output is cross-referenced
- `type: "leaf"` nodes are the retrieval units — navigation always terminates here
- Page ranges are inclusive

---

## Stage 1 — Ingestion Pipeline

**Goal:** Parse the PDF using Landing AI ADE and save the full structured output to disk as a reusable checkpoint.

**Definition of done:** `data/parsed/output.json` exists and contains all chunks for all 245 pages with chunk types, text, page numbers, and bounding boxes.

**Implementation notes:**
- Use the async Parse Jobs API (`parse_jobs.create`) — send the full PDF in one call, Landing AI handles splitting internally
- Poll until complete, then save the full response JSON to `data/parsed/output.json`
- Log total chunks, pages processed, and any failed pages
- This script runs once. If `output.json` already exists, skip and exit early (idempotent)

**Key fields to verify in output:**
- `chunk_type` — heading, paragraph, table, figure, etc.
- `text` — the actual content
- `page` — page number (verify 1-indexed vs 0-indexed)
- `grounding` — bounding box coordinates (carry these through, needed for Stage 9)

**File:** `scripts/run_ingestion.py`

---

## Stage 2 — Document Mapping

**Goal:** Produce the hand-authored `data/index.json` following the schema above.

**This stage is done entirely by the human.** No code needed.

**Inputs:** Knowledge of document structure + `data/parsed/output.json` to verify page numbers and identify `chunk_ids` for each leaf node.

**Definition of done:** `data/index.json` exists, all `pages` fields are filled, all `hook` fields are `null`, structure matches document exactly.

---

## Stage 3 — SILMA-9B via Ollama

**Goal:** SILMA-9B is running locally via Ollama, serving an OpenAI-compatible endpoint, and responding correctly to a test prompt with structured JSON output.

**Definition of done:** A test script hits the Ollama endpoint, sends a simple Arabic prompt requesting JSON output, and receives a valid parsed JSON response.

**Setup:**

Ollama must be installed and the model pulled before running anything:
```bash
ollama pull <model-name>   # run: ollama list, to confirm the exact name
ollama serve               # starts the server on http://localhost:11434
```

No extra Python dependencies are needed — the existing `openai` package points to Ollama's OpenAI-compatible endpoint at `http://localhost:11434/v1`.

**Client wrapper** (`waraq/llm/client.py`):
- Wraps the OpenAI-compatible client pointed at `LLM_BASE_URL` (default `http://localhost:11434/v1`)
- Exposes two methods:
  - `complete(prompt, system, temperature) → str` — free text generation
  - `structured(prompt, system, schema) → dict` — uses Ollama's `response_format` with `json_schema` to enforce JSON output; falls back to `json_object` mode when no schema is given
- All prompts go through this client — no direct API calls elsewhere in the codebase
- `schema` accepts a Pydantic model class or a raw JSON schema dict

**Environment variables:**
```bash
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=<your-ollama-model-name>   # e.g. silma-v1, qwen3:8b
```

---

## Stage 4 — Summary Generation (Bottom-Up)

**Goal:** Enrich every `hook` field in `index.json` with a SILMA-generated Arabic summary that answers *"what regulatory questions does this node answer?"*

**Definition of done:** All `hook` fields in `index.json` are non-null Arabic strings. The file is valid JSON. A spot-check of 5 hooks reads as accurate and query-relevant.

**Algorithm:**

```
for each leaf node:
    content = extract text from parsed chunks for node's page range
    hook = llm.complete(summarize_leaf_prompt(node.title, content))
    node.hook = hook

for each non-leaf node (bottom-up, children before parents):
    child_hooks = [child.hook for child in node.children]
    hook = llm.complete(rollup_prompt(node.title, child_hooks))
    node.hook = hook

save index.json
```

**Prompts** (`waraq/navigation/prompts.py`):

`summarize_leaf_prompt`:
> أنت محلل قانوني متخصص في اللوائح المصرفية المصرية. بناءً على النص التالي من وثيقة تنظيمية، اكتب فقرة واحدة موجزة تصف: ما هي الأسئلة التنظيمية التي يجيب عليها هذا القسم؟ ما هي الالتزامات أو المعايير أو المفاهيم التي يغطيها؟

`rollup_prompt`:
> بناءً على ملخصات الأقسام الفرعية التالية، اكتب ملخصاً موحداً للقسم الرئيسي يصف نطاقه التنظيمي الكامل.

**File:** `scripts/run_summary_gen.py`

**Note:** This script is also idempotent — skip any node where `hook` is already non-null. Allows resuming if interrupted.

---

## Stage 5 — LangGraph Navigation System

**Goal:** A LangGraph graph that takes a user query, navigates the index hierarchy to the most relevant leaf node, and returns the leaf content + node metadata. Max 1 retry with query rephrasing.

**Definition of done:** Given 5 known test queries, the graph returns the correct leaf node for each. Given an out-of-domain query, it returns a rejection. Given an unanswerable in-domain query, it returns "not found" after retry.

### Graph State

```python
class NavigationState(TypedDict):
    original_query: str
    query: str                    # normalized/translated working query
    language: str                 # detected: "ar" or "en"
    intent: str                   # "valid" | "invalid"
    current_node_ids: list[str]   # candidates at current navigation level
    navigation_path: list[str]    # trail of selected node ids
    leaf_content: str             # markdown content of final leaf
    leaf_metadata: dict           # id, title, pages, chunk_ids
    retry_count: int
    status: str                   # "navigating" | "found" | "not_found" | "rejected"
```

### Graph Nodes

**`normalize_query`**
- Detects language (simple heuristic: Arabic unicode range check)
- If English: translate to Arabic using the LLM
- Normalize: strip ambiguity, ensure formal Arabic phrasing
- Output: `state.query` set, `state.language` set

**`check_intent`**
- Single LLM structured output call
- Schema: `{"intent": "valid" | "invalid", "reason": "string"}`
- System prompt enforces: this system answers questions about Egyptian accounting standards only. Document clarification and standards interpretation are valid. Everything else is invalid.
- If invalid: set `state.status = "rejected"`, route to END

**`navigate_level`**
- The core node. Called repeatedly as the graph traverses levels.
- Takes current level's candidate nodes from index, formats their hooks as a numbered list
- LLM structured output call: `{"selected_ids": ["id1"], "confidence": "high|low"}`
- If top-level: candidates are the root sections
- If mid-level: candidates are children of previously selected node
- If leaf reached: set `state.leaf_content`, `state.leaf_metadata`, `state.status = "found"`, route to END
- If confidence is low and `retry_count < 1`: route to `rephrase_and_retry`
- If confidence is low and `retry_count >= 1`: set `state.status = "not_found"`, route to END

**`rephrase_and_retry`**
- LLM call: given the original query and the available section hooks, rephrase the query to be more specific and aligned with the document's terminology
- Increment `state.retry_count`
- Reset navigation path, route back to `navigate_level` from top

### Graph Edges

```
START
  → normalize_query
  → check_intent
  → [rejected → END] | [valid → navigate_level]
  → [found → END] | [not_found → END] | [low confidence + retry → rephrase_and_retry]
  → rephrase_and_retry → navigate_level (from top)
```

**File:** `waraq/navigation/graph.py`, `waraq/navigation/nodes.py`

---

## Stage 6 — Response Generation

**Goal:** Take the leaf content returned by the navigation graph and generate a final Arabic answer with citation.

**Definition of done:** Response is in Arabic, directly answers the query, cites the specific paragraph/article by name and page number, stays strictly within the retrieved content (no hallucination beyond source).

**Implementation:**

Single LLM call via `llm.client.complete()`:

System prompt:
> أنت مساعد قانوني متخصص في اللوائح المصرفية المصرية. مهمتك الإجابة على أسئلة المستخدمين بدقة واحترافية بناءً حصراً على النص التنظيمي المقدم إليك. يجب أن تتضمن إجابتك دائماً مرجعاً صريحاً للفقرة أو المادة والصفحات التي استندت إليها. لا تضف أي معلومات خارج النص المقدم.

User prompt includes:
- The normalized query
- The leaf node title + page range (as citation anchor)
- The full leaf markdown content

Response format (structured):
```json
{
  "answer": "النص العربي للإجابة...",
  "citation": {
    "node_id": "criterion_1_para_1",
    "title": "الفقرة 1.1 — المعيار الأول",
    "pages": { "start": 80, "end": 82 }
  }
}
```

**File:** `waraq/generation/responder.py`

---

## Stage 7 — FastAPI + Frontend Integration

**Goal:** A running FastAPI backend that the frontend can query and receive answers from.

**Definition of done:** Frontend sends a query and receives a structured response. End-to-end flow works in a browser.

**Step 1 — Assess frontend:**
Inspect the existing frontend code. Document exactly: what endpoint it calls, what request schema it sends, what response schema it expects. Define the API contract from this.

**Step 2 — Build API:**

Single endpoint:
```
POST /query
```

Request:
```json
{ "query": "string" }
```

Response:
```json
{
  "answer": "string",
  "citation": {
    "node_id": "string",
    "title": "string",
    "pages": { "start": 0, "end": 0 }
  },
  "navigation_path": ["string"],
  "status": "found | not_found | rejected",
  "language_detected": "ar | en"
}
```

**Step 3 — CORS + startup:**
- CORS configured for frontend origin
- On startup: load `index.json` into memory once, initialize LangGraph, initialize LLM client
- Health check endpoint: `GET /health`

**File:** `waraq/api/main.py`, `waraq/api/schemas.py`

---

## Stage 8 — Langfuse Observability

**Goal:** Every query is fully traced in Langfuse — from raw input to final answer — with all intermediate LLM calls visible.

**Definition of done:** A query sent through the API appears in the local Langfuse dashboard as a full trace with spans for: normalize, intent check, each navigation step, rephrasing (if triggered), and response generation.

**Implementation:**
- Wrap `llm.client.complete()` and `llm.client.structured()` to automatically create Langfuse spans
- Each span captures: prompt, response, model, latency, token counts
- Top-level trace captures: original query, final status, navigation path, total latency
- Use `LANGFUSE_HOST=http://localhost:3000` in `.env`

**File:** `waraq/observability/tracer.py`

---

## Stage 9 — Bounding Box Visualization (Optional)

**Goal:** Alongside the answer, the frontend can optionally display the source page(s) with bounding boxes highlighting the exact chunks the answer came from.

**Definition of done:** Frontend receives bounding box data, renders the PDF page as an image, and draws highlight rectangles over the relevant chunks.

**Implementation notes:**
- Bounding box data is already captured in Stage 1 from Landing AI's `grounding` field per chunk
- `chunk_ids` in the leaf node index entry map directly to chunks in `parsed/output.json`
- API response extended with:
```json
{
  "visualization": {
    "page": 80,
    "bounding_boxes": [
      { "x": 0.1, "y": 0.2, "width": 0.8, "height": 0.05 }
    ]
  }
}
```
- Backend renders the PDF page to an image (using `pymupdf`) and returns it as base64, or returns raw coordinates and lets the frontend render against a PDF viewer

---

## Environment Variables

```bash
# .env.example
VISION_AGENT_API_KEY=
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=silma-v1
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=http://localhost:3000
```

---

## Definition of Done — Full Project

- [ ] `data/parsed/output.json` exists with all pages parsed
- [ ] `data/index.json` exists with full structure, all hooks filled, all page ranges accurate
- [ ] Ollama serving the model at `localhost:11434`, health check passing
- [ ] 5 known test queries return correct leaf nodes via navigation graph
- [ ] Out-of-domain query returns rejection response
- [ ] End-to-end query through FastAPI returns Arabic answer with citation
- [ ] Frontend connected and rendering responses
- [ ] All traces visible in local Langfuse dashboard

---

## Development Order

Build and validate each stage before starting the next. Do not parallelize — each stage is a dependency of the next.

```
Stage 1 → Stage 2 → Stage 3 → Stage 4 → Stage 5 → Stage 6 → Stage 7 → Stage 8 → Stage 9
```

Exception: Stage 1 (ingestion) can run in the background while Stage 2 (manual mapping) is being authored.
