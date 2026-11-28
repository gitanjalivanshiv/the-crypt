// Typed wrappers over the collector's HTTP routes.
// Ledger and plan types mirror debt-collector/interest.py by hand. AnswerResult
// belongs to the shell and is re-exported, never redefined.

export type { AnswerResult } from "@kiroween/ui-shell";
import type { AnswerResult } from "@kiroween/ui-shell";

export type Level = "courtesy" | "reminder" | "demand" | "final";

export interface LedgerLine {
  rank: number;
  finding_id: string;
  analyzer: string;
  file: string;
  line_start: number;
  line_end: number;
  severity: number;
  principal: number;
  interest: number;
  boss: boolean;
  metrics: Record<string, number>;
}

export interface Coverage {
  analyzer: string;
  returned: number;
  matching: number;
}

export interface Totals {
  principal: number;
  interest: number;
  severity: number;
}

export interface Ledger {
  snapshot_id: string;
  lines: LedgerLine[];
  totals: Totals;
  escalation: Level;
  coverage: Coverage[];
  truncated: boolean;
}

export interface PlanSource {
  file: string;
  line_start: number;
  line_end: number;
}

export interface PlanEntry {
  rank: number;
  finding_id: string;
  source: PlanSource;
  effort: number;
  interest: number;
  interest_per_effort: number;
  boss: boolean;
}

export interface PlanResult {
  snapshot_id: string;
  entries: PlanEntry[];
}

/** The part of the skeleton's snapshot detail this app reads. */
export interface SnapshotDetail {
  meta: { snapshot_id: string; licence: string; [key: string]: unknown };
  [key: string]: unknown;
}

/** A structured error body: `{"error": {"code", "message"}}`. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

async function toApiError(res: Response): Promise<ApiError> {
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    body = undefined;
  }
  if (isRecord(body) && isRecord(body.error)) {
    const { code, message } = body.error;
    if (typeof code === "string" && typeof message === "string") {
      return new ApiError(code, message, res.status);
    }
  }
  return new ApiError("http_error", `Request failed with status ${res.status}`, res.status);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch (err) {
    throw new ApiError("network_error", err instanceof Error ? err.message : "Network error");
  }
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

const snap = (ref: string): string => `/snapshots/${encodeURIComponent(ref)}`;
const collector = (ref: string): string => `/collector/snapshots/${encodeURIComponent(ref)}`;

export const getSnapshot = (ref: string): Promise<SnapshotDetail> => request(snap(ref));

export const getLedger = (ref: string): Promise<Ledger> => request(`${collector(ref)}/ledger`);

export const getPlan = (ref: string): Promise<PlanResult> => request(`${collector(ref)}/plan`);

/** Serve a notice. The route takes no body; the result is returned unmodified. */
export const postNotice = (ref: string): Promise<AnswerResult> =>
  request(`${collector(ref)}/notice`, { method: "POST" });
