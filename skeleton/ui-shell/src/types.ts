/** Hand-written mirror of the API schema (skeleton/verify/models.py). */

export type ReasonCode =
  | "malformed"
  | "path_unsafe"
  | "file_not_found"
  | "symlink"
  | "range_invalid"
  | "range_out_of_bounds"
  | "file_unreadable"
  | "quote_mismatch"
  | "uncited_claim"
  | "figure_not_in_metrics"
  | "figure_not_cited"
  | "unbacked_number";

export interface Citation {
  file: string;
  line_start: number;
  line_end: number;
  quote?: string | null;
}

export interface Figure {
  finding_id: string;
  key: string;
  value: number;
}

export interface VerifiedClaim {
  kind: "fact" | "guess";
  text: string;
  citations: Citation[];
  figures: Figure[];
}

export type BanishmentTarget =
  | { type: "citation"; index: number; citation: Citation }
  | { type: "figure"; index: number; figure: Figure }
  | { type: "number"; token: string };

export interface Banishment {
  claim_text: string;
  reason: ReasonCode;
  message: string;
  target?: BanishmentTarget | null;
  attempt: number;
  snapshot_id: string;
}

export interface AttemptRecord {
  attempt: number;
  outcome: "accepted" | "banished" | "failed";
  failure_kind?: "generator_error" | "unparseable" | null;
}

export interface AnswerResult {
  snapshot_id: string;
  status: "answered" | "declined";
  claims: VerifiedClaim[];
  banishments: Banishment[];
  decline_line?: string | null;
  attempts: AttemptRecord[];
}

export type ChatMessage =
  | { role: "user"; text: string }
  | { role: "persona"; result: AnswerResult };

/** Types generated from the API's OpenAPI schema (scripts/gen-ts-types.sh). */
export type { components, paths, operations } from "./types.generated";
