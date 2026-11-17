"""Signals: pure-code analyzers producing verifiable findings."""

from collections.abc import Iterable, Mapping

from skeleton.ingest.snapshot import Snapshot
from skeleton.signals.models import (
    Analyzer,
    AnalyzerOutput,
    AnalyzerStatus,
    Finding,
    FindingSet,
    SignalsConfig,
    finding_id,
)
from skeleton.verify.textnorm import normalised_lines

ANALYZERS: tuple[Analyzer, ...] = ()

__all__ = [
    "ANALYZERS",
    "Analyzer",
    "AnalyzerOutput",
    "AnalyzerStatus",
    "Finding",
    "FindingSet",
    "SignalsConfig",
    "finding_id",
    "run_all",
]


def _gate(snapshot: Snapshot, findings: list[Finding]) -> str | None:
    """Return the id of the first invalid finding, or None if all are valid."""
    cache: dict[str, list[str] | None] = {}
    for f in findings:
        if f.file not in cache:
            data = snapshot.read_bytes(f.file) if snapshot.entry(f.file) else None
            try:
                cache[f.file] = None if data is None else normalised_lines(data)
            except UnicodeDecodeError:
                cache[f.file] = None
        lines = cache[f.file]
        if lines is None or not 1 <= f.line_start <= f.line_end <= len(lines):
            return finding_id(f)
        if f.evidence != "\n".join(lines[f.line_start - 1 : f.line_end]):
            return finding_id(f)
    return None


def run_all(
    snapshot: Snapshot,
    cfg: SignalsConfig,
    analyzers: Iterable[Analyzer] | None = None,
    inputs: Mapping[str, object] | None = None,
) -> FindingSet:
    available = inputs or {}
    chosen = ANALYZERS if analyzers is None else analyzers
    findings: list[Finding] = []
    statuses: list[AnalyzerStatus] = []
    for a in chosen:
        if a.needs_history and not snapshot.meta.history_available:
            statuses.append(
                AnalyzerStatus(
                    name=a.name, state="skipped", reason="history_unavailable"
                )
            )
            continue
        missing = sorted(r for r in a.requires if r not in available)
        if missing:
            statuses.append(
                AnalyzerStatus(
                    name=a.name, state="skipped", reason=f"{missing[0]}_unavailable"
                )
            )
            continue
        try:
            out = a.analyze(snapshot, cfg)
            bad = _gate(snapshot, out.findings)
        except Exception as exc:  # noqa: BLE001 - an analyzer failure must not stop the others
            statuses.append(
                AnalyzerStatus(
                    name=a.name, state="failed", reason=str(exc) or type(exc).__name__
                )
            )
            continue
        if bad is not None:
            statuses.append(
                AnalyzerStatus(
                    name=a.name, state="failed", reason=f"invalid_finding: {bad}"
                )
            )
            continue
        findings.extend(out.findings)
        statuses.append(
            AnalyzerStatus(
                name=a.name,
                state="ok",
                truncated=out.truncated,
                total_found=out.total_found,
            )
        )
    findings.sort(key=lambda f: (f.analyzer, f.file, f.line_start, f.line_end))
    return FindingSet(
        snapshot_id=snapshot.meta.snapshot_id, findings=findings, analyzers=statuses
    )
