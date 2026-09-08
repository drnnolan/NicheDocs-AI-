"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatMessage, DocumentSummary } from "@/lib/types";
import { Message, ThinkingBubble } from "./Message";
import { SendIcon } from "./icons";

const EXAMPLE_QUESTIONS = [
  "What is the minimum attendance requirement?",
  "How do I appeal a final grade?",
  "What counts as academic misconduct?",
  "When is the deadline to withdraw from a unit?",
];

interface Props {
  document: DocumentSummary | null;
  messages: ChatMessage[];
  pending: boolean;
  onAsk: (question: string) => void;
}

export function ChatPanel({ document, messages, pending, onAsk }: Props) {
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, pending]);

  const ready = document?.status === "ready";

  function submit(question: string) {
    const trimmed = question.trim();
    if (!trimmed || pending || !ready) return;
    onAsk(trimmed);
    setDraft("");
  }

  if (!document) {
    return (
      <section className="flex flex-1 items-center justify-center rounded-2xl bg-surface p-8 shadow-lg shadow-black/10 ring-1 ring-line">
        <div className="max-w-md text-center">
          <h2 className="text-lg font-semibold text-content">
            Upload a handbook to begin
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            HandbookIQ answers questions using only the document you upload, and
            shows the page each answer came from. When the handbook does not
            cover something, it says so instead of guessing.
          </p>
        </div>
      </section>
    );
  }

  return (
    // Matches the sidebar's floating-card treatment so the two panes read as a
    // pair. overflow-hidden keeps the children clipped to the rounded corners.
    <section className="flex flex-1 flex-col overflow-hidden rounded-2xl bg-surface shadow-lg shadow-black/10 ring-1 ring-line">
      <header className="border-b border-line bg-surface px-6 py-3">
        <h2 className="truncate text-sm font-semibold text-content">
          {document.title || document.filename}
        </h2>
        <p className="text-xs text-muted">
          {document.page_count} pages indexed · answers cite this document only
        </p>
      </header>

      <div className="scroll-thin flex-1 space-y-4 overflow-y-auto px-6 py-5">
        {messages.length === 0 && (
          <div className="mx-auto max-w-lg pt-6 text-center">
            <p className="text-sm text-muted">
              Ask anything about this handbook.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {EXAMPLE_QUESTIONS.map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => submit(question)}
                  disabled={pending}
                  className="rounded-full border border-line-strong bg-surface-sunken px-3 py-1.5 text-xs text-content-soft transition hover:border-accent-line hover:bg-accent-soft hover:text-accent-text disabled:opacity-50"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => (
          <Message key={message.id} message={message} />
        ))}

        {pending && <ThinkingBubble />}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit(draft);
        }}
        className="border-t border-line bg-surface px-6 py-4"
      >
        <div className="flex items-end gap-2">
          <label htmlFor="question" className="sr-only">
            Your question
          </label>
          <textarea
            id="question"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              // Enter sends; Shift+Enter inserts a newline.
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit(draft);
              }
            }}
            rows={1}
            placeholder="Ask about attendance, grading, conduct…"
            disabled={pending || !ready}
            className="max-h-40 min-h-[44px] flex-1 resize-y rounded-xl border border-line-strong px-3.5 py-2.5 text-sm text-content placeholder:text-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent-soft disabled:bg-surface-sunken"
          />
          <button
            type="submit"
            disabled={pending || !ready || !draft.trim()}
            className="flex h-11 shrink-0 items-center gap-1.5 rounded-xl bg-accent px-4 text-sm font-semibold text-on-accent transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:bg-surface-sunken"
          >
            <SendIcon />
            Ask
          </button>
        </div>
        {/*
          slate-600 at 12px, not slate-400 at 11px: the lighter grey fell below
          the WCAG AA contrast minimum on white, which made the grounding
          promise — the most important claim the app makes — the hardest line
          on the page to read.
        */}
        <p className="mt-2 text-xs text-muted">
          Answers come only from this document. Enter to send, Shift+Enter for a new line.
        </p>
      </form>
    </section>
  );
}
