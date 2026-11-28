import { useEffect, useRef, useState } from "react";
import { getPlan } from "./api";
import type { PlanResult } from "./api";
import { formatNumber } from "./state";

interface PlanError {
  code: string;
  message: string;
}

/**
 * The repayment plan. Entries render in the order the route returned them;
 * nothing here sorts, filters or recomputes. A failure shows the structured
 * error and no partial plan.
 */
export function PlanPanel({ snapshotRef }: { snapshotRef: string }) {
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [error, setError] = useState<PlanError | null>(null);
  const [pending, setPending] = useState(false);
  const inFlight = useRef(false);
  const live = useRef(true);

  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
    };
  }, []);

  const show = async () => {
    if (inFlight.current) return; // a second submit while pending is ignored
    inFlight.current = true;
    setPending(true);
    setError(null);
    try {
      const result = await getPlan(snapshotRef);
      if (live.current) setPlan(result);
    } catch (err) {
      const e = err as { code?: unknown; message?: unknown };
      if (live.current) {
        setPlan(null);
        setError({
          code: typeof e.code === "string" ? e.code : "unknown_error",
          message: typeof e.message === "string" ? e.message : "Unknown error",
        });
      }
    } finally {
      inFlight.current = false;
      if (live.current) setPending(false);
    }
  };

  return (
    <section aria-label="Repayment plan">
      <button type="button" onClick={() => void show()} disabled={pending} aria-busy={pending}>
        {pending ? "Loading repayment plan…" : "Show repayment plan"}
      </button>
      <div aria-live="assertive" data-testid="plan-error">
        {error ? `${error.code}: ${error.message}` : null}
      </div>
      {plan && (
        <ol aria-label="Plan">
          {plan.entries.map((e) => (
            <li key={e.finding_id} data-testid="plan-entry">
              <strong>#{e.rank}</strong>{" "}
              <code>{`${e.source.file}:${e.source.line_start}-${e.source.line_end}`}</code>{" "}
              <small>({e.finding_id})</small>
              <br />
              Effort {formatNumber(e.effort)}. Interest {formatNumber(e.interest)}. Interest per effort{" "}
              {formatNumber(e.interest_per_effort)}.
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
