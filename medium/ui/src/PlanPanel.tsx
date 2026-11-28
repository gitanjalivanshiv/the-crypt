import { ChatPanel } from "@kiroween/ui-shell";
import { useRef, useState } from "react";
import { getPlan } from "./api";
import { ApiError, type PlanResult } from "./types";

const HEADINGS: Record<string, string> = {
  requirements: "Requirements",
  design: "Design",
  tasks: "Tasks",
};

export interface PlanPanelProps {
  snapshotRef: string;
  licence?: string;
}

/** Resurrection plan: one ChatPanel per section, result passed unmodified. */
export function PlanPanel({ snapshotRef, licence }: PlanPanelProps) {
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [pending, setPending] = useState(false);
  const inFlight = useRef(false);

  const resurrect = () => {
    if (inFlight.current || !snapshotRef) return;
    inFlight.current = true;
    setPending(true);
    setError(null);
    setPlan(null);
    getPlan(snapshotRef).then(
      (result) => {
        inFlight.current = false;
        setPlan(result);
        setPending(false);
      },
      (err: unknown) => {
        inFlight.current = false;
        setError(err instanceof ApiError ? err : new ApiError("unknown", "the plan request failed"));
        setPending(false);
      },
    );
  };

  return (
    <section aria-label="Resurrection plan">
      <h2>Resurrection plan</h2>
      <button type="button" onClick={resurrect} disabled={pending || !snapshotRef}>
        Resurrect
      </button>
      <p role="status" aria-live="polite">
        {pending ? "The spirit is gathering its bones..." : ""}
      </p>
      <div role="alert" aria-live="assertive" data-testid="plan-error">
        {error ? `${error.code}: ${error.message}` : ""}
      </div>
      {plan && !error
        ? plan.sections.map((s) => (
            <section key={s.section} aria-labelledby={`plan-${s.section}`}>
              <h3 id={`plan-${s.section}`}>{HEADINGS[s.section] ?? s.section}</h3>
              <ChatPanel result={s.result} licence={licence} />
            </section>
          ))
        : null}
    </section>
  );
}
