"use client";

import { useRef, useState } from "react";
import { Send, Paperclip, Loader2 } from "lucide-react";
import MessageBubble, { ChatMessage } from "./MessageBubble";
import PipelineRail from "./PipelineRail";
import FileUpload from "./FileUpload";
import { streamChat } from "@/lib/api";

const STAGE_INDEX: Record<string, number> = {
  router: 0,
  diagnostic: 1,
  retrieval: 2,
  synthesis: 3,
};

const EXAMPLE_PROMPTS = [
  "Interface Gi0/1 keeps flapping every few minutes, high CRC error count",
  "Ping 8.8.8.8 and tell me if latency looks normal",
  "%LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down\n%LINEPROTO-5-UPDOWN: Line protocol on Interface Gi0/1, changed state to down",
];

export default function ChatWindow() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [activeStage, setActiveStage] = useState<number>(-1);
  const [isStreaming, setIsStreaming] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    });
  };

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);
    setIsStreaming(true);
    setActiveStage(0);
    scrollToBottom();

    await streamChat(trimmed, conversationId, (event) => {
      if (event.type === "meta") {
        setConversationId(event.conversation_id);
      } else if (event.type === "status") {
        setActiveStage(STAGE_INDEX[event.node] ?? 0);
      } else if (event.type === "token") {
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          next[next.length - 1] = { ...last, content: last.content + event.text };
          return next;
        });
        scrollToBottom();
      } else if (event.type === "citations") {
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          next[next.length - 1] = { ...last, citations: event.sources };
          return next;
        });
      } else if (event.type === "done" || event.type === "error") {
        setIsStreaming(false);
        setActiveStage(-1);
        if (event.type === "error") {
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = {
              role: "assistant",
              content: `⚠ ${event.message}`,
            };
            return next;
          });
        }
      }
    });

    setIsStreaming(false);
    setActiveStage(-1);
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-border bg-panel/60 px-6 py-3">
        <div className="flex items-center gap-2.5">
          <div className="h-2 w-2 rounded-full bg-ok" />
          <span className="font-display text-sm font-semibold tracking-wide text-ink">
            NET<span className="text-signal">AGENT</span>
          </span>
          <span className="ml-1 font-mono text-[10px] text-muted">
            v1.0 · {process.env.NEXT_PUBLIC_GEMINI_MODEL || "gemini-flash-latest"}
          </span>
        </div>
        <PipelineRail activeIndex={activeStage} />
      </header>

      {/* Transcript */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto bg-grid px-6 py-6">
        {messages.length === 0 ? (
          <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center gap-6 text-center">
            <h1 className="font-display text-2xl font-semibold text-ink">
              Describe the issue, or paste raw logs
            </h1>
            <p className="max-w-md text-sm text-muted">
              The agent routes your report through diagnosis, documentation
              retrieval, and fix synthesis — live, stage by stage.
            </p>
            <div className="flex flex-col gap-2 w-full">
              {EXAMPLE_PROMPTS.map((p) => (
                <button
                  key={p}
                  onClick={() => send(p)}
                  className="rounded border border-border bg-panel px-3 py-2 text-left font-mono text-xs text-muted hover:border-signal hover:text-ink transition-colors"
                >
                  {p.split("\n")[0]}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-4">
            {messages.map((m, i) => (
              <MessageBubble key={i} message={m} />
            ))}
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="border-t border-border bg-panel/60 px-6 py-4">
        <div className="relative mx-auto flex max-w-3xl items-end gap-2">
          {uploadOpen && <FileUpload onOpenChange={setUploadOpen} />}
          <button
            onClick={() => setUploadOpen((v) => !v)}
            className="mb-1 flex h-9 w-9 shrink-0 items-center justify-center rounded border border-border text-muted hover:border-signal hover:text-signal transition-colors"
            aria-label="Upload document to knowledge base"
          >
            <Paperclip size={15} />
          </button>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
            placeholder="Describe the symptom, or paste log lines…"
            rows={1}
            className="max-h-40 flex-1 resize-none rounded border border-border bg-panel2 px-3 py-2 font-mono text-[13px] text-ink placeholder:text-muted focus:border-signal outline-none"
          />
          <button
            onClick={() => send(input)}
            disabled={isStreaming || !input.trim()}
            className="mb-1 flex h-9 w-9 shrink-0 items-center justify-center rounded bg-signal text-bg disabled:opacity-30 hover:bg-signal/90 transition-colors"
            aria-label="Send message"
          >
            {isStreaming ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
          </button>
        </div>
      </div>
    </div>
  );
}
