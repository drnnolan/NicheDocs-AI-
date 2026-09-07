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
  ready: "bg-emerald-100 text-emerald-700",
  processing: "bg-amber-100 text-amber-700",
  pending: "bg-slate-200 text-slate-600",
  failed: "bg-rose-100 text-rose-700",
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
          <li key={index} className="h-14 animate-pulse rounded-lg bg-slate-200" />
        ))}
      </ul>
    );
  }

  if (documents.length === 0) {
    return (
      <p className="rounded-lg border border-slate-200 bg-white px-3 py-4 text-center text-xs text-slate-500">
        No handbooks yet. Upload one to get started.
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
                "group flex items-start gap-2 rounded-lg border px-3 py-2.5 transition-colors",
                selected
                  ? "border-indigo-300 bg-indigo-50"
                  : "border-slate-200 bg-white hover:border-slate-300",
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
                    selected ? "text-indigo-600" : "text-slate-400"
                  }`}
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-slate-800">
                    {doc.title || doc.filename}
                  </span>
                  <span className="mt-1 flex flex-wrap items-center gap-1.5">
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                        STATUS_STYLES[doc.status]
                      }`}
                    >
                      {doc.status}
                    </span>
                    {queryable && (
                      <span className="text-[11px] text-slate-500">
                        {doc.page_count} pages · {doc.chunk_count} chunks
                      </span>
                    )}
                  </span>
                  {doc.status === "failed" && doc.error_message && (
                    <span className="mt-1 block text-[11px] leading-snug text-rose-600">
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
                className="shrink-0 rounded p-1 text-slate-400 opacity-0 transition hover:bg-rose-50 hover:text-rose-600 focus-visible:opacity-100 group-hover:opacity-100"
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
