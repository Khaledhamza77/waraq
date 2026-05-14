"""
Waraq — Chainlit application entry point (Stage 7).

Run:
    chainlit run chainlit_app.py --port 8000
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import chainlit as cl

from waraq.generation.responder import NOT_FOUND_ANSWER, generate_answer, generate_greeting
from waraq.navigation.graph import build_graph
from waraq.navigation.state import NavigationState
from waraq.observability.tracer import flush, get_langfuse, safe_end, safe_span

log = logging.getLogger(__name__)

# ── Data paths ────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).parent
_INDEX_PATH = _ROOT / "data" / "index.json"
_MARKDOWN_DIR = _ROOT / "data" / "parsed" / "markdown" / "pages"

# ── Node → Arabic status string ───────────────────────────────────────────────

_NODE_STATUS: dict[str, str] = {
    "check_intent": "جاري تحليل نية السؤال...",
    "normalize_query": "جاري توحيد صياغة السؤال...",
}


def _nav_status(level: int) -> str:
    return f"جاري التنقل في المعايير (المستوى {level})..."


# ── Markdown formatting ────────────────────────────────────────────────────────

def _format_response(answer: str, citations: list[dict]) -> str:
    parts = [answer]
    if citations:
        parts.append("\n---\n**المصادر:**")
        for cit in citations:
            pages = cit.get("pages", {})
            start, end = pages.get("start", "?"), pages.get("end", "?")
            title = cit.get("title", "")
            page_ref = f"صفحة {start}" if start == end else f"صفحات {start}–{end}"
            parts.append(f"- {title} ({page_ref})")
    return "\n".join(parts)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _span_output_from_updates(updates: dict[str, Any]) -> dict[str, Any]:
    """Build Langfuse span output from a node's state updates, omitting heavy fields."""
    return {k: v for k, v in updates.items() if k not in ("leaf_content",)}


# ── Chainlit lifecycle ────────────────────────────────────────────────────────

@cl.on_chat_start
async def on_chat_start() -> None:
    index = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
    graph = build_graph()
    config: dict[str, Any] = {
        "configurable": {"index": index, "markdown_dir": _MARKDOWN_DIR},
    }
    cl.user_session.set("graph", graph)
    cl.user_session.set("config", config)
    log.info("Chat session started — graph and index loaded.")


@cl.on_message
async def on_message(message: cl.Message) -> None:
    graph = cl.user_session.get("graph")
    config = cl.user_session.get("config")
    query: str = message.content.strip()

    # ── Langfuse trace ────────────────────────────────────────────────────────
    lf = get_langfuse()
    trace = None
    if lf:
        try:
            trace = lf.trace(name="waraq_query", input={"query": query})
        except Exception:
            log.exception("Langfuse trace init failed")

    # ── Initial Chainlit status bubble ────────────────────────────────────────
    msg = cl.Message(content=_NODE_STATUS["check_intent"])
    await msg.send()

    # ── Build initial NavigationState ─────────────────────────────────────────
    initial: NavigationState = {
        "original_query": query,
        "query": "",
        "language": "",
        "intent": "",
        "navigation_path": [],
        "leaf_content": "",
        "leaf_metadata": [],
        "status": "",
    }

    # ── Stream through the graph, one node at a time ──────────────────────────
    nav: dict[str, Any] = dict(initial)
    nav_level = 0

    try:
        async for chunk in graph.astream(initial, config=config, stream_mode="updates"):
            node_name: str = next(iter(chunk))
            updates: dict[str, Any] = chunk[node_name]
            nav.update(updates)

            # Update Chainlit status
            if node_name == "navigate_level":
                nav_level += 1
                status_text = _nav_status(nav_level)
            else:
                status_text = _NODE_STATUS.get(node_name, f"جاري تنفيذ {node_name}...")
            msg.content = status_text
            await msg.update()

            # Langfuse span for this node
            if trace:
                try:
                    span_name = (
                        f"navigate_level_{nav_level}"
                        if node_name == "navigate_level"
                        else node_name
                    )
                    safe_span(
                        trace,
                        name=span_name,
                        input={
                            "query": nav.get("query") or query,
                            "navigation_path": nav.get("navigation_path", []),
                        },
                        output=_span_output_from_updates(updates),
                    )
                except Exception:
                    log.exception("Langfuse span failed for node '%s'", node_name)

    except Exception:
        log.exception("graph.astream failed")
        msg.content = "حدث خطأ أثناء معالجة سؤالك. يُرجى المحاولة مرة أخرى."
        await msg.update()
        if trace:
            try:
                trace.update(output={"error": "graph_stream_failed"})
            except Exception:
                pass
        flush()
        return

    # ── Generate response based on navigation status ──────────────────────────
    pipeline_status: str = nav.get("status", "")
    final_content: str = ""

    if pipeline_status == "found":
        msg.content = "جاري صياغة الإجابة..."
        await msg.update()

        gen_span = safe_span(
            trace,
            name="generate_answer",
            input={
                "query": nav["query"],
                "sources": [m["title"] for m in nav.get("leaf_metadata", [])],
                "content_chars": len(nav.get("leaf_content", "")),
                "leaf_count": len(nav.get("leaf_metadata", [])),
            },
        )

        response: dict[str, Any] = await asyncio.to_thread(
            generate_answer,
            query=nav["query"],
            leaf_content=nav["leaf_content"],
            leaf_metadata=nav["leaf_metadata"],
        )

        safe_end(
            gen_span,
            output={
                "answer_chars": len(response.get("answer", "")),
                "citations": response.get("citations", []),
            },
        )

        answer_text = response.get("answer") or NOT_FOUND_ANSWER
        final_content = _format_response(answer_text, response.get("citations", []))

    elif pipeline_status == "greeting":
        msg.content = "جاري الرد..."
        await msg.update()

        greet_span = safe_span(
            trace,
            name="generate_greeting",
            input={"query": query},
        )

        greeting_text: str = await asyncio.to_thread(generate_greeting, query)

        safe_end(greet_span, output={"answer_chars": len(greeting_text)})
        final_content = greeting_text

    elif pipeline_status == "not_found":
        final_content = NOT_FOUND_ANSWER

    else:  # rejected or unexpected
        final_content = (
            "لا يمكنني الإجابة على هذا السؤال. "
            "يُرجى طرح سؤال يتعلق بمعايير المحاسبة المصرية."
        )

    # ── Send final message ────────────────────────────────────────────────────
    msg.content = final_content
    await msg.update()

    # ── Close Langfuse trace ──────────────────────────────────────────────────
    if trace:
        try:
            trace.update(
                output={
                    "status": pipeline_status,
                    "navigation_path": nav.get("navigation_path", []),
                    "navigation_levels": nav_level,
                    "answer_chars": len(final_content),
                }
            )
        except Exception:
            log.exception("Langfuse trace update failed")
    flush()
