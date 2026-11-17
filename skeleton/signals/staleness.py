"""staleness: files not modified for a long time before the pinned commit.

Age is measured against the pinned commit date, never the wall clock, so the
result is reproducible for a given snapshot.
"""

from typing import ClassVar

from skeleton.ingest.parse import ParseResult, parse_python
from skeleton.ingest.snapshot import Snapshot
from skeleton.signals.anchor import anchor_range
from skeleton.signals.models import AnalyzerOutput, Finding, SignalsConfig
from skeleton.verify.textnorm import normalised_lines


def staleness_severity(days: int, saturation: int) -> float:
    return min(1.0, max(0, days) / saturation)


class Staleness:
    name: ClassVar[str] = "staleness"
    needs_history: ClassVar[bool] = True
    requires: ClassVar[frozenset[str]] = frozenset()

    def analyze(self, snapshot: Snapshot, cfg: SignalsConfig) -> AnalyzerOutput:
        pinned = snapshot.meta.pinned_commit_time
        if pinned is None:
            return AnalyzerOutput([])
        findings: list[Finding] = []
        for entry in snapshot.graph.files:
            history = entry.history
            if history is None:
                continue
            days = max(0, (pinned.date() - history.last_modified.date()).days)
            if days < cfg.stale_min_days:
                continue
            data = snapshot.read_bytes(entry.path)
            if data is None:
                continue
            try:
                lines = normalised_lines(data)
            except UnicodeDecodeError:
                continue
            parsed = parse_python(data) if entry.path.endswith(".py") else ParseResult()
            anchor = anchor_range(data, parsed)
            if anchor is None:
                continue
            start, end = anchor
            findings.append(
                Finding(
                    analyzer=self.name,
                    file=entry.path,
                    line_start=start,
                    line_end=end,
                    evidence="\n".join(lines[start - 1 : end]),
                    severity=staleness_severity(days, cfg.stale_saturation_days),
                    metrics={
                        "days_since_modified": days,
                        "commit_count": history.commit_count,
                    },
                )
            )
        return AnalyzerOutput(findings)
