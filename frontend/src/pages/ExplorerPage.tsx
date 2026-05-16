import React, { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

// ─── Types ──────────────────────────────────────────────────────────────────

interface Box {
  top: number;
  bottom: number;
  left: number;
  right: number;
}

interface Chunk {
  chunk_id: string;
  page: number;
  box: Box;
  markdown: string;
  type: string;
}

interface SectionChunkData {
  title: string;
  hook: string;
  start_page: number;
  end_page: number;
  chunks: Chunk[];
}

interface Section {
  id: string;
  title: string;
  start_page?: number;
  end_page?: number;
  hook?: string;
  children?: Section[];
}

interface IndexData {
  document: { title: string; total_pages: number; language: string };
  sections: Section[];
}

// ─── Constants ──────────────────────────────────────────────────────────────

const API_BASE = "http://localhost:8000";
const FONT = "'Almarai', sans-serif";
const TOTAL_PAGES = 208;

// Color per top-level section id
const SEC_COLORS: Record<string, string> = {
  section_1: "#94A3B8",
  section_2: "#22D3EE",
  section_3: "#A78BFA",
  section_4: "#60A5FA",
  section_5: "#C084FC",
  section_6: "#34D399",
  section_7: "#FBBF24",
  section_8: "#F87171",
  section_9: "#4ADE80",
};

function sectionColor(id: string): string {
  const parts = id.split("_");
  const topKey = parts.slice(0, 2).join("_");
  return SEC_COLORS[topKey] ?? "#A78BFA";
}

// Stable empty array — avoids creating a new reference every render,
// which would defeat React.memo on PageView for pages with no chunks.
const EMPTY_CHUNKS: Chunk[] = [];

// ─── Sub-components ──────────────────────────────────────────────────────────

// Single page with optional bbox overlays
interface PageViewProps {
  pageNum: number;
  chunks: Chunk[];
  activeChunkId: string | null;
  color: string;
  onChunkClick: (chunk: Chunk) => void;
}

const PageView = React.memo(function PageView({
  pageNum,
  chunks,
  activeChunkId,
  color,
  onChunkClick,
}: PageViewProps) {
  return (
    <div
      id={`page-${pageNum}`}
      style={{
        position: "relative",
        width: "100%",
        maxWidth: 820,
        // US Letter (612×792 pt) — the actual PDF page size.
        // Keeps the container the right height while images are lazy-loading
        // so scrollIntoView lands on the correct page.
        aspectRatio: "612 / 792",
        margin: "0 auto 32px",
        boxShadow: "0 2px 20px rgba(0,0,0,0.6)",
        background: "#fff",
        borderRadius: 2,
      }}
    >
      {/* Page image — lazy loaded */}
      <img
        src={`${API_BASE}/explorer/page/${pageNum}`}
        loading="lazy"
        decoding="async"
        style={{ width: "100%", height: "auto", display: "block", borderRadius: 2 }}
        alt={`صفحة ${pageNum}`}
      />

      {/* Bbox overlays */}
      {chunks.length > 0 && (
        <div style={{ position: "absolute", inset: 0, borderRadius: 2 }}>
          {chunks.map((chunk) => {
            const isActive = activeChunkId === chunk.chunk_id;
            const w = (chunk.box.right - chunk.box.left) * 100;
            const h = (chunk.box.bottom - chunk.box.top) * 100;
            if (w <= 0 || h <= 0) return null;
            return (
              <BboxOverlay
                key={chunk.chunk_id}
                chunk={chunk}
                isActive={isActive}
                color={color}
                onChunkClick={onChunkClick}
              />
            );
          })}
        </div>
      )}

      {/* Page number label */}
      <div
        style={{
          position: "absolute",
          bottom: -22,
          left: "50%",
          transform: "translateX(-50%)",
          fontSize: 11,
          color: "#4A4F6E",
          fontFamily: FONT,
          userSelect: "none",
        }}
      >
        {pageNum}
      </div>
    </div>
  );
});

interface BboxOverlayProps {
  chunk: Chunk;
  isActive: boolean;
  color: string;
  onChunkClick: (chunk: Chunk) => void;
}

function BboxOverlay({ chunk, isActive, color, onChunkClick }: BboxOverlayProps) {
  const [hovered, setHovered] = useState(false);

  const left   = `${chunk.box.left * 100}%`;
  const top    = `${chunk.box.top * 100}%`;
  const width  = `${(chunk.box.right - chunk.box.left) * 100}%`;
  const height = `${(chunk.box.bottom - chunk.box.top) * 100}%`;

  let bg = `${color}18`;
  if (hovered) bg = `${color}30`;
  if (isActive) bg = `${color}45`;

  return (
    <div
      style={{
        position: "absolute",
        left, top, width, height,
        background: bg,
        border: `1.5px solid ${color}${isActive ? "cc" : "70"}`,
        borderRadius: 2,
        cursor: "pointer",
        transition: "background 0.12s, border-color 0.12s",
        boxSizing: "border-box",
      }}
      onClick={() => onChunkClick(chunk)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    />
  );
}

// ─── TOC ─────────────────────────────────────────────────────────────────────

interface TocNodeProps {
  section: Section;
  depth: number;
  selectedId: string | null;
  expandedIds: Set<string>;
  onSelect: (s: Section) => void;
  onToggle: (id: string) => void;
  bboxIds: Set<string>; // sections that have bbox chunk data
}

function TocNode({ section, depth, selectedId, expandedIds, onSelect, onToggle, bboxIds }: TocNodeProps) {
  const isSelected = selectedId === section.id;
  const isExpanded = expandedIds.has(section.id);
  const hasChildren = (section.children?.length ?? 0) > 0;
  const hasBbox = bboxIds.has(section.id);
  const color = sectionColor(section.id);

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          // In RTL the right side is the start (indent side); left is the end.
          padding: `5px ${14 + depth * 14}px 5px 12px`,
          cursor: "pointer",
          background: isSelected ? `${color}18` : "transparent",
          borderRight: isSelected ? `2px solid ${color}` : "2px solid transparent",
          color: isSelected ? color : "#C4C9E8",
          fontFamily: FONT,
          fontSize: depth === 0 ? 13 : 12,
          fontWeight: isSelected ? 700 : depth === 0 ? 600 : 400,
          lineHeight: 1.55,
          transition: "background 0.12s",
          userSelect: "none",
        }}
        onClick={() => {
          if (hasChildren) onToggle(section.id);
          onSelect(section);
        }}
        onMouseEnter={(e) => {
          if (!isSelected) e.currentTarget.style.background = "rgba(255,255,255,0.04)";
        }}
        onMouseLeave={(e) => {
          if (!isSelected) e.currentTarget.style.background = "transparent";
        }}
      >
        {/* Expand arrow — first flex item in RTL (appears on the right) */}
        {hasChildren ? (
          <span
            style={{
              fontSize: 9,
              minWidth: 10,
              display: "inline-block",
              transition: "transform 0.15s",
              transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
              color: "#6B7280",
              flexShrink: 0,
            }}
          >
            ▶
          </span>
        ) : (
          <span style={{ minWidth: 10, display: "inline-block", flexShrink: 0 }} />
        )}

        {/* Section title */}
        <span style={{ flex: 1, direction: "rtl", textAlign: "right" }}>
          {section.title}
        </span>

        {/* Page number + bbox dot — last flex item in RTL (appears on the left) */}
        <span
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            flexShrink: 0,
            fontSize: 10,
            color: isSelected ? color : "#4A4F6E",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {hasBbox && (
            <span
              style={{
                width: 5,
                height: 5,
                borderRadius: "50%",
                background: isSelected ? color : `${color}90`,
                display: "inline-block",
                flexShrink: 0,
              }}
            />
          )}
          {section.start_page !== undefined && section.start_page}
        </span>
      </div>

      {hasChildren && isExpanded &&
        section.children!.map((child) => (
          <TocNode
            key={child.id}
            section={child}
            depth={depth + 1}
            selectedId={selectedId}
            expandedIds={expandedIds}
            onSelect={onSelect}
            onToggle={onToggle}
            bboxIds={bboxIds}
          />
        ))}
    </div>
  );
}

