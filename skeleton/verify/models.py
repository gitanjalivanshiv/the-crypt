"""Frozen result models and the SnapshotView protocol for grounded answers."""

from collections.abc import Mapping
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from skeleton.verify.codes import ReasonCode


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Citation(_Model):
    file: str
    line_start: int
    line_end: int
    quote: str | None = None


class Figure(_Model):
    finding_id: str
    key: str
    value: int | float


class VerifiedClaim(_Model):
    kind: Literal["fact", "guess"]
    text: str
    citations: tuple[Citation, ...] = ()
    figures: tuple[Figure, ...] = ()


class CitationTarget(_Model):
    type: Literal["citation"] = "citation"
    index: int
    citation: Citation


class FigureTarget(_Model):
    type: Literal["figure"] = "figure"
    index: int
    figure: Figure


class NumberTarget(_Model):
    type: Literal["number"] = "number"
    token: str


BanishmentTarget = Annotated[
    CitationTarget | FigureTarget | NumberTarget, Field(discriminator="type")
]


class Banishment(_Model):
    claim_text: str
    reason: ReasonCode
    message: str
    target: BanishmentTarget | None = None
    attempt: int
    snapshot_id: str


class AttemptRecord(_Model):
    attempt: int
    outcome: Literal["accepted", "banished", "failed"]
    failure_kind: Literal["generator_error", "unparseable"] | None = None


class AnswerResult(_Model):
    snapshot_id: str
    status: Literal["answered", "declined"]
    claims: tuple[VerifiedClaim, ...] = ()
    banishments: tuple[Banishment, ...] = ()
    decline_line: str | None = None
    attempts: tuple[AttemptRecord, ...] = ()


class VerifyConfig(_Model):
    allowed_numbers: frozenset[str] = frozenset()


class SnapshotView(Protocol):
    snapshot_id: str

    def entry_kind(self, path: str) -> Literal["file", "symlink"] | None: ...

    def has_symlink_ancestor(self, path: str) -> bool: ...

    def read_bytes(self, path: str) -> bytes | None: ...

    def finding(
        self, finding_id: str
    ) -> tuple[str, Mapping[str, int | float]] | None: ...
