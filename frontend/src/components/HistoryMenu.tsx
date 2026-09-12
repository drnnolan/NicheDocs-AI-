"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "@/lib/types";
import { CloseIcon, HistoryIcon } from "./icons";

interface Props {
  messages: ChatMessage[];
  /** Re-asks a previous question. */
  onPick: (question: string) => void;
  disabled?: boolean;
}

/**
 * Dropdown listing the questions already asked about the current document.
 *
 * Derives its list from the `messages` already held for this document rather
 * than keeping a parallel copy — one source of truth, so it cannot drift out of
 * sync with the transcript. History is per-document and per-session by design.
 */
export function HistoryMenu({ messages, onPick, disabled = false }: Props) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // Newest first: the question you want again is usually a recent one.
  const questions = messages
    .filter((m): m is Extract<ChatMessage, { role: "user" }> => m.role === "user")
    .map((m) => m.text)
    .reverse();

  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  // Move focus into the panel when it opens so keyboard users land inside it.
  useEffect(() => {
    if (open) panelRef.current?.focus();
  }, [open]);

  const count = questions.length;

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        disabled={disabled || count === 0}
        aria-expanded={open}
        aria-haspopup="dialog"
        title={
          count === 0
            ? "No questions asked yet for this document"
            : `${count} previous question${count === 1 ? "" : "s"}`
        }
        className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-4 py-2 text-sm font-semibold text-content-soft shadow-sm transition hover:border-accent-line hover:text-accent-text hover:shadow focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:border-line disabled:hover:text-content-soft disabled:hover:shadow-sm"
      >
        <HistoryIcon className="h-4 w-4" />
        <span>History</span>
        {count > 0 && (
          <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-bold tabular-nums text-accent-text">
            {count}
          </span>
        )}
      </button>

      {open && count > 0 && (
        <div
          ref={panelRef}
          tabIndex={-1}
          role="dialog"
          aria-label="Previous questions"
          className="absolute right-0 z-30 mt-2 w-[min(22rem,calc(100vw-3rem))] overflow-hidden rounded-2xl border border-line bg-surface shadow-xl shadow-black/10 focus:outline-none"
        >
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <p className="text-xs font-bold uppercase tracking-widest text-muted">
              Previous questions
            </p>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close history"
              className="rounded-full p-1 text-muted transition hover:bg-surface-sunken hover:text-content focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              <CloseIcon className="h-4 w-4" />
            </button>
          </div>

          <ul className="scroll-thin max-h-80 overflow-y-auto py-1">
            {questions.map((question, index) => (
              // Questions can legitimately repeat, so the index is part of the
              // key; the list is never reordered, only appended to.
              <li key={`${index}-${question}`}>
                <button
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    onPick(question);
                  }}
                  className="block w-full px-4 py-2.5 text-left text-sm text-content-soft transition hover:bg-accent-soft hover:text-accent-text focus:bg-accent-soft focus:outline-none"
                >
                  {question}
                </button>
              </li>
            ))}
          </ul>

          <p className="border-t border-line px-4 py-2 text-[11px] text-muted">
            Click a question to ask it again
          </p>
        </div>
      )}
    </div>
  );
}