// ─── Content Panel ───────────────────────────────────────────────────────────

interface ContentPanelProps {
  chunk: Chunk;
  color: string;
  onClose: () => void;
}

function ContentPanel({ chunk, color, onClose }: ContentPanelProps) {
  const TYPE_LABELS: Record<string, string> = {
    text: "نص",
    figure: "شكل",
    table: "جدول",
    attestation: "توثيق",
    heading: "عنوان",
  };

  return (
    <div
      style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        height: "42vh",
        background: "#080A14",
        borderTop: `1px solid ${color}50`,
        display: "flex",
        flexDirection: "column",
        zIndex: 200,
        boxShadow: `0 -6px 40px rgba(0,0,0,0.7), 0 -1px 0 ${color}30`,
        animation: "slideUp 0.2s ease-out",
      }}
    >
      {/* Panel header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          padding: "8px 20px",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          gap: 12,
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontFamily: FONT,
            fontSize: 11,
            color: color,
            background: `${color}18`,
            border: `1px solid ${color}40`,
            borderRadius: 4,
            padding: "2px 8px",
          }}
        >
          {TYPE_LABELS[chunk.type] ?? chunk.type}
        </span>
        <span style={{ fontFamily: FONT, fontSize: 11, color: "#4A4F6E" }}>
          صفحة {chunk.page}
        </span>
        <div style={{ flex: 1 }} />
        <button
          onClick={onClose}
          style={{
            background: "transparent",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 4,
            cursor: "pointer",
            color: "#6B7280",
            fontSize: 14,
            lineHeight: 1,
            padding: "3px 8px",
            fontFamily: FONT,
            transition: "color 0.15s, border-color 0.15s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = "#C4C9E8";
            e.currentTarget.style.borderColor = "rgba(255,255,255,0.25)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = "#6B7280";
            e.currentTarget.style.borderColor = "rgba(255,255,255,0.1)";
          }}
        >
          ✕
        </button>
      </div>

      {/* Content */}
      <div
        dir="rtl"
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "14px 24px 20px",
          fontFamily: FONT,
          fontSize: 13,
          lineHeight: 1.8,
          color: "#C4C9E8",
        }}
        className="prose prose-invert prose-sm max-w-none"
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
          {chunk.markdown}
        </ReactMarkdown>
      </div>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function ExplorerPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [indexData, setIndexData]           = useState<IndexData | null>(null);
  const [bboxIds, setBboxIds]               = useState<Set<string>>(new Set());
  const [selectedId, setSelectedId]         = useState<string | null>(null);
  const [sectionData, setSectionData]       = useState<SectionChunkData | null>(null);
  const [activeChunk, setActiveChunk]       = useState<Chunk | null>(null);
  const [expandedIds, setExpandedIds]       = useState<Set<string>>(new Set());
  const [loadingSection, setLoadingSection] = useState(false);
  const [error, setError]                   = useState<string | null>(null);

  // Fetch index on mount
  useEffect(() => {
    fetch(`${API_BASE}/explorer/index`)
      .then((r) => r.json())
      .then((data: IndexData) => setIndexData(data))
      .catch(() => setError("تعذّر تحميل فهرس الوثيقة"));
  }, []);

  // Fetch section IDs that have bbox chunk data
  useEffect(() => {
    fetch(`${API_BASE}/explorer/sections`)
      .then((r) => r.json())
      .then((ids: string[]) => setBboxIds(new Set(ids)))
      .catch(() => {}); // bbox data is optional — silent failure is fine
  }, []);

  // Chunk lookup: page → chunks[]
  const pageChunks = React.useMemo<Map<number, Chunk[]>>(() => {
    const map = new Map<number, Chunk[]>();
    if (!sectionData) return map;
    for (const c of sectionData.chunks) {
      const arr = map.get(c.page) ?? [];
      arr.push(c);
      map.set(c.page, arr);
    }
    return map;
  }, [sectionData]);

  const activeColor = selectedId ? sectionColor(selectedId) : "#A78BFA";

  const handleSectionSelect = useCallback(
    async (section: Section) => {
      // Deselect if same section clicked twice
      if (section.id === selectedId) {
        setSelectedId(null);
        setSectionData(null);
        setActiveChunk(null);
        return;
      }

      setSelectedId(section.id);
      setActiveChunk(null);
      setSectionData(null);
      setError(null);

      // Always navigate to the section's start_page from the index
      if (section.start_page !== undefined) {
        setTimeout(() => {
          document
            .getElementById(`page-${section.start_page}`)
            ?.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 80);
      }

      // Only fetch bbox chunks for sections that have them
      if (!bboxIds.has(section.id)) return;

      setLoadingSection(true);
      try {
        const res = await fetch(`${API_BASE}/explorer/section/${section.id}/chunks`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: SectionChunkData = await res.json();
        setSectionData(data);

        // If no start_page in index, fall back to first chunk page for navigation
        if (section.start_page === undefined && data.chunks.length > 0) {
          const firstPage = Math.min(...data.chunks.map((c) => c.page));
          setTimeout(() => {
            document
              .getElementById(`page-${firstPage}`)
              ?.scrollIntoView({ behavior: "smooth", block: "start" });
          }, 80);
        }
      } catch {
        setError("خطأ في تحميل بيانات القسم");
      } finally {
        setLoadingSection(false);
      }
    },
    [selectedId, bboxIds]
  );

  // Auto-open section + page when arriving from a citation link
  const citationHandled = useRef(false);
  useEffect(() => {
    if (citationHandled.current) return;
    if (!indexData || bboxIds.size === 0) return;

    const sectionId = searchParams.get("section");
    const page = parseInt(searchParams.get("page") ?? "", 10);
    if (!sectionId) return;

    citationHandled.current = true;

    function findSection(sections: Section[], id: string): Section | null {
      for (const s of sections) {
        if (s.id === id) return s;
        if (s.children) {
          const found = findSection(s.children, id);
          if (found) return found;
        }
      }
      return null;
    }

    function collectAncestorIds(sections: Section[], id: string, path: string[] = []): string[] {
      for (const s of sections) {
        if (s.id === id) return path;
        if (s.children) {
          const found = collectAncestorIds(s.children, id, [...path, s.id]);
          if (found.length) return found;
        }
      }
      return [];
    }

    const section = findSection(indexData.sections, sectionId);
    if (!section) return;

    const ancestors = collectAncestorIds(indexData.sections, sectionId);
    if (ancestors.length) setExpandedIds(new Set(ancestors));

    handleSectionSelect(section).then(() => {
      const targetPage = !isNaN(page) ? page : section.start_page;
      if (targetPage) {
        setTimeout(() => {
          document
            .getElementById(`page-${targetPage}`)
            ?.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 300);
      }
    });
  }, [indexData, bboxIds, searchParams, handleSectionSelect]);

  const handleToggle = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const totalPages = indexData?.document.total_pages ?? TOTAL_PAGES;

  return (
    <div
      dir="rtl"
      style={{
        backgroundColor: "#000000",
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        fontFamily: FONT,
        color: "#F0F2FF",
        overflow: "hidden",
      }}
    >
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div
        style={{
          height: 52,
          borderBottom: "1px solid rgba(255,255,255,0.07)",
          display: "flex",
          alignItems: "center",
          padding: "0 20px",
          gap: 16,
          flexShrink: 0,
          background: "rgba(0,0,0,0.6)",
          backdropFilter: "blur(12px)",
        }}
      >
        <span
          style={{ fontSize: 16, fontWeight: 700, letterSpacing: "0.02em", color: "#F0F2FF" }}
        >
          ورق
        </span>
        <span style={{ color: "#2A2D50", fontSize: 16 }}>|</span>
        <span style={{ fontSize: 13, color: "#6B7280" }}>
          {indexData?.document.title ?? "تصفح الوثيقة"}
        </span>

        <div style={{ flex: 1 }} />

        {/* Section info when selected */}
        {sectionData && !loadingSection && (
          <span style={{ fontSize: 12, color: activeColor, maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {sectionData.title}
          </span>
        )}
        {loadingSection && (
          <span style={{ fontSize: 12, color: "#4A4F6E" }}>جاري التحميل…</span>
        )}

        <button
          onClick={() => navigate("/app")}
          style={{
            fontFamily: FONT,
            fontSize: 12,
            fontWeight: 600,
            color: "rgba(255,255,255,0.4)",
            background: "transparent",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 6,
            padding: "5px 14px",
            cursor: "pointer",
            transition: "all 0.15s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = "#fff";
            e.currentTarget.style.borderColor = "rgba(255,255,255,0.25)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = "rgba(255,255,255,0.4)";
            e.currentTarget.style.borderColor = "rgba(255,255,255,0.1)";
          }}
        >
          المحادثة
        </button>
      </div>

      {/* ── Body (viewer + TOC) ─────────────────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Document Viewer — left */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "32px 24px",
            paddingBottom: activeChunk ? "calc(42vh + 32px)" : "32px",
            background: "#0A0C18",
          }}
        >
          {error && (
            <div style={{ textAlign: "center", color: "#F87171", fontSize: 13, padding: 24 }}>
              {error}
            </div>
          )}

          {Array.from({ length: totalPages }, (_, i) => i + 1).map((pageNum) => (
            <PageView
              key={pageNum}
              pageNum={pageNum}
              chunks={pageChunks.get(pageNum) ?? EMPTY_CHUNKS}
              activeChunkId={activeChunk?.chunk_id ?? null}
              color={activeColor}
              onChunkClick={setActiveChunk}
            />
          ))}
        </div>

        {/* TOC Panel — right */}
        <div
          style={{
            width: 290,
            flexShrink: 0,
            borderRight: "1px solid rgba(255,255,255,0.06)",
            overflowY: "auto",
            background: "#05070F",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div
            style={{
              padding: "14px 16px 10px",
              fontSize: 11,
              color: "#4A4F6E",
              fontWeight: 600,
              letterSpacing: "0.08em",
              borderBottom: "1px solid rgba(255,255,255,0.05)",
              flexShrink: 0,
            }}
          >
            فهرس المحتويات
          </div>

          {!indexData && (
            <div style={{ padding: 20, fontSize: 12, color: "#4A4F6E", textAlign: "center" }}>
              جاري التحميل…
            </div>
          )}

          {indexData && (
            <div style={{ flex: 1, paddingBottom: 24 }}>
              {indexData.sections.map((section) => (
                <TocNode
                  key={section.id}
                  section={section}
                  depth={0}
                  selectedId={selectedId}
                  expandedIds={expandedIds}
                  onSelect={handleSectionSelect}
                  onToggle={handleToggle}
                  bboxIds={bboxIds}
                />
              ))}
            </div>
          )}

          {/* Clear selection button */}
          {selectedId && (
            <div
              style={{
                padding: "10px 16px",
                borderTop: "1px solid rgba(255,255,255,0.05)",
                flexShrink: 0,
              }}
            >
              <button
                onClick={() => {
                  setSelectedId(null);
                  setSectionData(null);
                  setActiveChunk(null);
                }}
                style={{
                  width: "100%",
                  fontFamily: FONT,
                  fontSize: 12,
                  color: "#6B7280",
                  background: "transparent",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: 6,
                  padding: "6px 0",
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = "#C4C9E8";
                  e.currentTarget.style.borderColor = "rgba(255,255,255,0.2)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "#6B7280";
                  e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)";
                }}
              >
                إلغاء التحديد
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ── Content Panel (fixed bottom) ───────────────────────────────── */}
      {activeChunk && (
        <ContentPanel
          chunk={activeChunk}
          color={activeColor}
          onClose={() => setActiveChunk(null)}
        />
      )}

      <style>{`
        @keyframes slideUp {
          from { transform: translateY(100%); opacity: 0; }
          to   { transform: translateY(0);    opacity: 1; }
        }
      `}</style>
    </div>
  );
}
