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
import { AppShell } from "./ui/Shell";
import { InputBar } from "./ui/InputBar";
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
  const [mode, setMode] = useState<"pick" | "chat">("pick");
  const [isLeaving, setIsLeaving] = useState(false);

  const switchToChat = () => {
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
      <TopBar />
      <AppShell
        className={mode === "pick" ? "max-w-[75%]" : "max-w-[75%] h-full flex flex-col"}
        outerClassName="flex-1 flex items-center overflow-hidden"
      >
        {/* ── Pick mode: two option cards ── */}
        {mode === "pick" && (
          <div
            className={isLeaving ? "fade-out" : "fade-in"}
            style={{
              width: "100%",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 10,
              padding: "12px 0 0",
            }}
          >
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
                maxWidth: 860,
              }}
            >
              {/* Option 1: Document Explorer */}
              <OptionCard
                icon={<BookOpen size={28} strokeWidth={1.5} />}
                iconBg="rgba(124,58,237,0.15)"
                iconColor="#8B5CF6"
                title="تصفح الوثيقة"
                description="استعرض معايير المحاسبة المصرية قسمًا بقسم وتحقق كيف تم تحليلها."
                cta="ابدأ الاستعراض"
                onClick={() => navigate("/explorer")}
              />

              {/* Option 2: Chat */}
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
        )}

        {/* ── Chat mode: messages ── */}
        {mode === "chat" && (
          <div className="fade-in w-full h-full overflow-y-auto px-6 pt-6 pb-40">
            <div className="space-y-4">
              {flatMessages.map((message, index) =>
                renderMessage(message, index === flatMessages.length - 1),
              )}
              <div ref={bottomRef} />
            </div>
          </div>
        )}

      </AppShell>

      {/* ── Input bar (chat mode only) ── */}
      {mode === "chat" && (
        <div className="fade-in-opacity">
          <InputBar ref={inputBarRef} topContent={
            attachedFiles.length > 0 ? (
              <AttachedFiles files={attachedFiles} onRemove={removeAttachedFile} />
            ) : undefined
          }>
            <Input
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
          </InputBar>
        </div>
      )}

      {/* Go to explorer button — rendered outside any animated wrapper */}
      {mode === "chat" && (
        <button
          className="fade-in-opacity"
          onClick={() => navigate("/explorer")}
          style={{
            position: "fixed",
            bottom: 18,
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 200,
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
