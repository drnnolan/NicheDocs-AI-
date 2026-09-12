"use client";

import type { DocumentSummary } from "@/lib/types";
import { FileIcon, TrashIcon } from "./icons";

interface Props {
  documents: DocumentSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  loading: boolean;
}

const STATUS_STYLES: Record<DocumentSummary["status"], string> = {
  ready: "bg-ok-soft text-ok-text",
  processing: "bg-warn-soft text-warn-text",
  pending: "bg-surface-sunken text-muted",
  failed: "bg-danger-soft text-danger-text",
};

export function DocumentList({
  documents,
  selectedId,
  onSelect,
  onDelete,
  loading,
}: Props) {
  if (loading) {
    return (
      <ul className="space-y-2" aria-busy="true">
        {[0, 1, 2].map((index) => (
          <li key={index} className="h-16 animate-pulse rounded-xl bg-surface-sunken" />
        ))}
      </ul>
    );
  }

  if (documents.length === 0) {
    return (
      <p className="rounded-xl border border-line bg-surface px-3 py-5 text-center text-xs text-muted">
        No documents yet. Upload a PDF to get started.
      </p>
    );
  }

  return (
    <ul className="space-y-1.5">
      {documents.map((doc) => {
        const selected = doc.id === selectedId;
        const queryable = doc.status === "ready";

        return (
          <li key={doc.id}>
            <div
              className={[
                "group flex items-start gap-2.5 rounded-xl border px-3.5 py-3 transition-colors",
                selected
                  ? "border-accent-line bg-accent-soft ring-1 ring-accent-line"
                  : "border-line bg-surface hover:border-accent-line hover:bg-accent-soft/40",
              ].join(" ")}
            >
              <button
                type="button"
                onClick={() => onSelect(doc.id)}
                disabled={!queryable}
                aria-current={selected ? "true" : undefined}
                className="flex min-w-0 flex-1 items-start gap-2.5 text-left disabled:cursor-not-allowed"
              >
                <FileIcon
                  className={`mt-0.5 h-4 w-4 shrink-0 ${
                    selected ? "text-accent-text" : "text-muted"
                  }`}
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-content">
                    {doc.title || doc.filename}
                  </span>
                  <span className="mt-1 flex flex-wrap items-center gap-1.5">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                        STATUS_STYLES[doc.status]
                      }`}
                    >
                      {doc.status}
                    </span>
                    {queryable && (
                      <span className="text-[11px] text-muted">
                        {doc.page_count} pages · {doc.chunk_count} chunks
                      </span>
                    )}
                  </span>
                  {doc.status === "failed" && doc.error_message && (
                    <span className="mt-1 block text-[11px] leading-snug text-danger-text">
                      {doc.error_message}
                    </span>
                  )}
                </span>
              </button>

              <button
                type="button"
                onClick={() => onDelete(doc.id)}
                title={`Delete ${doc.title || doc.filename}`}
                aria-label={`Delete ${doc.title || doc.filename}`}
                className="shrink-0 rounded p-1 text-muted opacity-0 transition hover:bg-danger-soft hover:text-danger-text focus-visible:opacity-100 group-hover:opacity-100"
              >
                <TrashIcon />
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
