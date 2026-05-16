import logging
import os
from contextvars import ContextVar, Token
from typing import Any

log = logging.getLogger(__name__)

_langfuse = None
_disabled = False

# Holds the current Langfuse trace/span for the active request.
# asyncio.to_thread() copies the context to the worker thread automatically (Python 3.7+).
_trace_parent: ContextVar[Any] = ContextVar("langfuse_trace_parent", default=None)


def set_trace_parent(parent: Any) -> "Token[Any]":
    """Set the Langfuse parent for the current async context. Returns a reset token."""
    return _trace_parent.set(parent)


def reset_trace_parent(token: "Token[Any]") -> None:
    """Restore the previous Langfuse parent (call in finally)."""
    _trace_parent.reset(token)


def get_langfuse():
    """Return the shared Langfuse instance, or None if keys are missing / import fails."""
    global _langfuse, _disabled
    if _disabled:
        return None
    if _langfuse is not None:
        return _langfuse
    try:
        from langfuse import Langfuse  # noqa: PLC0415

        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
        if not public_key or not secret_key:
            log.warning("tracer: LANGFUSE keys not set — tracing disabled")
            _disabled = True
            return None

        host = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
        _langfuse = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        log.info("tracer: Langfuse tracing enabled → %s", host)
    except ImportError:
        log.warning("tracer: langfuse package not installed — tracing disabled")
        _disabled = True
    except Exception:
        log.exception("tracer: Langfuse init failed — tracing disabled")
        _disabled = True

    return _langfuse


def safe_span(
    parent: Any,
    name: str,
    input: dict[str, Any] | None = None,
    output: dict[str, Any] | None = None,
) -> Any:
    """Create a span on *parent* (trace or span). Returns None on failure.

    If *output* is provided the span is immediately closed.
    """
    if parent is None:
        return None
    try:
        span = parent.span(name=name, input=input or {})
        if output is not None:
            span.end(output=output)
        return span
    except Exception:
        log.exception("tracer: span '%s' creation failed", name)
        return None


def safe_end(span: Any, output: dict[str, Any] | None = None) -> None:
    """End a span. No-op if span is None."""
    if span is None:
        return
    try:
        span.end(output=output or {})
    except Exception:
        log.exception("tracer: span end failed")


def safe_generation(
    name: str,
    model: str,
    messages: list[dict[str, str]],
    completion: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """Log a single LLM API call as a Langfuse generation attached to the current parent.

    No-op when tracing is disabled or no parent is set.
    """
    parent = _trace_parent.get()
    if parent is None:
        return
    try:
        parent.generation(
            name=name,
            model=model,
            input=messages,
            output=completion,
            usage={
                "input": prompt_tokens,
                "output": completion_tokens,
                "total": prompt_tokens + completion_tokens,
            },
        )
    except Exception:
        log.exception("tracer: generation '%s' failed", name)


def flush() -> None:
    """Flush pending Langfuse events. Safe to call even when tracing is disabled."""
    lf = _langfuse  # read without triggering init
    if lf is None:
        return
    try:
        lf.flush()
    except Exception:
        log.exception("tracer: flush failed")
