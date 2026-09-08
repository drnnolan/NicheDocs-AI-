"use client";

import type { Source } from "@/lib/types";

interface Props {
  source: Source;
  index: number;
}

/**
 * One citation. `cited` distinguishes chunks the model actually used from
 * chunks that merely scored well in retrieval — showing both, clearly labelled,
 * is more honest than hiding the near-misses.
 */
export function SourceCard({ source, index }: Props) {
  return (
    <li
      className={[
        "rounded-lg border px-3 py-2",
        source.cited ? "border-accent-line bg-accent-soft" : "border-line bg-surface-sunken",
      ].join(" ")}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={[
            "flex h-5 w-5 shrink-0 items-center justify-center rounded text-[11px] font-bold",
            source.cited ? "bg-accent text-on-accent" : "bg-line-strong text-content-soft",
          ].join(" ")}
        >
          {index}
        </span>

        <span className="text-xs font-semibold text-content">
          Page {source.page_number}
        </span>

        {source.section && (
          <span className="min-w-0 truncate text-xs text-muted">
            · {source.section}
          </span>
        )}

        <span
          className="ml-auto shrink-0 text-[11px] tabular-nums text-muted"
          title="Cosine similarity between your question and this passage"
        >
          {(source.similarity * 100).toFixed(0)}% match
        </span>
      </div>

      <p className="mt-1.5 text-xs leading-relaxed text-muted">{source.excerpt}</p>

      {!source.cited && (
        <p className="mt-1 text-[11px] italic text-muted">
          Retrieved, but not used in the answer.
        </p>
      )}
    </li>
  );
}
