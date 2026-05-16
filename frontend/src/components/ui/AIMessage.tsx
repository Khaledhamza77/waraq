import * as React from "react";
import { Message, type MessageProps } from "./Message";
import { cn } from "@/lib/utils";
import { SyncLoader } from "react-spinners";
import Plot from "react-plotly.js";

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

  // While loading: always show spinner + current status text from backend.
  // The backend updates response_msg.content with each node's status, so
  // `text` here IS the live status (or empty at the very start).
  if (isLoading) {
    return (
      <div className={cn("relative flex items-center gap-3", className)}>
        <div className="flex items-center gap-4">
          <SyncLoader
            color="#7b61ff"
            margin={5}
            size={8}
            speedMultiplier={0.3}
          />
          <span className="text-gray-400 text-sm animate-pulse">
            {text.trim() || "Analyzing your question…"}
          </span>
        </div>
      </div>
    );
  }

  // Not loading — render nothing if response is empty, bubble otherwise.
  if (text.length === 0) return null;

  return (
    <div className={cn("relative flex items-center gap-3", className)}>
      <Message
        text={text}
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
          <Plot
            data={elements[0].props.data}
            layout={plotLayout}
          />
        )}
      </Message>
    </div>
  );
});
