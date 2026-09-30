const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type StreamEvent =
  | { type: "meta"; conversation_id: string }
  | { type: "status"; node: string }
  | { type: "token"; text: string }
  | { type: "citations"; sources: string[] }
  | { type: "done"; conversation_id: string }
  | { type: "error"; message: string };

/**
 * Streams a chat response via SSE. We use fetch + a manual reader instead of
 * the browser's EventSource because EventSource only supports GET requests,
 * and we need to POST the user's message + conversation_id.
 */
export async function streamChat(
  message: string,
  conversationId: string | null,
  onEvent: (event: StreamEvent) => void,
  getToken: () => Promise<string | null>,
  signal?: AbortSignal
): Promise<void> {
  const token = await getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(`${API_URL}/api/chat/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({ message, conversation_id: conversationId }),
    signal,
  });

  if (!response.ok || !response.body) {
    if (response.status === 429) {
      onEvent({
        type: "error",
        message: "You're sending messages a bit too fast. Please wait a minute and try again.",
      });
    } else {
      onEvent({ type: "error", message: `Request failed (${response.status})` });
    }
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const rawEvents = buffer.split(/\r?\n\r?\n/);
    buffer = rawEvents.pop() || "";

    for (const raw of rawEvents) {
      let eventType = "message";
      let data = "";
      for (const line of raw.split(/\r?\n/)) {
        if (line.startsWith("event:")) eventType = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      try {
        const parsed = JSON.parse(data);
        onEvent({ type: eventType as StreamEvent["type"], ...parsed });
      } catch {
        // ignore malformed chunk
      }
    }
  }
}

export async function uploadDocument(
  file: File,
  getToken: () => Promise<string | null>
): Promise<{ filename: string; chunks_indexed: number; message: string }> {
  const token = await getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_URL}/api/documents/upload`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!response.ok) {
    if (response.status === 429) {
      throw new Error("Too many uploads recently. Please wait a while before uploading again.");
    }
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Upload failed (${response.status})`);
  }
  return response.json();
}
export type ConversationSummary = { conversation_id: string; created_at: string };
export type ChatMessageOut = { role: string; content: string };
export type ConversationDetail = { conversation_id: string; messages: ChatMessageOut[] };

async function _authedFetch(
  path: string,
  getToken: () => Promise<string | null>,
  init?: RequestInit
): Promise<Response> {
  const token = await getToken();
  const headers: Record<string, string> = { ...(init?.headers as Record<string, string>) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(`${API_URL}${path}`, { ...init, headers });
}

export async function listConversations(
  getToken: () => Promise<string | null>
): Promise<ConversationSummary[]> {
  const response = await _authedFetch("/api/chat/conversations", getToken);
  if (!response.ok) throw new Error(`Failed to load conversations (${response.status})`);
  return response.json();
}

export async function getConversation(
  conversationId: string,
  getToken: () => Promise<string | null>
): Promise<ConversationDetail> {
  const response = await _authedFetch(`/api/chat/conversations/${conversationId}`, getToken);
  if (!response.ok) throw new Error(`Failed to load conversation (${response.status})`);
  return response.json();
}
