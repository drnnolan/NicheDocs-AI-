"use client";

import type { ChatMessage } from "@/lib/types";
import { AlertIcon, SearchIcon } from "./icons";
import { SourceCard } from "./SourceCard";

export function Message({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-2.5 text-sm leading-relaxed text-white">
          {message.text}
        </p>
      </div>
    );
  }

  if (message.role === "error") {
    return (
      <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
        <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
        <p>{message.text}</p>
      </div>
    );
  }

  // Assistant. A "not found" answer gets its own visual treatment so it can
  // never be mistaken for a confident reply — that distinction is the whole
  // point of the product.
  const notFound = !message.found;

  return (
    <div className="max-w-[92%] space-y-3">
      <div
        className={[
          "rounded-2xl rounded-bl-sm border px-4 py-3",
          notFound ? "border-amber-200 bg-amber-50" : "border-slate-200 bg-white",
        ].join(" ")}
      >
        {notFound && (
          <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-amber-700">
            <SearchIcon className="h-3.5 w-3.5" />
            Not found in this document
          </p>
        )}
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
          {message.text}
        </p>
      </div>

      {message.sources.length > 0 && (
        <div>
          <p className="mb-1.5 px-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            {notFound ? "Closest passages found" : "Sources"}
          </p>
          <ul className="space-y-1.5">
            {message.sources.map((source, index) => (
              <SourceCard key={source.chunk_id} source={source} index={index + 1} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function ThinkingBubble() {
  return (
    <div
      className="flex w-fit items-center gap-1.5 rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3"
      role="status"
      aria-live="polite"
    >
      <span className="sr-only">Searching the handbook…</span>
      {[0, 1, 2].map((index) => (
        <span
          key={index}
          className="thinking-dot h-1.5 w-1.5 rounded-full bg-slate-400"
          style={{ animationDelay: `${index * 0.15}s` }}
        />
      ))}
    </div>
  );
}
