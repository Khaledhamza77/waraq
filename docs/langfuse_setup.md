# Langfuse Setup Guide

Langfuse is the observability backend for waraq. Every query produces a full trace in the Langfuse UI showing the navigation path, each LLM call (with prompt, completion, and token counts), and the final response.

---

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- The waraq `.env` file (copy `.env.example` → `.env`)

---

## 1 — Create data directories

The docker-compose bind-mounts require these to exist before first start:

```bash
mkdir -p data/postgres data/langfuse
```

---

## 2 — Start the stack

```bash
docker compose up -d
```

Wait ~20 seconds for postgres to initialise and Langfuse to apply its schema migrations. Check health:

```bash
docker compose ps          # both services should show "healthy" / "running"
docker compose logs langfuse --tail 30
```

Langfuse is ready when the logs show `✓ Langfuse server started`.

---

## 3 — Create an account and project

1. Open [http://localhost:3000](http://localhost:3000) in a browser.
2. Click **Sign up** → create a local admin account (any email/password; no verification).
3. After login, create a new **organization** and **project** (e.g. `waraq`).
4. In the project sidebar go to **Settings → API Keys → Create new key**.
5. Copy the **Public Key** and **Secret Key**.

---

## 4 — Add keys to `.env`

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
```

The waraq backend reads these at startup. Restart `uvicorn app.server:app` after editing.

---

## 5 — Verify a trace

Send any query through the Chainlit frontend, then open [http://localhost:3000](http://localhost:3000) → your project → **Traces**. You should see one trace named `waraq_query` containing:

```
trace: waraq_query  {input: {query: "..."}}
  ├── span: normalize_query
  ├── span: check_intent
  │     └── generation: structured  {model, prompt_tokens, completion_tokens}
  ├── span: navigate_level_1
  │     └── generation: structured  {model, prompt_tokens, completion_tokens}
  ├── span: navigate_level_N
  │     └── generation: structured  {model, prompt_tokens, completion_tokens}
  └── span: generate_answer
        └── generation: structured  {model, prompt_tokens, completion_tokens}
  [output: {status, navigation_path, answer_chars}]
```

If tracing is working you will see `tracer: Langfuse tracing enabled → http://localhost:3000` in the waraq backend logs at startup.

If the keys are missing or wrong, waraq logs `tracer: LANGFUSE keys not set — tracing disabled` and continues normally with no UI impact.

---

## 6 — Stop the stack

```bash
docker compose down        # stops containers, data persists
docker compose down -v     # stops + deletes volumes (wipes all trace data)
```

---

## Troubleshooting

| Symptom | Check |
|---|---|
| `docker compose ps` shows langfuse not healthy | `docker compose logs langfuse` — usually postgres not ready yet; wait 30 s and retry |
| No traces appear after a query | Confirm `.env` keys match what Langfuse shows; confirm `chainlit run` was restarted after editing `.env` |
| `NEXTAUTH_SECRET` / `SALT` warnings | Fine for local dev; change them if you ever expose Langfuse beyond localhost |
| Port 3000 already in use | Edit `docker-compose.yml` `ports:` from `"3000:3000"` to e.g. `"3001:3000"` and update `LANGFUSE_HOST` |
