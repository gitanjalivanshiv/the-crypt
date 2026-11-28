// Pure data layer: debt arithmetic over a ledger's numbers, and the reducer.
// No number here comes from a model. Settling is local and sends no request.

import type { AnswerResult, Ledger } from "./api";

/** The payload carries six decimal places; nothing here rounds beyond that. */
export const PLACES = 6;

const round6 = (n: number): number => Number(n.toFixed(PLACES));

/** Interest still owed: the sum over lines whose id is not settled. */
export function outstanding(ledger: Ledger, settled: ReadonlySet<string>): number {
  let sum = 0;
  for (const line of ledger.lines) {
    if (!settled.has(line.finding_id)) sum += line.interest;
  }
  return round6(sum);
}

/** Outstanding over total interest, in [0, 1]; 0 when the total is 0. */
export function meterValue(ledger: Ledger, settled: ReadonlySet<string>): number {
  const total = ledger.totals.interest;
  if (!(total > 0)) return 0;
  const v = outstanding(ledger, settled) / total;
  return Math.min(1, Math.max(0, v));
}

/** A new set with the id settled. The input is not changed. */
export function settle(settled: ReadonlySet<string>, id: string): Set<string> {
  const next = new Set(settled);
  next.add(id);
  return next;
}

/** Up to six decimal places, trailing zeros dropped. Never rounds further. */
export function formatNumber(n: number): string {
  if (!Number.isFinite(n)) return String(n);
  const s = n.toFixed(PLACES);
  const trimmed = s.includes(".") ? s.replace(/0+$/, "").replace(/\.$/, "") : s;
  return trimmed === "-0" ? "0" : trimmed;
}

export interface NoticeError {
  code: string;
  message: string;
}

export interface CollectorState {
  settled: ReadonlySet<string>;
  pending: boolean;
  /** The notice exactly as received (same object, not a copy). */
  notice: AnswerResult | null;
  error: NoticeError | null;
}

export type CollectorAction =
  | { type: "settle"; id: string }
  | { type: "notice_start" }
  | { type: "notice_done"; result: AnswerResult }
  | { type: "notice_fail"; error: NoticeError };

export const initialState: CollectorState = {
  settled: new Set<string>(),
  pending: false,
  notice: null,
  error: null,
};

export function reducer(state: CollectorState, action: CollectorAction): CollectorState {
  switch (action.type) {
    case "settle":
      if (state.settled.has(action.id)) return state;
      return { ...state, settled: settle(state.settled, action.id) };
    case "notice_start":
      if (state.pending) return state; // a second submit is ignored
      return { ...state, pending: true, error: null };
    case "notice_done":
      return { ...state, pending: false, notice: action.result, error: null };
    case "notice_fail":
      return { ...state, pending: false, error: action.error };
  }
}

/**
 * Serve a notice. Returns false, without calling `post`, when one is pending.
 * `getState` must read the state after each dispatch.
 */
export async function submitNotice(
  getState: () => CollectorState,
  dispatch: (action: CollectorAction) => void,
  post: () => Promise<AnswerResult>,
): Promise<boolean> {
  if (getState().pending) return false;
  dispatch({ type: "notice_start" });
  try {
    dispatch({ type: "notice_done", result: await post() });
  } catch (err) {
    const e = err as { code?: unknown; message?: unknown };
    dispatch({
      type: "notice_fail",
      error: {
        code: typeof e.code === "string" ? e.code : "unknown_error",
        message: typeof e.message === "string" ? e.message : "Unknown error",
      },
    });
  }
  return true;
}
