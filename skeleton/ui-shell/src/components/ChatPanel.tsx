import type { AnswerResult, Citation } from "../types";
import styles from "./ChatPanel.module.css";

export interface ChatPanelProps {
  result: AnswerResult;
  licence?: string | null;
}

const cite = (c: Citation): string =>
  `${c.file}:${c.line_start}${c.line_end !== c.line_start ? `-${c.line_end}` : ""}`;

/** Claim text is rendered only from result.claims (verified) and, struck through, result.banishments. */
export function ChatPanel({ result, licence }: ChatPanelProps) {
  const declined = result.status === "declined";
  return (
    <section className={styles.panel} aria-label="Persona message">
      {!declined &&
        result.claims.map((claim, i) => (
          <p key={`claim-${i}`} className={styles.claim} data-kind={claim.kind}>
            {claim.kind === "guess" && <span className={styles.guess}>guess</span>}{" "}
            {claim.text}
            {claim.citations.length > 0 && (
              <span className={styles.citations}>
                {" "}
                {claim.citations.map((c, j) => (
                  <cite key={j} className={styles.cite}>
                    [{cite(c)}]
                  </cite>
                ))}
              </span>
            )}
          </p>
        ))}
      {result.banishments.map((b, i) => (
        <div key={`ban-${i}`} className={styles.banishment} data-testid="banishment">
          <span className={styles.banished}>BANISHED</span> <del>{b.claim_text}</del>
          <p className={styles.reason}>{b.message}</p>
        </div>
      ))}
      {declined && result.decline_line && (
        <p className={styles.decline} data-testid="decline-line">
          {result.decline_line}
        </p>
      )}
      <footer className={styles.meta}>
        <span>Snapshot ID: {result.snapshot_id}</span>
        {licence ? <span> Licence: {licence}</span> : null}
      </footer>
    </section>
  );
}
