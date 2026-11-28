import {
  ChatPanel,
  CrtFrame,
  FileTree,
  SoundProvider,
  ThemeProvider,
} from "@kiroween/ui-shell";
import { useEffect, useMemo, useReducer, useState, type FormEvent, type KeyboardEvent } from "react";
import { ask, getFindings, getSnapshot } from "./api";
import { active, cited, files, initialState, reducer } from "./state";
import { seance } from "./theme/seance";
import { ApiError } from "./types";
import { useSweep } from "./useSweep";

/** Reads the snapshot ref from the URL query: `?ref=<snapshot id>`. */
export function refFromLocation(search: string = window.location.search): string {
  return new URLSearchParams(search).get("ref") ?? "";
}

function describe(err: unknown): string {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`;
  return "unexpected: the request failed";
}

export interface AppProps {
  /** Overrides the URL query; used by tests. */
  snapshotRef?: string;
}

export function App({ snapshotRef }: AppProps) {
  const ref = snapshotRef ?? refFromLocation();
  const [state, dispatch] = useReducer(reducer, ref, initialState);
  const [question, setQuestion] = useState("");

  useEffect(() => {
    if (!ref) {
      dispatch({ type: "failed", message: "missing_ref: add ?ref=<snapshot id> to the URL" });
      return;
    }
    let cancelled = false;
    Promise.all([getSnapshot(ref), getFindings(ref, { limit: 200 })]).then(
      ([snapshot, findings]) => {
        if (cancelled) return;
        dispatch({
          type: "loaded",
          licence: snapshot.meta.licence,
          findingFiles: findings.findings.map((f) => f.file),
        });
      },
      (err: unknown) => {
        if (!cancelled) dispatch({ type: "failed", message: describe(err) });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [ref]);

  const submit = () => {
    const text = question.trim();
    if (!text || state.pending || !ref) return;
    dispatch({ type: "submit", question: text });
    setQuestion("");
    ask(ref, text).then(
      (result) => dispatch({ type: "answered", question: text, result }),
      (err: unknown) => dispatch({ type: "failed", message: describe(err) }),
    );
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit();
  };
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  };

  const latest = state.turns[state.turns.length - 1];
  const citedFiles = useMemo(() => (latest ? cited(latest.result) : []), [latest]);
  const treeFiles = useMemo(() => files(state), [state]);
  const swept = useSweep(citedFiles, state.selected !== null);
  // A user selection (R5.5) wins; otherwise the sweep drives `active`.
  const activeFile = state.selected ?? swept ?? active(state);

  return (
    <ThemeProvider theme={seance}>
      <SoundProvider sounds={seance.sounds}>
        <CrtFrame>
          <main style={{ display: "flex", gap: "1rem", padding: "1rem" }}>
            <nav aria-label="Haunted files" style={{ flex: "0 0 18rem" }}>
              <FileTree
                files={treeFiles}
                cited={citedFiles}
                active={activeFile ?? undefined}
                onSelect={(file) => dispatch({ type: "select", file })}
              />
            </nav>
            <section aria-label="Interview" style={{ flex: 1 }}>
              <h1>The Medium</h1>
              {state.turns.map((turn, i) => (
                <div key={i}>
                  <p>
                    <strong>You:</strong> {turn.question}
                  </p>
                  <ChatPanel result={turn.result} licence={state.licence} />
                </div>
              ))}
              <form onSubmit={onSubmit}>
                <label htmlFor="question">Ask the spirit</label>{" "}
                <input
                  id="question"
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={onKeyDown}
                  disabled={state.pending}
                  autoComplete="off"
                />
              </form>
              <p role="status" aria-live="polite">
                {state.pending ? "The spirit is stirring..." : ""}
              </p>
              <div role="alert" aria-live="assertive" data-testid="error-region">
                {state.error}
              </div>
            </section>
          </main>
        </CrtFrame>
      </SoundProvider>
    </ThemeProvider>
  );
}
