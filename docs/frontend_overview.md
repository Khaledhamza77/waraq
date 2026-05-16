# Frontend Overview

## Stack

| Layer | Choice |
|---|---|
| Framework | React 18 + TypeScript, built with Vite 7 |
| Styling | Tailwind CSS 3 (dark theme, HSL CSS variables) |
| State | Recoil |
| Chat protocol | `@chainlit/react-client` 0.2.2 — **all backend communication goes through Chainlit** |
| Markdown | react-markdown + remark-gfm + rehype-raw |
| Diagrams | Mermaid 11 |
| Charts | Plotly.js via react-plotly.js |

## Key Architectural Point

The frontend is **not** a plain REST API consumer. It uses `@chainlit/react-client`, which talks to a Chainlit server over **WebSocket** (socket.io). There are no direct HTTP calls to waraq except for one auth ping. All message sending, file uploading, and response streaming go through Chainlit's protocol.

## Network Contract

### 1. Custom auth ping
```
GET http://localhost:8000/custom-auth
Credentials: include (cookies)
Response: any 2xx → auth accepted, proceed to connect
```
Called once on app load in `App.tsx` before opening the WebSocket.

### 2. Chainlit WebSocket
```
Base URL: http://localhost:8000/chainlit
Client ID: webapp
Protocol: socket.io (WebSocket upgrade)
```
The `ChainlitContext.Provider` in `main.tsx` bootstraps the connection.

### 3. Message send (via Chainlit client hook)
```typescript
sendMessage(
  { name: "User", type: "user_message", output: string },
  fileAttachments?: Array<{ id: string }>
)
```

### 4. File upload (via Chainlit client hook)
```typescript
uploadFile(file: File, progressCallback?)
// Returns: Promise<{ id: string }>
// Accepted: .pdf only, max 20 MB
```
File IDs returned here are passed back as attachments in `sendMessage`.

### 5. Document links
Links of the form `/documents/{path}` in AI message markdown are intercepted and opened in a new tab at `http://localhost:8000/documents/{path}`. The backend must serve these if used.

## What the Backend Receives

Each user turn arrives in the Chainlit `@on_message` handler as a `cl.Message` with:
- `message.content` — the user's raw text
- `message.elements` — list of uploaded file elements (if any)

## What the Frontend Expects Back

### Message content
A `cl.Message` (or streamed updates to one) with `content` set to a **markdown string**. The frontend renders full markdown including:
- Bold, italic, tables, lists
- Mermaid fenced code blocks → rendered as interactive diagrams
- Links starting with `/documents/` → opened in new tab

### Elements (optional)
If the backend attaches a Chainlit element with Plotly data, `AIMessage.tsx` renders it as a chart. The element must expose `props.data` (Plotly traces) and optionally `props.layout`.

### Loading state
While processing, the frontend shows a spinner with the current `cl.Message.content` as status text. This means the backend can stream intermediate status strings ("جاري البحث...", "تحليل النص...") and the user sees live progress.

### Error state
If the Chainlit step has `isError=True`, the message bubble gets a red left-border treatment.

## Component Map

```
App.tsx                  — auth ping + Chainlit session bootstrap
└── Playground.tsx       — main chat container; owns inputValue, attachedFiles state
    ├── Shell.tsx        — dark background with gradient glows
    ├── TopBar.tsx       — header bar with title
    ├── WelcomeCard.tsx  — shown when no messages; contains 4 prompt suggestions
    │   └── PromptSuggestion.tsx
    ├── AIMessage.tsx    — AI bubble: spinner → Plotly chart or Markdown
    │   └── Message.tsx  — markdown renderer (Mermaid, links, code blocks)
    ├── UserMessage.tsx  — user bubble + attached file badges
    │   └── AttachedFiles.tsx
    ├── InputBar.tsx     — fixed bottom bar
    │   ├── FileUploader.tsx  — paperclip button → .pdf upload
    │   └── button.tsx        — SendButton / StopButton
    └── PoweredByFinaira.tsx  — fixed logo watermark
```

## Prompt Suggestions (hardcoded in Playground.tsx)

Four suggestions are shown on the welcome screen. These hit the same `sendMessage` path as typed queries — no special endpoint. They are:
1. ما هي الخصائص النوعية الأساسية للمعلومات المالية المفيدة؟
2. كيف يتم قياس المخزون وفق معايير المحاسبة المصرية؟
3. ما هي متطلبات قائمة المركز المالي وفق المعيار الأول؟
4. ما هو هدف معيار المحاسبة المصري رقم 2 الخاص بالمخزون؟

(These overlap exactly with the navigation test cases — good signal.)

## Ports & CORS

- Chainlit server must run on **port 8000**
- Custom auth and Chainlit both on the same origin → no CORS issues
- Frontend dev server (Vite) runs on a separate port (default 5173) → CORS headers needed on the backend during development

## Stage 7 Implementation Shape

Stage 7 is a **FastAPI application** (`app/server.py`) that mounts Chainlit internally. `app/chainlit_app.py` contains the Chainlit handlers. It:

1. Exposes `GET /custom-auth` — trivial passthrough
2. Hosts Chainlit at `/chainlit` — WebSocket + HTTP endpoints handled by Chainlit itself
3. Wires `@cl.on_message` to the waraq pipeline:
   - Stream status updates to the message while navigating
   - Call `graph.invoke(...)` → `generate_answer(...)` or `generate_greeting(...)`
   - Format response as markdown with citations appended
   - Send final `cl.Message`
4. Optionally handles `@cl.on_file_upload` if PDF upload is in scope

## Citation Rendering

`generate_answer` now returns `citations: list[dict]`. These must be formatted into markdown before sending back. Example:

```
**المصادر:**
- الفقرة 1 — الهدف (صفحات 55–56)
- تعريفات (صفحات 60–62)
```

Since links of the form `/documents/{path}` are intercepted by the frontend, page references could eventually link to served PDFs.
