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
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_URL}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
    signal,
  });

  if (!response.ok || !response.body) {
    onEvent({ type: "error", message: `Request failed (${response.status})` });
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

export async function uploadDocument(file: File): Promise<{ filename: string; chunks_indexed: number; message: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_URL}/api/documents/upload`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Upload failed (${response.status})`);
  }
  return response.json();
}