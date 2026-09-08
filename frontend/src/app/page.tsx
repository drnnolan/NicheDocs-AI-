"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { DocumentList } from "@/components/DocumentList";
import { UploadPanel } from "@/components/UploadPanel";
import { ExternalLinkIcon, GitHubIcon } from "@/components/icons";
import { ApiError, ask, deleteDocument, listDocuments } from "@/lib/api";
import type { ChatMessage, DocumentSummary, ProcessResponse } from "@/lib/types";

/** Chat history lives in component state: it is per-session by design (FR6). */
type HistoryMap = Record<string, ChatMessage[]>;

function newId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export default function Home() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [loadingDocuments, setLoadingDocuments] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryMap>({});
  const [pending, setPending] = useState(false);
  const [listError, setListError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const { documents: rows } = await listDocuments();
      setDocuments(rows);
      setListError(null);
      return rows;
    } catch (err) {
      setListError(
        err instanceof ApiError ? err.message : "Could not load your documents.",
      );
      return [];
    } finally {
      setLoadingDocuments(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Auto-select the first ready document so a returning user lands in a
  // usable state instead of an empty pane.
  useEffect(() => {
    if (selectedId) return;
    const firstReady = documents.find((doc) => doc.status === "ready");
    if (firstReady) setSelectedId(firstReady.id);
  }, [documents, selectedId]);

  const selectedDocument = useMemo(
    () => documents.find((doc) => doc.id === selectedId) ?? null,
    [documents, selectedId],
  );

  const messages = selectedId ? (history[selectedId] ?? []) : [];

  const handleUploaded = useCallback(
    async (result: ProcessResponse) => {
      await refresh();
      if (result.status === "ready") setSelectedId(result.document_id);
    },
    [refresh],
  );

  const handleAsk = useCallback(
    async (question: string) => {
      if (!selectedId) return;

      const documentId = selectedId;
      setHistory((current) => ({
        ...current,
        [documentId]: [
          ...(current[documentId] ?? []),
          { id: newId(), role: "user", text: question },
        ],
      }));
      setPending(true);

      try {
        const response = await ask(documentId, question);
        setHistory((current) => ({
          ...current,
          [documentId]: [
            ...(current[documentId] ?? []),
            {
              id: newId(),
              role: "assistant",
              text: response.answer,
              found: response.found,
              sources: response.sources,
            },
          ],
        }));
      } catch (err) {
        setHistory((current) => ({
          ...current,
          [documentId]: [
            ...(current[documentId] ?? []),
            {
              id: newId(),
              role: "error",
              text:
                err instanceof ApiError
                  ? err.message
                  : "Something went wrong while answering. Please try again.",
            },
          ],
        }));
      } finally {
        setPending(false);
      }
    },
    [selectedId],
  );

  const handleDelete = useCallback(
    async (documentId: string) => {
      const target = documents.find((doc) => doc.id === documentId);
      const label = target?.title || target?.filename || "this document";
      if (!window.confirm(`Delete “${label}”? This also removes its chat history.`)) {
        return;
      }

      try {
        await deleteDocument(documentId);
      } catch (err) {
        setListError(
          err instanceof ApiError ? err.message : "Could not delete that document.",
        );
        return;
      }

      setHistory((current) => {
        const next = { ...current };
        delete next[documentId];
        return next;
      });
      if (selectedId === documentId) setSelectedId(null);
      await refresh();
    },
    [documents, refresh, selectedId],
  );

  return (
    <main className="flex h-screen flex-col bg-slate-50">
      <header className="flex shrink-0 items-center justify-between border-b border-sky-200 bg-sky-100 px-6 py-3">
        <div>
          <h1 className="text-base font-bold tracking-tight text-sky-950">
            HandbookIQ
          </h1>
          <p className="text-xs text-sky-800">
            Grounded answers from your student handbook — with page citations
          </p>
        </div>
        <a
          href="https://github.com/drnnolan/NicheDocs-AI-"
          target="_blank"
          // noopener closes the reverse-tabnabbing hole that target="_blank" opens.
          rel="noopener noreferrer"
          aria-label="View the NicheDocs AI source on GitHub (opens in a new tab)"
          className="group inline-flex items-center gap-2 rounded-lg border border-sky-300 bg-white/70 px-3 py-1.5 text-xs font-semibold text-sky-900 shadow-sm transition hover:border-sky-400 hover:bg-white hover:text-sky-950 hover:shadow focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-1 focus-visible:ring-offset-sky-100"
        >
          <GitHubIcon className="h-4 w-4" />
          <span>View source</span>
          <ExternalLinkIcon className="h-3 w-3 opacity-0 transition-opacity group-hover:opacity-70" />
        </a>
      </header>

      <div className="flex min-h-0 flex-1 gap-4 p-4">
        {/*
          Floating card rather than a flush panel: inset from the page edges,
          rounded, and lifted with a soft shadow. The shadow replaces the old
          right-hand border — using both reads as a double edge.
        */}
        <aside className="scroll-thin flex w-80 shrink-0 flex-col gap-4 overflow-y-auto rounded-2xl bg-white p-4 shadow-lg shadow-slate-300/40 ring-1 ring-slate-900/5">
          <UploadPanel onUploaded={handleUploaded} />

          <div>
            <h2 className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Your handbooks
            </h2>

            {listError && (
              <p
                className="mb-2 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700"
                role="alert"
              >
                {listError}
              </p>
            )}

            <DocumentList
              documents={documents}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onDelete={handleDelete}
              loading={loadingDocuments}
            />
          </div>
        </aside>

        <ChatPanel
          document={selectedDocument}
          messages={messages}
          pending={pending}
          onAsk={handleAsk}
        />
      </div>
    </main>
  );
}
