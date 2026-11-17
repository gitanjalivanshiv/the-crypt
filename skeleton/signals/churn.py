"""churn: files with many commits.

`commit_count` is the number of commits since the current path was created.
Renames are not followed (git log --no-renames), so a renamed file's history
starts at the rename (D9).
"""

import math
from typing import ClassVar

from skeleton.ingest.parse import ParseResult, parse_python
from skeleton.ingest.snapshot import Snapshot
from skeleton.signals.anchor import anchor_range
from skeleton.signals.models import AnalyzerOutput, Finding, SignalsConfig
from skeleton.verify.textnorm import normalised_lines


def churn_severity(commit_count: int, saturation: int) -> float:
    if commit_count <= 1:
        return 0.0
    return min(1.0, math.log(commit_count) / math.log(saturation))


class Churn:
    name: ClassVar[str] = "churn"
    needs_history: ClassVar[bool] = True
    requires: ClassVar[frozenset[str]] = frozenset()

    def analyze(self, snapshot: Snapshot, cfg: SignalsConfig) -> AnalyzerOutput:
        findings: list[Finding] = []
        for entry in snapshot.graph.files:
            history = entry.history
            if history is None or history.commit_count < cfg.churn_min_commits:
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
                    severity=churn_severity(
                        history.commit_count, cfg.churn_saturation
                    ),
                    metrics={
                        "commit_count": history.commit_count,
                        "author_count": history.author_count,
                    },
                )
            )
        return AnalyzerOutput(findings)
