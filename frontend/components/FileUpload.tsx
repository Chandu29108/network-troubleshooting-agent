"use client";

import { useState, useRef } from "react";
import { Paperclip, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { uploadDocument } from "@/lib/api";

type Status = { kind: "idle" | "loading" | "success" | "error"; message?: string };

export default function FileUpload({ onOpenChange }: { onOpenChange: (open: boolean) => void }) {
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    setStatus({ kind: "loading" });
    try {
      const result = await uploadDocument(file);
      setStatus({ kind: "success", message: result.message });
    } catch (err) {
      setStatus({ kind: "error", message: err instanceof Error ? err.message : "Upload failed" });
    }
  };

  return (
    <div className="absolute bottom-full right-0 mb-2 w-80 rounded-lg border border-border bg-panel p-4 shadow-xl">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-display text-xs font-semibold tracking-wide text-ink">
          KNOWLEDGE BASE
        </span>
        <button
          onClick={() => onOpenChange(false)}
          className="text-muted hover:text-ink text-xs"
        >
          close
        </button>
      </div>
      <p className="mb-3 text-xs text-muted">
        Upload vendor runbooks, RFCs, or internal docs (.pdf, .txt, .md, .log).
        The agent will cite these when relevant.
      </p>

      <button
        onClick={() => inputRef.current?.click()}
        className="flex w-full items-center justify-center gap-2 rounded border border-dashed border-border py-3 text-xs text-muted hover:border-signal hover:text-signal transition-colors"
      >
        <Paperclip size={14} />
        Choose file
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.txt,.md,.log"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />

      {status.kind === "loading" && (
        <div className="mt-3 flex items-center gap-2 text-xs text-muted">
          <Loader2 size={13} className="animate-spin" /> Indexing…
        </div>
      )}
      {status.kind === "success" && (
        <div className="mt-3 flex items-center gap-2 text-xs text-ok">
          <CheckCircle2 size={13} /> {status.message}
        </div>
      )}
      {status.kind === "error" && (
        <div className="mt-3 flex items-center gap-2 text-xs text-crit">
          <XCircle size={13} /> {status.message}
        </div>
      )}
    </div>
  );
}
