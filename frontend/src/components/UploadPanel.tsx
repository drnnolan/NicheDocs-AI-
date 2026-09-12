"use client";

import { useCallback, useRef, useState } from "react";
import { ApiError, uploadDocument } from "@/lib/api";
import type { ProcessResponse } from "@/lib/types";
import { UploadIcon } from "./icons";

const MAX_BYTES = 20 * 1024 * 1024;

const STAGE_LABEL: Record<string, string> = {
  signing: "Preparing upload…",
  uploading: "Uploading to storage…",
  processing: "Extracting text and building the index…",
};

interface Props {
  onUploaded: (result: ProcessResponse) => void;
  disabled?: boolean;
}

export function UploadPanel({ onUploaded, disabled = false }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [stage, setStage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const busy = stage !== null;

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);

      if (!file.name.toLowerCase().endsWith(".pdf")) {
        setError("Only PDF files are supported.");
        return;
      }
      if (file.size > MAX_BYTES) {
        setError(
          `That file is ${(file.size / 1_048_576).toFixed(1)} MB. The limit is 20 MB.`,
        );
        return;
      }

      try {
        const result = await uploadDocument(file, (next) => setStage(next));
        onUploaded(result);
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : "Something went wrong during upload.",
        );
      } finally {
        setStage(null);
        // Clear the input so re-selecting the same file fires onChange again.
        if (inputRef.current) inputRef.current.value = "";
      }
    },
    [onUploaded],
  );

  return (
    <div>
      <div
        onDragOver={(event) => {
          event.preventDefault();
          if (!busy && !disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          if (busy || disabled) return;
          const file = event.dataTransfer.files?.[0];
          if (file) void handleFile(file);
        }}
        className={[
          "rounded-2xl border-2 border-dashed p-6 text-center transition-colors",
          dragging
            ? "border-accent bg-accent-soft"
            : "border-line-strong bg-surface hover:border-accent-line hover:bg-accent-soft/40",
          busy || disabled ? "opacity-70" : "",
        ].join(" ")}
      >
        <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-accent-soft text-accent-text">
          <UploadIcon className="h-5 w-5" />
        </span>

        {busy ? (
          <p className="mt-2 text-sm font-medium text-content-soft" role="status" aria-live="polite">
            {STAGE_LABEL[stage] ?? "Working…"}
          </p>
        ) : (
          <>
            <p className="mt-3 text-base font-bold text-content">Drop a PDF here</p>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              disabled={disabled}
              className="mt-4 inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-on-accent shadow-sm transition hover:bg-accent-hover hover:shadow focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas disabled:cursor-not-allowed disabled:opacity-50"
            >
              <UploadIcon className="h-4 w-4" />
              Browse files
            </button>
          </>
        )}

        <p className="mt-1 text-xs text-muted">Selectable text · up to 20MB</p>

        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void handleFile(file);
          }}
        />
      </div>

      {busy && (
        <div className="mt-2 h-1 overflow-hidden rounded-full bg-surface-sunken">
          <div className="h-full w-1/3 animate-pulse rounded-full bg-accent" />
        </div>
      )}

      {error && (
        <p className="mt-2 rounded-lg bg-danger-soft px-3 py-2 text-xs text-danger-text" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
