"use client";

import { useState } from "react";

export function MessageComposer({
  disabled,
  onSend,
}: {
  disabled: boolean;
  onSend: (text: string) => Promise<void>;
}) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);

  async function submit() {
    const t = text.trim();
    if (!t || sending) return;
    setSending(true);
    try {
      await onSend(t);
      setText("");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="border-t bg-white p-3">
      <div className="flex gap-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void submit();
            }
          }}
          placeholder={disabled ? "Select a conversation" : "Message… (Enter to send)"}
          disabled={disabled || sending}
          rows={2}
          className="min-h-[44px] flex-1 resize-none rounded-md border bg-gray-50 px-3 py-2 text-sm outline-none focus:border-brand-400 focus:bg-white disabled:opacity-50"
        />
        <button
          type="button"
          onClick={() => void submit()}
          disabled={disabled || sending || !text.trim()}
          className="self-end rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {sending ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}
