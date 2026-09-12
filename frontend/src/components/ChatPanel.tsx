"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatMessage, DocumentSummary } from "@/lib/types";
import { HistoryMenu } from "./HistoryMenu";
import { Message, ThinkingBubble } from "./Message";
import { ArrowRightIcon } from "./icons";

/*
  Document-agnostic starters. These have to be useful whether the upload is a
  student handbook, an employment contract, or a compliance FAQ, so they ask
  about a document's *shape* — scope, obligations, deadlines, definitions —
  rather than any particular subject matter.

  The last one is deliberately unanswerable-ish: it invites the "not found in
  this document" path, which is the behaviour worth showing off.
*/
const EXAMPLE_QUESTIONS = [
  "What is this document about?",
  "What are the key takeaways?",
  "Summarize the main argument",
  "Give me 3 practical lessons",
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
      <section className="flex flex-1 items-center justify-center bg-surface p-8">
        <div className="max-w-md text-center">
          <h2 className="text-lg font-semibold text-content">
            Upload a document to begin
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            NicheDocs answers questions using only the document you upload, and
            shows the page each answer came from. When the document does not
            cover something, it says so instead of guessing.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="flex flex-1 flex-col overflow-hidden bg-surface">
      <header className="flex items-center justify-between gap-4 border-b border-line bg-surface px-8 py-4">
        {/* min-w-0 lets the title truncate instead of shoving the button out. */}
        <div className="min-w-0">
          <h2 className="truncate text-lg font-bold text-content">
            {document.title || document.filename}
          </h2>
          <p className="text-xs text-muted">
            {document.page_count} pages indexed · answers cite this document only
          </p>
        </div>
        <div className="shrink-0">
          <HistoryMenu messages={messages} onPick={submit} disabled={!ready} />
        </div>
      </header>

      <div className="scroll-thin flex-1 space-y-4 overflow-y-auto px-8 py-6">
        {messages.length === 0 && (
          <div className="mx-auto flex max-w-xl flex-col items-center justify-center py-20 text-center">
            <h3 className="text-2xl font-bold tracking-tight text-content">
              Ask anything about this document
            </h3>
            <p className="mt-2 text-sm text-muted">
              Every answer points back to the page it came from
            </p>
            <div className="mt-7 flex flex-wrap justify-center gap-3">
              {EXAMPLE_QUESTIONS.map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => submit(question)}
                  disabled={pending}
                  className="rounded-full border border-line bg-surface px-5 py-2.5 text-sm text-content-soft shadow-sm transition hover:border-accent-line hover:bg-accent-soft hover:text-accent-text hover:shadow disabled:opacity-50"
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
        className="bg-surface px-8 pb-6 pt-2"
      >
        <label htmlFor="question" className="sr-only">
          Your question
        </label>
        {/*
          One capsule containing both the field and the send button, rather than
          a bordered bar with a button beside it. `focus-within` moves the focus
          ring onto the wrapper so the whole capsule lights up as a single
          control — the textarea itself has no border of its own.
        */}
        <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-[28px] border border-line bg-surface py-2 pl-6 pr-2 shadow-lg shadow-black/5 transition focus-within:border-accent-line focus-within:shadow-xl">
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
            placeholder="Ask a question about this document…"
            disabled={pending || !ready}
            className="max-h-40 min-h-[44px] flex-1 resize-none self-center border-0 bg-transparent py-2 text-base text-content placeholder:text-muted focus:outline-none disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={pending || !ready || !draft.trim()}
            aria-label="Send question"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent text-on-accent shadow-sm transition hover:bg-accent-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ArrowRightIcon className="h-5 w-5" />
          </button>
        </div>
        <p className="mt-3 text-center text-xs text-muted">
          Answers come only from this document · Enter to send, Shift+Enter for a new line
        </p>
      </form>
    </section>
  );
}
