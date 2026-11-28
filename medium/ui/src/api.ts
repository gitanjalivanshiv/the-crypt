import {
  ApiError,
  type AnswerResult,
  type FindingsQuery,
  type FindingsResult,
  type PlanResult,
  type SnapshotDetail,
} from "./types";

/** The Medium always speaks as the ghost. */
export const PERSONA = "ghost";

function snapshotPath(ref: string): string {
  return `/snapshots/${encodeURIComponent(ref)}`;
}

async function parseErrorBody(res: Response): Promise<ApiError> {
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    body = undefined;
  }
  const err = (body as { error?: { code?: unknown; message?: unknown } } | undefined)?.error;
  if (err && typeof err.code === "string" && typeof err.message === "string") {
    return new ApiError(err.code, err.message, res.status);
  }
  return new ApiError("unknown", `request failed with status ${res.status}`, res.status);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError("network", "could not reach the API", 0);
  }
  if (!res.ok) throw await parseErrorBody(res);
  return (await res.json()) as T;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getSnapshot(ref: string): Promise<SnapshotDetail> {
  return request<SnapshotDetail>(snapshotPath(ref));
}

export function getFindings(ref: string, query: FindingsQuery = {}): Promise<FindingsResult> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) params.set(key, String(value));
  }
  const qs = params.toString();
  return request<FindingsResult>(`${snapshotPath(ref)}/findings${qs ? `?${qs}` : ""}`);
}

export function ask(ref: string, question: string): Promise<AnswerResult> {
  return post<AnswerResult>(`${snapshotPath(ref)}/ask`, { persona: PERSONA, question });
}

export function getPlan(ref: string): Promise<PlanResult> {
  return request<PlanResult>(`/medium${snapshotPath(ref)}/plan`, { method: "POST" });
}
