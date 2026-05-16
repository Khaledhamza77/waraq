"""
Explorer API — serves the document explorer frontend.

Endpoints:
  GET /explorer/index                         → full index.json (section tree)
  GET /explorer/page/{page_num}               → PDF page rendered as PNG
  GET /explorer/section/{section_id}/chunks  → chunks + metadata from section_chunks.json
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

log = logging.getLogger(__name__)

try:
    import pymupdf as fitz  # pymupdf ≥ 1.24
except ImportError:
    import fitz  # type: ignore[no-redef]  # older pymupdf

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).parent.parent
_PDF_PATH           = _ROOT / "data" / "عينة_من_معايير_المحاسبة_المصرية_2020.pdf"
_INDEX_PATH         = _ROOT / "data" / "index.json"
_SECTION_CHUNKS_PATH = _ROOT / "data" / "section_chunks.json"

# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------
_pdf_doc:        fitz.Document | None = None
_index_data:     dict | None = None
_section_chunks: dict | None = None
_excluded_pages: set[int] | None = None

# In-memory page-image cache  {page_num: png_bytes}
_page_cache: dict[int, bytes] = {}

PAGE_ZOOM = 1.5  # render at 108 DPI (72 × 1.5)


def _get_pdf() -> fitz.Document:
    global _pdf_doc
    if _pdf_doc is None:
        if not _PDF_PATH.exists():
            raise FileNotFoundError(f"PDF not found: {_PDF_PATH}")
        _pdf_doc = fitz.open(str(_PDF_PATH))
    return _pdf_doc


def _get_index() -> dict:
    global _index_data
    if _index_data is None:
        _index_data = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
    return _index_data


def _collect_excluded_pages(sections: list) -> set[int]:
    """Recursively collect page numbers from sections titled 'فهرس ومقدمة'."""
    pages: set[int] = set()
    for section in sections:
        if section.get("title") == "فهرس ومقدمة":
            start = section.get("start_page")
            end = section.get("end_page")
            if start is not None and end is not None:
                pages.update(range(int(start), int(end) + 1))
        if "children" in section:
            pages |= _collect_excluded_pages(section["children"])
    return pages


def _get_excluded_pages() -> set[int]:
    global _excluded_pages
    if _excluded_pages is None:
        index = _get_index()
        _excluded_pages = _collect_excluded_pages(index.get("sections", []))
    return _excluded_pages


def _get_section_chunks() -> dict:
    global _section_chunks
    if _section_chunks is None:
        if not _SECTION_CHUNKS_PATH.exists():
            raise FileNotFoundError(
                f"section_chunks.json not found — run: python scripts/build_section_chunks.py"
            )
        _section_chunks = json.loads(_SECTION_CHUNKS_PATH.read_text(encoding="utf-8"))
    return _section_chunks


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/explorer", tags=["explorer"])


@router.get("/index")
async def explorer_index() -> Any:
    """Return the full index.json section tree."""
    try:
        return _get_index()
    except FileNotFoundError as e:
        log.error("index.json missing: %s", e)
        raise HTTPException(status_code=503, detail="Document index not available")


@router.get("/page/{page_num}")
async def explorer_page(page_num: int) -> Response:
    """Render a single PDF page as PNG (1-indexed)."""
    if page_num in _page_cache:
        return Response(content=_page_cache[page_num], media_type="image/png")

    try:
        doc = _get_pdf()
    except FileNotFoundError as e:
        log.error("PDF missing: %s", e)
        raise HTTPException(status_code=503, detail="PDF document not available")

    if page_num < 1 or page_num > len(doc):
        raise HTTPException(status_code=404, detail=f"Page {page_num} not in document")

    page = doc[page_num - 1]  # pymupdf is 0-indexed
    mat = fitz.Matrix(PAGE_ZOOM, PAGE_ZOOM)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img_bytes = pix.tobytes("png")

    _page_cache[page_num] = img_bytes
    return Response(
        content=img_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/sections")
async def explorer_sections() -> list[str]:
    """Return list of section IDs that have chunk data in section_chunks.json."""
    try:
        return list(_get_section_chunks().keys())
    except FileNotFoundError:
        return []


@router.get("/section/{section_id}/chunks")
async def explorer_section_chunks(section_id: str) -> Any:
    """Return all chunks (with bbox + markdown) for a section."""
    try:
        chunks_map = _get_section_chunks()
    except FileNotFoundError as e:
        log.error("section_chunks.json missing: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Section chunks not available — run: python scripts/build_section_chunks.py",
        )
    if section_id not in chunks_map:
        raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found")

    section_data = chunks_map[section_id]
    excluded = _get_excluded_pages()

    def _is_visible(chunk: dict) -> bool:
        if chunk.get("page") in excluded:
            return False
        # Drop gazette running-header that repeats on every page
        if "الوقائع المصرية" in chunk.get("markdown", ""):
            return False
        return True

    filtered_chunks = [c for c in section_data.get("chunks", []) if _is_visible(c)]
    return {**section_data, "chunks": filtered_chunks}
