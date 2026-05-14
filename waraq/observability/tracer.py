import logging
import os
from typing import Any

log = logging.getLogger(__name__)

_langfuse = None
_disabled = False


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


def flush() -> None:
    """Flush pending Langfuse events. Safe to call even when tracing is disabled."""
    lf = _langfuse  # read without triggering init
    if lf is None:
        return
    try:
        lf.flush()
    except Exception:
        log.exception("tracer: flush failed")
