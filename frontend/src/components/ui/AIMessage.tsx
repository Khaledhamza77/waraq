import * as React from "react";
import { Message, type MessageProps } from "./Message";
import { cn } from "@/lib/utils";
import { SyncLoader } from "react-spinners";
import Plot from "react-plotly.js";
import { ChevronDown } from "lucide-react";
import { useNavigate } from "react-router-dom";

export interface AIMessageProps extends Omit<
  MessageProps,
  "align" | "bubbleClassName"
> {
  isError: boolean;
  isLoading?: boolean;
  className?: string;
  bubbleClassName?: string;
  children?: React.ReactNode;
  elements?: any[];
}

const CITE_SEP = "\n---\n**المصادر:**";

interface Citation {
  label: string;
  href: string | null;
}

function parseCitations(raw: string): Citation[] {
  return raw
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.startsWith("- "))
    .map((l) => {
      const body = l.slice(2);
      // Find a markdown link anywhere in the line — no anchors so whitespace/RTL markers don't break it
      const m = body.match(/\[([^\]]+)\]\(([^)]+)\)/);
      if (m) return { label: m[1], href: m[2] };
      return { label: body, href: null };
    });
}

function CitationsBlock({ raw }: { raw: string }) {
  const [open, setOpen] = React.useState(false);
  const navigate = useNavigate();
  const citations = parseCitations(raw);
  if (citations.length === 0) return null;

  const handleCitationClick = (href: string) => {
    // href is e.g. /explorer?section=section_3_2_1&page=55
    navigate(href);
  };

  return (
    <div style={{ marginTop: 12 }} dir="rtl">
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          fontSize: 11,
          color: "rgba(255,255,255,0.35)",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          padding: 0,
          transition: "color 0.15s",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.color = "rgba(255,255,255,0.6)")}
        onMouseLeave={(e) => (e.currentTarget.style.color = "rgba(255,255,255,0.35)")}
      >
        <ChevronDown
          size={12}
          style={{
            transition: "transform 0.2s",
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
          }}
        />
        {citations.length === 1 ? "مصدر واحد" : `${citations.length} مصادر`}
      </button>

      {open && (
        <ul
          style={{
            marginTop: 6,
            padding: 0,
            listStyle: "none",
            display: "flex",
            flexDirection: "column",
            gap: 3,
          }}
        >
          {citations.map((c, i) => (
            <li key={i}>
              {c.href ? (
                <button
                  onClick={() => handleCitationClick(c.href!)}
                  style={{
                    fontSize: 11,
                    color: "rgba(168,85,247,0.6)",
                    lineHeight: 1.5,
                    paddingRight: 8,
                    borderRight: "2px solid rgba(168,85,247,0.25)",
                    background: "transparent",
                    borderTop: "none",
                    borderBottom: "none",
                    borderLeft: "none",
                    borderRight: "2px solid rgba(168,85,247,0.25)",
                    cursor: "pointer",
                    textAlign: "right",
                    padding: "0 8px 0 0",
                    transition: "color 0.15s",
                    display: "block",
                    width: "100%",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = "rgba(168,85,247,1)")}
                  onMouseLeave={(e) => (e.currentTarget.style.color = "rgba(168,85,247,0.6)")}
                >
                  {c.label}
                </button>
              ) : (
                <span
                  style={{
                    fontSize: 11,
                    color: "rgba(255,255,255,0.3)",
                    lineHeight: 1.5,
                    paddingRight: 8,
                    borderRight: "2px solid rgba(168,85,247,0.25)",
                    display: "block",
                  }}
                >
                  {c.label}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export const AIMessage: React.FC<AIMessageProps> = React.memo(({
  isError,
  isLoading = false,
  text,
  elements,
  meta,
  className,
  bubbleClassName,
}) => {
  const plotLayout = React.useMemo(() => {
    const el = elements?.[0];
    if (!el?.props?.layout) return null;
    return {
      title: { text: el.props.layout.title },
      xaxis: { title: { text: el.props.layout.xaxis.title } },
      yaxis: { title: { text: el.props.layout.yaxis.title } },
    };
  }, [elements]);

  if (isLoading) {
    return (
      <div className={cn("relative flex items-center gap-3", className)}>
        <div className="flex items-center gap-4">
          <SyncLoader color="#7b61ff" margin={5} size={8} speedMultiplier={0.3} />
          <span className="text-gray-400 text-sm animate-pulse">
            {text.trim() || "Analyzing your question…"}
          </span>
        </div>
      </div>
    );
  }

  if (text.length === 0) return null;

  const sepIdx = text.indexOf(CITE_SEP);
  const bodyText = sepIdx === -1 ? text : text.slice(0, sepIdx);
  const citationsRaw = sepIdx === -1 ? "" : text.slice(sepIdx + CITE_SEP.length);

  return (
    <div className={cn("relative flex items-center gap-3", className)}>
      <Message
        text={bodyText}
        meta={meta}
        align="left"
        bubbleClassName={cn(
          "relative rounded-2xl px-6 py-4 text-gray-200",
          isError
            ? "bg-[#FF63631A] border-l-[4px] border-l-[#ef4444]"
            : "bg-[#1e1e2e] border-l-[4px] border-l-[#a855f7]",
          bubbleClassName,
        )}
      >
        {elements && elements.length > 0 && elements[0]?.props?.data && plotLayout && (
          <Plot data={elements[0].props.data} layout={plotLayout} />
        )}
        {citationsRaw && <CitationsBlock raw={citationsRaw} />}
      </Message>
    </div>
  );
});
