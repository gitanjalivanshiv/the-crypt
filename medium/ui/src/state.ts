import type { AnswerResult } from "./types";

export interface Turn {
  question: string;
  /** The unmodified object received from the API (R4.2). */
  result: AnswerResult;
}

export interface State {
  ref: string;
  licence: string;
  turns: Turn[];
  filesFromFindings: string[];
  pending: boolean;
  error: string | null;
  /** The user's last file selection, if any. */
  selected: string | null;
}

export type Action =
  | { type: "loaded"; licence: string; findingFiles: string[] }
  | { type: "submit"; question: string }
  | { type: "answered"; question: string; result: AnswerResult }
  | { type: "failed"; message: string }
  | { type: "select"; file: string };

export function initialState(ref: string): State {
  return {
    ref,
    licence: "",
    turns: [],
    filesFromFindings: [],
    pending: false,
    error: null,
    selected: null,
  };
}

function unique(items: Iterable<string>): string[] {
  return [...new Set(items)];
}

/** Files cited by verified facts, first appearance order. Banished and guess citations are excluded. */
export function cited(result: AnswerResult): string[] {
  return unique(
    result.claims.filter((c) => c.kind === "fact").flatMap((c) => c.citations.map((x) => x.file)),
  );
}

/** Findings files union every cited file, sorted. */
export function files(state: State): string[] {
  return unique([...state.filesFromFindings, ...state.turns.flatMap((t) => cited(t.result))]).sort();
}

/** The user's selection, else the first file cited by the latest turn. */
export function active(state: State): string | null {
  if (state.selected !== null) return state.selected;
  const last = state.turns[state.turns.length - 1];
  return last ? (cited(last.result)[0] ?? null) : null;
}

export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "loaded":
      return { ...state, licence: action.licence, filesFromFindings: unique(action.findingFiles) };
    case "submit":
      if (state.pending) return state;
      return { ...state, pending: true, error: null };
    case "answered":
      return {
        ...state,
        pending: false,
        error: null,
        selected: null,
        turns: [...state.turns, { question: action.question, result: action.result }],
      };
    case "failed":
      return { ...state, pending: false, error: action.message };
    case "select":
      return { ...state, selected: action.file };
  }
}
