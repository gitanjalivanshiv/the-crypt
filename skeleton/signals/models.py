"""Finding types, config and the analyzer protocol."""

import math
from typing import ClassVar, Literal, NamedTuple, Protocol

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from skeleton.ingest.snapshot import Snapshot


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Finding(_Model):
    analyzer: str
    file: str
    line_start: int
    line_end: int
    evidence: str
    severity: float
    metrics: dict[str, int | float]

    @field_validator("severity")
    @classmethod
    def _severity_range(cls, v: float) -> float:
        if not math.isfinite(v) or not 0.0 <= v <= 1.0:
            raise ValueError("severity must be finite and within [0, 1]")
        return v

    @field_validator("metrics", mode="before")
    @classmethod
    def _metrics_numeric(cls, v: object) -> object:
        if isinstance(v, dict):
            for key, value in v.items():
                if isinstance(value, bool):
                    raise ValueError(f"metric {key!r} must not be a bool")  # noqa: TRY004
        return v

    @field_validator("metrics")
    @classmethod
    def _metrics_finite(cls, v: dict[str, int | float]) -> dict[str, int | float]:
        for key, value in v.items():
            if not math.isfinite(value):
                raise ValueError(f"metric {key!r} must be finite")
        return v

    @model_validator(mode="after")
    def _line_order(self) -> "Finding":
        if self.line_start > self.line_end:
            raise ValueError("line_start must be <= line_end")
        return self


def finding_id(f: Finding) -> str:
    return f"{f.analyzer}:{f.file}:{f.line_start}-{f.line_end}"


class AnalyzerStatus(_Model):
    name: str
    state: Literal["ok", "skipped", "failed"]
    reason: str | None = None
    truncated: bool = False
    total_found: int | None = None


class FindingSet(_Model):
    snapshot_id: str
    findings: list[Finding]
    analyzers: list[AnalyzerStatus]


class SignalsConfig(_Model):
    churn_min_commits: int = 10
    churn_saturation: int = 200
    stale_min_days: int = 365
    stale_saturation_days: int = 3650
    todo_max_markers: int = 2000
    todo_saturation_days: int = 1825


class AnalyzerOutput(NamedTuple):
    findings: list[Finding]
    truncated: bool = False
    total_found: int | None = None


class Analyzer(Protocol):
    name: ClassVar[str]
    needs_history: ClassVar[bool]
    requires: ClassVar[frozenset[str]]

    def analyze(self, snapshot: Snapshot, cfg: SignalsConfig) -> AnalyzerOutput: ...
