"""Frozen models, limits and errors for snapshot ingest."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

Intent = Literal["retained", "ephemeral"]
DEFAULT_INTENT: Intent = "ephemeral"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class IngestLimits(_Model):
    max_bytes: int = 500 * 1024**2
    clone_timeout_s: int = 180
    max_files: int = 50_000


class IngestCode(StrEnum):
    invalid_source = "invalid_source"
    ref_not_found = "ref_not_found"
    size_limit_exceeded = "size_limit_exceeded"
    file_limit_exceeded = "file_limit_exceeded"
    clone_timeout = "clone_timeout"
    unsafe_archive = "unsafe_archive"
    licence_not_permitted = "licence_not_permitted"


class IngestError(Exception):
    def __init__(self, code: IngestCode, detail: str) -> None:
        super().__init__(f"{code.value}: {detail}")
        self.code = code
        self.detail = detail


class FileHistory(_Model):
    commit_count: int
    last_modified: datetime
    author_count: int


class FileEntry(_Model):
    path: str
    size_bytes: int
    line_count: int
    is_symlink: bool
    parsed: bool
    decodable: bool
    has_syntax_errors: bool
    history: FileHistory | None


class Symbol(_Model):
    name: str
    kind: Literal["module", "class", "function", "method"]
    line_start: int
    line_end: int


class Import(_Model):
    module: str
    names: list[str]
    line: int
    level: int
    resolved_file: str | None


class CodeGraph(_Model):
    files: list[FileEntry]
    symbols: dict[str, list[Symbol]]
    imports: dict[str, list[Import]]


class SnapshotMeta(_Model):
    snapshot_id: str
    source: str
    licence: str
    retainable: bool
    intent: Intent
    history_available: bool
    ingested_at: datetime
    file_count: int
    total_bytes: int
    pinned_commit_time: datetime | None
