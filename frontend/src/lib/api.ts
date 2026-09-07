import type {
  AskResponse,
  DocumentSummary,
  ProcessResponse,
  SignUploadResponse,
} from "./types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(
  /\/+$/,
  "",
);

/** An error the API returned deliberately, with a message safe to show. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code = "error",
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function readError(response: Response): Promise<ApiError> {
  let message = `Request failed (${response.status})`;
  let code = "error";
  try {
    const body = await response.json();
    if (body?.error?.message) {
      message = body.error.message;
      code = body.error.code ?? code;
    } else if (typeof body?.detail === "string") {
      // FastAPI's own validation errors use `detail`.
      message = body.detail;
    } else if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
      message = body.detail[0].msg;
    }
  } catch {
    // Non-JSON body (a proxy error page, say) — keep the generic message.
  }
  return new ApiError(message, response.status, code);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(
      "Could not reach the server. Check that the backend is running and that NEXT_PUBLIC_API_URL is correct.",
      0,
      "network_error",
    );
  }

  if (!response.ok) throw await readError(response);
  return (await response.json()) as T;
}

export function listDocuments(): Promise<{ documents: DocumentSummary[] }> {
  return request("/documents", { cache: "no-store" });
}

export function deleteDocument(documentId: string): Promise<{ deleted: boolean }> {
  return request(`/documents/${documentId}`, { method: "DELETE" });
}

export function ask(documentId: string, question: string): Promise<AskResponse> {
  return request("/ask", {
    method: "POST",
    body: JSON.stringify({ document_id: documentId, question }),
  });
}

/**
 * Upload a PDF in three steps.
 *
 * The middle step sends the file straight from the browser to Supabase Storage
 * rather than through our API. That is not an optimisation — Vercel Functions
 * reject request bodies over 4.5 MB at the platform edge, so a 20 MB handbook
 * could not reach the backend any other way.
 */
export async function uploadDocument(
  file: File,
  onStage?: (stage: "signing" | "uploading" | "processing") => void,
): Promise<ProcessResponse> {
  onStage?.("signing");
  const signed = await request<SignUploadResponse>("/upload/sign", {
    method: "POST",
    body: JSON.stringify({ filename: file.name, byte_size: file.size }),
  });

  onStage?.("uploading");
  let storageResponse: Response;
  try {
    storageResponse = await fetch(signed.upload_url, {
      method: "PUT",
      headers: { "Content-Type": "application/pdf" },
      body: file,
    });
  } catch {
    throw new ApiError("The upload to storage failed. Check your connection.", 0, "network_error");
  }
  if (!storageResponse.ok) {
    throw new ApiError(
      `Storage rejected the upload (${storageResponse.status}).`,
      storageResponse.status,
      "storage_error",
    );
  }

  onStage?.("processing");
  return request<ProcessResponse>(`/documents/${signed.document_id}/process`, {
    method: "POST",
  });
}
