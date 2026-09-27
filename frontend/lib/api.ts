// Typed client for the CodeCare API. Types come only from the generated lib/types.ts.
import type { components } from "./types";

type Schemas = components["schemas"];
export type Note = Schemas["Note"];
export type NoteCreate = Schemas["NoteCreate"];
export type AnalysisResult = Schemas["AnalysisResult"];
export type Suggestion = Schemas["Suggestion"];
export type Gap = Schemas["Gap"];
export type RuleResult = Schemas["RuleResult"];
export type ReviewRequest = Schemas["ReviewRequest"];
export type ReviewEvent = Schemas["ReviewEvent"];
export type NoteHistory = Schemas["NoteHistory"];
export type ErrorResponse = Schemas["ErrorResponse"];

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** A non-2xx response. Pages branch on errorCode, never on the message text. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly errorCode: string,
    message: string,
    readonly analysisId: string | null = null,
  ) {
    super(message);
  }
}

async function call<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}/api/v1${path}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", `Cannot reach the API at ${API_BASE}.`);
  }
  const data: unknown = await resp.json().catch(() => null);
  if (!resp.ok) {
    const err = data as Partial<ErrorResponse> | null;
    throw new ApiError(
      resp.status,
      err?.error_code ?? "UNKNOWN_ERROR",
      err?.message ?? `HTTP ${resp.status}`,
      err?.analysis_id ?? null,
    );
  }
  return data as T;
}

export const api = {
  createNote: (body: NoteCreate) => call<Note>("POST", "/notes", body),
  getNote: (id: string) => call<Note>("GET", `/notes/${encodeURIComponent(id)}`),
  analyzeNote: (id: string) =>
    call<AnalysisResult>("POST", `/notes/${encodeURIComponent(id)}/analyze`),
  getAnalysis: (id: string) =>
    call<AnalysisResult>("GET", `/analyses/${encodeURIComponent(id)}`),
  getHistory: (id: string) =>
    call<NoteHistory>("GET", `/notes/${encodeURIComponent(id)}/history`),
  review: (analysisId: string, suggestionId: string, body: ReviewRequest) =>
    call<ReviewEvent>(
      "POST",
      `/analyses/${encodeURIComponent(analysisId)}/suggestions/${encodeURIComponent(suggestionId)}/reviews`,
      body,
    ),
};

/** Friendly text for an error code; the raw code and message are shown too. */
export function describeError(err: unknown): string {
  if (!(err instanceof ApiError)) return "Something went wrong.";
  switch (err.errorCode) {
    case "NETWORK_ERROR":
      return err.message;
    case "LLM_UNAVAILABLE":
      return "The language model is unavailable right now. Try again in a minute.";
    case "LLM_BAD_OUTPUT":
      return "The language model returned output that failed validation.";
    case "TIMEOUT":
      return "The analysis took longer than the time limit.";
    case "CODE_SET_MISSING":
      return "No ICD-10-CM code set covers this visit date.";
    case "PIPELINE_ERROR":
      return "The analysis failed inside the pipeline.";
    case "DB_ERROR":
      return "The database could not store the result.";
    default:
      return err.message;
  }
}
