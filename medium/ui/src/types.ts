import type { AnswerResult } from "@kiroween/ui-shell";

export type { AnswerResult };

/** Mirrors medium/plan.py. */
export interface PlanSection {
  section: "requirements" | "design" | "tasks";
  result: AnswerResult;
}

export interface PlanResult {
  snapshot_id: string;
  sections: PlanSection[];
}

/** Mirrors skeleton/api/models.py (SnapshotDetail, SnapshotMeta, AnalyzerStatus). */
export interface AnalyzerStatus {
  name: string;
  state: "ok" | "skipped" | "failed";
  reason?: string | null;
  truncated?: boolean;
  total_found?: number | null;
}

export interface SnapshotMeta {
  snapshot_id: string;
  source: string;
  licence: string;
  retainable: boolean;
  intent: string;
  history_available: boolean;
  ingested_at: string;
  file_count: number;
  total_bytes: number;
  pinned_commit_time: string | null;
}

export interface SnapshotDetail {
  meta: SnapshotMeta;
  analyzers: AnalyzerStatus[];
}

/** Mirrors skeleton/mcp/contract.py (FindingWithId, ListFindingsOutput). */
export interface FindingWithId {
  id: string;
  analyzer: string;
  file: string;
  line_start: number;
  line_end: number;
  evidence: string;
  severity: number;
  metrics: Record<string, number>;
}

export interface FindingsResult {
  snapshot_id: string;
  findings: FindingWithId[];
  total_matching: number;
  limit_applied: number;
  clamped: boolean;
  analyzers: AnalyzerStatus[];
}

export interface FindingsQuery {
  analyzer?: string;
  file?: string;
  min_severity?: number;
  limit?: number;
}

/**
 * A structured API error: the skeleton's `{"error": {"code", "message"}}` body.
 * `status` is the HTTP status, or 0 when no structured body was received.
 */
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
