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
          "rounded-xl border-2 border-dashed p-5 text-center transition-colors",
          dragging
            ? "border-indigo-400 bg-indigo-50"
            // slate-50, not white: the sidebar card behind this is already
            // white, so a white dropzone would vanish into it.
            : "border-slate-300 bg-slate-50 hover:border-slate-400 hover:bg-slate-100/70",
          busy || disabled ? "opacity-70" : "",
        ].join(" ")}
      >
        <UploadIcon className="mx-auto h-6 w-6 text-slate-400" />

        {busy ? (
          <p className="mt-2 text-sm font-medium text-slate-700" role="status" aria-live="polite">
            {STAGE_LABEL[stage] ?? "Working…"}
          </p>
        ) : (
          <>
            <p className="mt-2 text-sm font-medium text-slate-700">
              Drop a handbook PDF here
            </p>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              disabled={disabled}
              className="mt-1 text-sm font-semibold text-indigo-600 underline-offset-2 hover:underline disabled:cursor-not-allowed disabled:text-slate-400"
            >
              or choose a file
            </button>
          </>
        )}

        <p className="mt-2 text-xs text-slate-500">PDF with selectable text, up to 20 MB</p>

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
        <div className="mt-2 h-1 overflow-hidden rounded-full bg-slate-200">
          <div className="h-full w-1/3 animate-pulse rounded-full bg-indigo-500" />
        </div>
      )}

      {error && (
        <p className="mt-2 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
