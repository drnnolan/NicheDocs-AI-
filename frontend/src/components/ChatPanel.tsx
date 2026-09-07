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
      <section className="flex flex-1 items-center justify-center p-8">
        <div className="max-w-md text-center">
          <h2 className="text-lg font-semibold text-slate-800">
            Upload a handbook to begin
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">
            HandbookIQ answers questions using only the document you upload, and
            shows the page each answer came from. When the handbook does not
            cover something, it says so instead of guessing.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="flex flex-1 flex-col overflow-hidden">
      <header className="border-b border-slate-200 bg-white px-6 py-3">
        <h2 className="truncate text-sm font-semibold text-slate-800">
          {document.title || document.filename}
        </h2>
        <p className="text-xs text-slate-500">
          {document.page_count} pages indexed · answers cite this document only
        </p>
      </header>

      <div className="scroll-thin flex-1 space-y-4 overflow-y-auto px-6 py-5">
        {messages.length === 0 && (
          <div className="mx-auto max-w-lg pt-6 text-center">
            <p className="text-sm text-slate-600">
              Ask anything about this handbook.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {EXAMPLE_QUESTIONS.map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => submit(question)}
                  disabled={pending}
                  className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 disabled:opacity-50"
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
        className="border-t border-slate-200 bg-white px-6 py-4"
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
            className="max-h-40 min-h-[44px] flex-1 resize-y rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-100"
          />
          <button
            type="submit"
            disabled={pending || !ready || !draft.trim()}
            className="flex h-11 shrink-0 items-center gap-1.5 rounded-xl bg-indigo-600 px-4 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            <SendIcon />
            Ask
          </button>
        </div>
        <p className="mt-2 text-[11px] text-slate-400">
          Answers come only from this document. Enter to send, Shift+Enter for a new line.
        </p>
      </form>
    </section>
  );
}
