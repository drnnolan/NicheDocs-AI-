export type DocumentStatus = "pending" | "processing" | "ready" | "failed";

export interface DocumentSummary {
  id: string;
  filename: string;
  title: string | null;
  page_count: number;
  chunk_count: number;
  status: DocumentStatus;
  error_message: string | null;
  uploaded_at: string;
  processed_at: string | null;
}

/** A retrieved chunk, rendered under an answer as a citation. */
export interface Source {
  chunk_id: string;
  page_number: number;
  section: string | null;
  excerpt: string;
  similarity: number;
  /** True when the model actually relied on this chunk. */
  cited: boolean;
}

export interface AskResponse {
  answer: string;
  /** False means the document does not cover the question. */
  found: boolean;
  sources: Source[];
  document_id: string;
  question: string;
}

export interface SignUploadResponse {
  document_id: string;
  upload_url: string;
  storage_path: string;
}

export interface ProcessResponse {
  document_id: string;
  page_count: number;
  chunk_count: number;
  status: DocumentStatus;
}

export type ChatMessage =
  | { id: string; role: "user"; text: string }
  | {
      id: string;
      role: "assistant";
      text: string;
      found: boolean;
      sources: Source[];
    }
  | { id: string; role: "error"; text: string };
