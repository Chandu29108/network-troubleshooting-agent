"use client";

import ReactMarkdown from "react-markdown";
import { FileText } from "lucide-react";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  citations?: string[];
};

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={[
          "max-w-[75ch] rounded-lg px-4 py-3 text-[14.5px] leading-relaxed",
          isUser
            ? "bg-signalSoft/20 border border-signal/30 text-ink"
            : "bg-panel border border-border text-ink",
        ].join(" ")}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap font-body">{message.content}</p>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none prose-headings:font-display prose-headings:text-signal prose-code:font-mono prose-code:text-[13px] prose-pre:bg-panel2 prose-pre:border prose-pre:border-border">
            <ReactMarkdown>{message.content || "…"}</ReactMarkdown>
          </div>
        )}

        {message.citations && message.citations.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5 border-t border-border pt-2.5">
            {message.citations.map((source) => (
              <span
                key={source}
                className="inline-flex items-center gap-1 rounded border border-border bg-panel2 px-2 py-0.5 font-mono text-[11px] text-muted"
              >
                <FileText size={11} className="text-signal" />
                {source}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
