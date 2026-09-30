"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { Plus, MessageSquare, Loader2 } from "lucide-react";
import { listConversations, ConversationSummary } from "@/lib/api";

export default function ConversationSidebar({
  activeConversationId,
  onSelect,
  onNewChat,
}: {
  activeConversationId: string | null;
  onSelect: (conversationId: string) => void;
  onNewChat: () => void;
}) {
  const { getToken } = useAuth();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);

  // Re-fetch whenever the active conversation changes — this covers both
  // "user picked a different one" and "a brand-new conversation was just
  // created by sending the first message", since that also changes
  // activeConversationId from null to a real id.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listConversations(getToken)
      .then((data) => {
        if (!cancelled) setConversations(data);
      })
      .catch(() => {
        // Non-critical: the sidebar just stays empty/stale rather than
        // blocking the chat itself, which works fine without it.
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeConversationId, getToken]);

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-panel/40">
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="flex w-full items-center justify-center gap-2 rounded border border-border px-3 py-2 font-mono text-xs text-ink hover:border-signal hover:text-signal transition-colors"
        >
          <Plus size={14} />
          New chat
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {loading && conversations.length === 0 ? (
          <div className="flex items-center justify-center py-6 text-muted">
            <Loader2 size={14} className="animate-spin" />
          </div>
        ) : conversations.length === 0 ? (
          <p className="px-2 py-4 text-center font-mono text-[11px] text-muted">
            No conversations yet
          </p>
        ) : (
          <ul className="flex flex-col gap-1">
            {conversations.map((c) => (
              <li key={c.conversation_id}>
                <button
                  onClick={() => onSelect(c.conversation_id)}
                  className={`flex w-full items-center gap-2 rounded px-2 py-2 text-left font-mono text-[11px] transition-colors ${
                    c.conversation_id === activeConversationId
                      ? "bg-panel2 text-ink"
                      : "text-muted hover:bg-panel2 hover:text-ink"
                  }`}
                >
                  <MessageSquare size={12} className="shrink-0" />
                  <span className="truncate">
                    {new Date(c.created_at).toLocaleString(undefined, {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}