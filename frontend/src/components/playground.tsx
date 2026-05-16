import { Input } from "@/components/ui/input";
import { SendButton } from "@/components/ui/button";

import {
  useChatInteract,
  useChatMessages,
  IStep,
  useChatData,
} from "@chainlit/react-client";
import { useMemo, useState, useRef, useEffect, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { BookOpen, MessageCircle, ArrowLeft, FileSearch } from "lucide-react";
import { UserMessage } from "./ui/UserMessage";
import { AIMessage } from "./ui/AIMessage";
import { TopBar } from "./ui/TopBar";
import { FileUploader } from "./ui/FileUploader";
import { AttachedFiles } from "./ui/AttachedFiles";
import type { AttachedFile } from "@/types/attachedFile";

const MAX_MB = 20;
const ACCEPT = [".pdf"];
const EMPTY_ELEMENTS: any[] = [];
const font = "'Almarai', sans-serif";

const sampleQuestions = [
  "ما هي شروط الاعتراف بالإيراد؟",
  "كيف يُحسب استهلاك الأصول الثابتة؟",
  "ما الفرق بين الإيجار التشغيلي والتمويلي؟",
  "كيف تُصنَّف الأدوات المالية وتُقاس؟",
];

const validate = (f: File) => {
  const ext = f.name.split(".").pop()?.toLowerCase();
  if (!ext || !ACCEPT.includes("." + ext)) {
    return `Only ${ACCEPT.join(", ")} files are allowed.`;
  }
  if (f.size > MAX_MB * 1024 * 1024) {
    return `File too big. Max ${MAX_MB} MB allowed.`;
  }
  return null;
};

function flattenMessages(
  messages: IStep[],
  condition: (node: IStep) => boolean,
): IStep[] {
  return messages.reduce((acc: IStep[], node) => {
    if (condition(node)) {
      acc.push(node);
    }
    if (node.steps?.length) {
      acc.push(...flattenMessages(node.steps, condition));
    }
    return acc;
  }, []);
}

export function Playground() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"pick" | "chat">(
    () => (sessionStorage.getItem("chatMode") as "pick" | "chat") || "pick"
  );
  const [isLeaving, setIsLeaving] = useState(false);

  const switchToChat = () => {
    sessionStorage.setItem("chatMode", "chat");
    setIsLeaving(true);
    setTimeout(() => {
      setMode("chat");
      setIsLeaving(false);
    }, 350);
  };
  const [inputValue, setInputValue] = useState("");
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const fileSnapshotsRef = useRef<AttachedFile[][]>([]);
  const [uploading, setUploading] = useState(false);
  const { sendMessage, uploadFile } = useChatInteract();
  const { messages } = useChatMessages();
  const { loading, disabled, elements } = useChatData();
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const inputBarRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const autoScrollRef = useRef(autoScroll);
  autoScrollRef.current = autoScroll;

  const flatMessages = useMemo(() => {
    return flattenMessages(messages, (m) => m.type.includes("message"));
  }, [messages]);

  useEffect(() => {
    const THRESHOLD = 10;
    const checkBottom = () => {
      const { scrollHeight, scrollTop, clientHeight } =
        document.documentElement;
      return scrollHeight - scrollTop - clientHeight <= THRESHOLD;
    };
    const onUserScroll = () => setAutoScroll(checkBottom());
    window.addEventListener("wheel", onUserScroll);
    window.addEventListener("touchmove", onUserScroll);
    return () => {
      window.removeEventListener("wheel", onUserScroll);
      window.removeEventListener("touchmove", onUserScroll);
    };
  }, []);

  const handleSendMessage = () => {
    if (loading || disabled) return;
    const content = inputValue.trim();
    if (content) {
      const message = {
        name: "User",
        type: "user_message" as const,
        output: content,
      };
      fileSnapshotsRef.current.push([...attachedFiles]);
      sendMessage(message, attachedFiles.map((f) => ({ id: f.id })));
      setAttachedFiles([]);
      setInputValue("");
      setAutoScroll(true);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  };

  const handleFileSelect = async (selectedFile: File) => {
    const err = validate(selectedFile);
    if (err) { alert(err); return; }
    setUploading(true);
    try {
      const { promise } = uploadFile(selectedFile, (p) => console.log("progress:", p));
      const { id } = await promise;
      setAttachedFiles((prev) => [...prev, { id, name: selectedFile.name }]);
    } catch {
      alert("Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  };

  const removeAttachedFile = (id: string) => {
    setAttachedFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const lastMessageOutput = useMemo(
    () => flatMessages[flatMessages.length - 1]?.output ?? "",
    [flatMessages],
  );

  useEffect(() => {
    if (bottomRef.current && autoScrollRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, lastMessageOutput]);

  const elementsByStepId = useMemo(() => {
    const map = new Map<string, any[]>();
    (elements ?? []).forEach((el: any) => {
      const forId = el.forId;
      if (!map.has(forId)) map.set(forId, []);
      map.get(forId)!.push(el);
    });
    return map;
  }, [elements]);

  let userMessageIndex = 0;
  const renderMessage = (message: IStep, isLastMessage: boolean) => {
    const author = (message.name ?? "").trim().toLowerCase();
    const text = message.output ?? "";
    const stepElements = elementsByStepId.get(message.id) ?? EMPTY_ELEMENTS;

    if (author === "user") {
      const files = fileSnapshotsRef.current[userMessageIndex];
      userMessageIndex++;
      return <UserMessage key={message.id} text={text} files={files} className="mt-4" />;
    }

    return (
      <AIMessage
        key={message.id}
        text={text}
        elements={stepElements}
        isError={message.isError || false}
        isLoading={isLastMessage && loading}
        className="mt-4"
      />
    );
  };

  return (
    <div
      dir="rtl"
      style={{
        backgroundColor: "#000000",
        height: "100vh",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Aurora background — shared across modes */}
      <div
        aria-hidden
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 0,
          pointerEvents: "none",
          overflow: "hidden",
        }}
      >
        <div
          className="aurora"
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            width: "140vw",
            height: "140vw",
            marginTop: "-70vw",
            marginLeft: "-70vw",
            background: `
              radial-gradient(ellipse 55% 40% at 60% 35%, rgba(124,58,237,0.55) 0%, transparent 70%),
              radial-gradient(ellipse 45% 50% at 75% 65%, rgba(6,182,212,0.38) 0%, transparent 65%),
              radial-gradient(ellipse 50% 45% at 30% 70%, rgba(37,99,235,0.45) 0%, transparent 70%)
            `,
            filter: "blur(55px)",
          }}
        />
      </div>

      <TopBar />

      {/* ── Pick mode ── */}
      {mode === "pick" && (
        <div
          className={isLeaving ? "fade-out" : "fade-in"}
          style={{
            flex: 1,
            minHeight: 0,
            position: "relative",
            zIndex: 10,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            overflowY: "auto",
            padding: "24px 40px",
          }}
        >
          <div style={{ width: "100%", maxWidth: 860, display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
            <h2
              style={{
                fontFamily: font,
                fontWeight: 700,
                fontSize: 32,
                color: "#F0F2FF",
                margin: "0 0 4px 0",
                textAlign: "center",
              }}
            >
              من أين تبدأ؟
            </h2>
            <p
              style={{
                fontFamily: font,
                fontWeight: 300,
                fontSize: 16,
                color: "#8A8FAD",
                margin: "0 0 20px 0",
                textAlign: "center",
              }}
            >
              اختر ما تريد فعله الآن
            </p>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 20,
                width: "100%",
              }}
            >
              <OptionCard
                icon={<BookOpen size={28} strokeWidth={1.5} />}
                iconBg="rgba(124,58,237,0.15)"
                iconColor="#8B5CF6"
                title="تصفح الوثيقة"
                description="استعرض معايير المحاسبة المصرية قسمًا بقسم وتحقق كيف تم تحليلها."
                cta="ابدأ الاستعراض"
                onClick={() => navigate("/explorer")}
              />
              <OptionCard
                icon={<MessageCircle size={28} strokeWidth={1.5} />}
                iconBg="rgba(59,130,246,0.15)"
                iconColor="#60A5FA"
                title="استشر الخبير"
                description="اطرح أسئلتك القانونية والمحاسبية وسيجيبك النظام بأدلة مباشرة من النصوص."
                cta="ابدأ المحادثة"
                onClick={switchToChat}
                hints={sampleQuestions}
              />
            </div>
          </div>
        </div>
      )}

      {/* ── Chat mode ── */}
      {mode === "chat" && (
        <div
          className="fade-in"
          style={{
            flex: 1,
            minHeight: 0,
            position: "relative",
            zIndex: 10,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Scrollable messages — this is the ONLY scroll container */}
          <div
            style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "24px 0 0" }}
            dir="ltr"
          >
            <div style={{ maxWidth: "75%", margin: "0 auto", padding: "0 40px" }}>
              <div className="space-y-4">
                {flatMessages.map((message, index) =>
                  renderMessage(message, index === flatMessages.length - 1),
                )}
                <div ref={bottomRef} />
              </div>
            </div>
          </div>

          {/* Input area — part of flex flow, never overlaps messages */}
          <div
            style={{
              flexShrink: 0,
              padding: "12px 0 8px",
              backgroundColor: "rgba(0,0,0,0.4)",
              backdropFilter: "blur(12px)",
            }}
          >
            <div style={{ maxWidth: "75%", margin: "0 auto", padding: "0 5px", display: "flex", flexDirection: "column", gap: 6 }}>
              {attachedFiles.length > 0 && (
                <AttachedFiles files={attachedFiles} onRemove={removeAttachedFile} />
              )}
              <div
                ref={inputBarRef}
                className="w-full flex items-center gap-2 rounded-2xl bg-white/5 backdrop-blur-sm border border-white/10 px-4 py-3 text-gray-200 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] transition"
              >
                <Input
                  ref={inputRef}
                  autoFocus
                  className="flex-1"
                  id="message-input"
                  placeholder="اكتب سؤالك هنا…"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyUp={(e) => { if (e.key === "Enter") handleSendMessage(); }}
                />
                <FileUploader
                  accept={ACCEPT}
                  uploading={uploading}
                  onFileSelect={handleFileSelect}
                />
                <SendButton
                  onClick={handleSendMessage}
                  type="submit"
                  disabled={!inputValue.trim() || disabled || loading}
                />
              </div>
              <div style={{ display: "flex", justifyContent: "center" }}>
                <button
                  onClick={() => navigate("/explorer")}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    fontFamily: font,
                    fontWeight: 500,
                    fontSize: 12,
                    color: "rgba(255,255,255,0.4)",
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    padding: "4px 8px",
                    transition: "color 0.2s ease",
                    letterSpacing: "0.02em",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = "rgba(255,255,255,0.75)")}
                  onMouseLeave={(e) => (e.currentTarget.style.color = "rgba(255,255,255,0.4)")}
                >
                  <FileSearch size={13} strokeWidth={1.5} />
                  تصفح الوثيقة
                  <ArrowLeft size={11} strokeWidth={2} />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Option card sub-component ── */
function OptionCard({
  icon,
  iconBg,
  iconColor,
  title,
  description,
  cta,
  onClick,
  hints,
}: {
  icon: ReactNode;
  iconBg: string;
  iconColor: string;
  title: string;
  description: string;
  cta: string;
  onClick: () => void;
  hints?: string[];
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: "rgba(0,0,0,0.2)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        border: `1px solid ${hovered ? "rgba(255,255,255,0.18)" : "rgba(255,255,255,0.08)"}`,
        borderRadius: 14,
        padding: "32px 28px",
        display: "flex",
        flexDirection: "column",
        gap: 0,
        transition: "border-color 0.25s ease, transform 0.25s ease",
        transform: hovered ? "translateY(-3px)" : "translateY(0)",
      }}
    >
      {/* Icon */}
      <div
        style={{
          width: 52,
          height: 52,
          borderRadius: 14,
          background: iconBg,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: iconColor,
        }}
      >
        {icon}
      </div>

      {/* Title */}
      <h3
        style={{
          fontFamily: font,
          fontWeight: 600,
          fontSize: 19,
          color: "#F0F2FF",
          margin: "14px 0 0 0",
        }}
      >
        {title}
      </h3>

      {/* Description */}
      <p
        style={{
          fontFamily: font,
          fontWeight: 400,
          fontSize: 14,
          color: "#7A7F9D",
          lineHeight: 1.75,
          marginTop: 8,
          marginBottom: 0,
          flexGrow: 1,
        }}
      >
        {description}
      </p>

      {/* Sample questions (hints) */}
      {hints && hints.length > 0 && (
        <ul
          style={{
            marginTop: 14,
            marginBottom: 0,
            padding: 0,
            listStyle: "none",
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          {hints.map((q) => (
            <li
              key={q}
              style={{
                fontFamily: font,
                fontSize: 13,
                color: "#4A4F6E",
                lineHeight: 1.65,
                paddingRight: 10,
                borderRight: "2px solid rgba(96,165,250,0.25)",
              }}
            >
              {q}
            </li>
          ))}
        </ul>
      )}

      {/* CTA button */}
      <button
        onClick={onClick}
        style={{
          marginTop: 20,
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          fontFamily: font,
          fontWeight: 600,
          fontSize: 14,
          color: iconColor,
          background: iconBg,
          border: "none",
          borderRadius: 8,
          padding: "10px 18px",
          cursor: "pointer",
          transition: "opacity 0.2s ease",
          alignSelf: "flex-start",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.8")}
        onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
      >
        {cta}
        <ArrowLeft size={13} strokeWidth={2} />
      </button>
    </div>
  );
}
