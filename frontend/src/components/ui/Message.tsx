import * as React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { cn } from "@/lib/utils";
import remarkBreaks from "remark-breaks";
import { MermaidDiagram } from "./MermaidDiagram";
import { useNavigate } from "react-router-dom";

export type MessageAlignment = "left" | "right";

export interface MessageProps {
  text: string;
  align?: MessageAlignment;
  meta?: string;
  className?: string;
  bubbleClassName?: string;
  children?: React.ReactNode;
}

const remarkPlugins = [remarkGfm, remarkBreaks];
const rehypePlugins = [rehypeRaw];

const API_BASE =
  (import.meta as any).env?.VITE_API_BASE_URL ?? "http://localhost:8000";

export const Message: React.FC<MessageProps> = React.memo(({
  text,
  align = "left",
  meta,
  className,
  bubbleClassName,
  children,
}) => {
  const isRight = align === "right";
  const navigate = useNavigate();

  return (
    <div
      className={cn(
        "w-full flex",
        isRight ? "justify-end" : "justify-start",
        className,
      )}
    >
      <div
        className={cn(
          "max-w-[120ch] text-[13.5px] leading-relaxed",
          bubbleClassName,
        )}
      >
        {/* prose-invert: light colors on dark bg; typography plugin handles sizing */}
        <div className="prose prose-invert max-w-none" dir="auto">
          <ReactMarkdown
            remarkPlugins={remarkPlugins}
            rehypePlugins={rehypePlugins}
            components={{
              // Intercept links — prevent SPA navigation for /documents/ paths
              a: ({ href, children }) => {
                const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
                  if (!href) return;
                  if (href.startsWith("/documents/")) {
                    e.preventDefault();
                    window.open(`${API_BASE}${href}`, "_blank", "noopener,noreferrer");
                  } else if (href.startsWith("/explorer")) {
                    e.preventDefault();
                    navigate(href);
                  }
                };
                const isExternal = !href?.startsWith("/documents/") && !href?.startsWith("/explorer");
                return (
                  <a
                    href={href}
                    onClick={handleClick}
                    target={isExternal ? "_blank" : undefined}
                    rel="noopener noreferrer"
                    className="text-purple-400 underline underline-offset-2 hover:text-purple-300 transition-colors cursor-pointer"
                  >
                    {children}
                  </a>
                );
              },
              code({ className, children, ...props }: any) {
                const language = /language-(\w+)/.exec(className ?? "")?.[1];
                const code = String(children).replace(/\n$/, "");
                if (language === "mermaid") {
                  return <MermaidDiagram code={code} />;
                }
                return (
                  <code className={className} {...props}>
                    {children}
                  </code>
                );
              },
            }}
          >
            {text}
          </ReactMarkdown>
        </div>

        {children}

        {meta ? (
          <div
            className={cn(
              "mt-1 text-[11px] text-green-400/80",
              isRight && "text-right",
            )}
          >
            {meta}
          </div>
        ) : null}
      </div>
    </div>
  );
});
