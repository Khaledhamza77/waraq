# waraq
Navigating Egypt's accounting standards and regulations with surgical precision. No embeddings and no guesswork.

An agentic RAG system for the Egyptian Accounting Standards Manual. Instead of vector search, a LangGraph agent navigates the document's hierarchical index level by level to locate the exact sections relevant to a query, then generates a grounded answer with citations that link back to the source pages.

---

## Architecture

```
User query
    │
    ▼
classify_and_normalize      ← intent detection + query normalization
    │
    ▼
navigate_level (loop)       ← LLM selects which child section to descend into
    │                          repeats until a leaf section is reached
    ▼
generate_answer             ← answer synthesized from leaf markdown + citations
```

**Stack:**
- **Backend** — Python, FastAPI, Chainlit (WebSocket chat), LangGraph
- **LLM** — Ollama (local, default: `qwen3:8b`) or OpenAI API
- **Ingestion** — LandingAI ADE for document OCR and object detection, PyMuPDF
- **Observability** — Langfuse (optional, self-hosted via Docker)
- **Frontend** — React + TypeScript + Vite, Chainlit React client

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- **For local inference:** [Ollama](https://ollama.com) running with a model pulled (e.g. `ollama pull qwen3:8b`)
- **For cloud inference:** an OpenAI API key
- **For ingestion only:** a [LandingAI](https://landing.ai) API key (`VISION_AGENT_API_KEY`)

---

## Setup

### 1. Clone and install Python dependencies

```bash
git clone <repo-url>
cd waraq

# with uv (recommended)
uv sync

# or with pip
pip install -e .
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your inference backend:

**Local (Ollama):**
```env
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen3:8b
LOCAL_INFERENCE=true
```

**Cloud (OpenAI):**
```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1
# Leave LOCAL_INFERENCE unset or set to false
```

Langfuse keys can be left blank to disable observability tracing.

### 3. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

---

## Running

Two processes must run simultaneously — the backend and the frontend.

### Backend

```bash
uvicorn app.server:app --host 0.0.0.0 --port 8000 --reload
```

Serves at `http://localhost:8000`. Chainlit WebSocket is mounted at `/chainlit`.

### Frontend

```bash
cd frontend
npm run dev
```

Serves at `http://localhost:5173`. Open this URL in your browser.

---

## Observability (optional)

Langfuse traces every query through the navigation graph. To run it locally:

```bash
docker compose up -d
```

Then open `http://localhost:3000`, create an account, generate API keys, and paste them into `.env`:

```env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
```

See [docs/langfuse_setup.md](docs/langfuse_setup.md) for details.

---

## Data & Ingestion

Pre-processed data is already committed under `data/`:

| Path | Contents |
|---|---|
| `data/index.json` | Hierarchical section index (the navigation tree) |
| `data/section_chunks.json` | Per-section text chunks with bounding boxes |
| `data/parsed/markdown/` | Per-page markdown extracted from the PDF |
| `data/bbox_map.json` | Chunk-to-page bounding box coordinates |

To re-run ingestion from a new PDF (requires `VISION_AGENT_API_KEY`):

```bash
python scripts/run_ingestion.py
```

Other scripts under `scripts/` handle individual pipeline steps (bbox assignment, markdown building, hook generation, etc.).

---

## Project Layout

```
waraq/
├── app/                    # FastAPI + Chainlit entry points
│   ├── server.py           # Root app, mounts Chainlit and explorer router
│   ├── chainlit_app.py     # Chat lifecycle (on_chat_start, on_message)
│   └── explorer_router.py  # REST endpoints for the document explorer
├── waraq/                  # Core Python package
│   ├── navigation/         # LangGraph graph, nodes, state, prompts
│   ├── generation/         # Answer + greeting generation
│   ├── llm/                # Ollama / OpenAI client abstraction
│   ├── ingestion/          # PDF ingestion pipeline
│   ├── index/              # Index loading utilities
│   └── observability/      # Langfuse tracer wrapper
├── frontend/               # React + TypeScript app
│   └── src/
│       ├── pages/          # LandingPage, ExplorerPage
│       └── components/     # Playground (chat UI), TopBar, AIMessage, etc.
├── data/                   # Processed document data (committed)
├── scripts/                # One-off ingestion and maintenance scripts
├── docs/                   # Setup guides and architecture notes
├── docker-compose.yml      # Langfuse + Postgres observability stack
└── pyproject.toml
```
