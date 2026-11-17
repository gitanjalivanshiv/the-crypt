"""API request and response models (design 10.2). All frozen pydantic v2."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from skeleton.ingest.models import SnapshotMeta
from skeleton.signals.models import AnalyzerStatus


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class SnapshotRequest(_Model):
    url: str
    ref: str | None = None
    sha: str | None = None
    intent: Literal["ephemeral", "retained"] = "ephemeral"


class JobAccepted(_Model):
    job_id: str
    status: Literal["queued", "running", "done", "failed"]


class JobError(_Model):
    code: str
    message: str


class JobStatus(_Model):
    status: Literal["queued", "running", "done", "failed"]
    stage: Literal["cloning", "parsing", "history", "analysing"] | None = None
    ref: str | None = None
    snapshot_id: str | None = None
    error: JobError | None = None


class SnapshotDetail(_Model):
    meta: SnapshotMeta
    analyzers: tuple[AnalyzerStatus, ...] = ()


class AskRequest(_Model):
    persona: str = Field(min_length=1)
    question: str = Field(min_length=1)
