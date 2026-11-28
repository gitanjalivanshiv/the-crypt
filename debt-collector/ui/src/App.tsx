import { useCallback, useEffect, useRef, useState } from "react";
import { ChatPanel, CrtFrame, Meter, SoundProvider, ThemeProvider, useSound } from "@kiroween/ui-shell";
import { getLedger, getSnapshot, postNotice } from "./api";
import type { Ledger, LedgerLine } from "./api";
import { PlanPanel } from "./PlanPanel";
import { formatNumber, initialState, meterValue, outstanding, reducer, submitNotice } from "./state";
import type { CollectorAction, CollectorState } from "./state";
import { ledger as ledgerTheme } from "./theme/ledger";
import { useDrain } from "./useDrain";
import "./boss.css";

// Units of the figures the ledger shows (mirrors FIGURES and METRIC_UNITS in interest.py).
const PRINCIPAL_UNIT = "lines";
const INTEREST_UNIT = "lines per year";
const METRIC_UNITS: Record<string, string> = {
  commit_count: "commits",
  author_count: "distinct authors",
  days_since_modified: "days",
  age_days: "days",
  todo_count_in_file: "markers in the file",
};

function snapshotFromUrl(): string {
  return new URLSearchParams(window.location.search).get("snapshot") ?? "";
}

function range(l: LedgerLine): string {
  return `${l.file}:${l.line_start}-${l.line_end}`;
}

function LedgerRow({ line, settled, onSettle }: { line: LedgerLine; settled: boolean; onSettle: () => void }) {
  return (
    <li data-boss={line.boss ? "true" : undefined} data-settled={settled ? "true" : undefined}>
      {line.boss && <span className="boss-label">Largest debt</span>}
      <p>
        <strong>#{line.rank}</strong> <code>{range(line)}</code> <small>({line.finding_id})</small>
      </p>
      <p>
        Severity {formatNumber(line.severity)}. Principal {formatNumber(line.principal)} {PRINCIPAL_UNIT}.
        Interest {formatNumber(line.interest)} {INTEREST_UNIT}.
      </p>
      <ul aria-label={`Metrics for ${range(line)}`}>
        {Object.entries(line.metrics).map(([key, value]) => (
          <li key={key}>
            {key}: {formatNumber(value)} {METRIC_UNITS[key] ?? "unspecified"}
          </li>
        ))}
      </ul>
      <button type="button" disabled={settled} onClick={onSettle} aria-label={`Mark settled: ${range(line)}`}>
        {settled ? "Settled" : "Mark settled"}
      </button>
    </li>
  );
}

// Mounted only once the ledger exists, so the first render starts on the target.
function DrainReadout({ target }: { target: number }) {
  return <span data-testid="readout">{formatNumber(useDrain(target))}</span>;
}

function CoverageNote({ ledger }: { ledger: Ledger }) {
  if (!ledger.truncated) return null;
  return (
    <p data-testid="coverage-note">
      Coverage note: this ledger is partial.{" "}
      {ledger.coverage.map((c) => `${c.analyzer}: ${c.returned} of ${c.matching} findings listed`).join("; ")}.
    </p>
  );
}

export function App({ snapshotRef }: { snapshotRef?: string }) {
  return (
    <ThemeProvider theme={ledgerTheme}>
      <SoundProvider sounds={ledgerTheme.sounds}>
        <CrtFrame>
          <Screen snapshotRef={snapshotRef} />
        </CrtFrame>
      </SoundProvider>
    </ThemeProvider>
  );
}

function Screen({ snapshotRef }: { snapshotRef?: string }) {
  const { play } = useSound();
  const ref = snapshotRef ?? snapshotFromUrl();
  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [licence, setLicence] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [state, setState] = useState<CollectorState>(initialState);
  const stateRef = useRef<CollectorState>(initialState);

  const dispatch = useCallback((action: CollectorAction) => {
    stateRef.current = reducer(stateRef.current, action);
    setState(stateRef.current);
  }, []);

  useEffect(() => {
    let live = true;
    getLedger(ref)
      .then((l) => live && setLedger(l))
      .catch((e: { code?: string; message?: string }) =>
        live && setLoadError(`${e.code ?? "unknown_error"}: ${e.message ?? "Unknown error"}`),
      );
    getSnapshot(ref)
      .then((s) => live && setLicence(s.meta.licence))
      .catch(() => undefined); // the licence is a footer detail; the ledger does not need it
    return () => {
      live = false;
    };
  }, [ref]);

  // The shell emits no sound by itself; name the events here.
  const lastNotice = useRef<CollectorState["notice"]>(null);
  useEffect(() => {
    if (!state.notice || state.notice === lastNotice.current) return;
    lastNotice.current = state.notice;
    play("notice");
    for (let i = 0; i < state.notice.banishments.length; i++) play("banish");
  }, [state.notice, play]);

  const serve = () => {
    void submitNotice(() => stateRef.current, dispatch, () => postNotice(ref));
  };

  const errorText = state.error ? `${state.error.code}: ${state.error.message}` : loadError;

  return (
          <main>
            <h1>The Debt Collector</h1>
            <div role="alert" aria-live="assertive" data-testid="error-region">
              {errorText}
            </div>
            {ledger ? (
              <>
                <Meter
                  label="Outstanding interest"
                  value={meterValue(ledger, state.settled)}
                />
                <p>
                  Outstanding: <DrainReadout target={outstanding(ledger, state.settled)} /> of{" "}
                  {formatNumber(ledger.totals.interest)} {INTEREST_UNIT}. Total principal{" "}
                  {formatNumber(ledger.totals.principal)} {PRINCIPAL_UNIT}.
                </p>
                <p data-testid="escalation" data-level={ledger.escalation}>
                  Escalation level: {ledger.escalation}
                </p>
                <CoverageNote ledger={ledger} />
                <button type="button" onClick={serve} disabled={state.pending} aria-busy={state.pending}>
                  {state.pending ? "Serving notice…" : "Serve notice"}
                </button>
                <PlanPanel snapshotRef={ref} />
                <ol aria-label="Ledger">
                  {ledger.lines.map((line) => (
                    <LedgerRow
                      key={line.finding_id}
                      line={line}
                      settled={state.settled.has(line.finding_id)}
                      onSettle={() => {
                        dispatch({ type: "settle", id: line.finding_id });
                        play("settle");
                      }}
                    />
                  ))}
                </ol>
              </>
            ) : (
              !loadError && <p>Loading ledger…</p>
            )}
            {state.notice && <ChatPanel result={state.notice} licence={licence} />}
          </main>
  );
}
