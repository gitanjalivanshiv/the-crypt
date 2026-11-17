"""Structured API error body and the code-to-HTTP table (design 10.4)."""
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict

from skeleton.ingest.models import IngestCode
from skeleton.verify.codes import ReasonCode


class ApiCode(StrEnum):
    retained_not_allowed = "retained_not_allowed"
    tool_not_allowed = "tool_not_allowed"
    persona_not_found = "persona_not_found"
    snapshot_not_found = "snapshot_not_found"
    job_not_found = "job_not_found"


class ErrorBody(BaseModel):
    model_config = ConfigDict(frozen=True)
    code: str
    message: str


class ErrorResponse(BaseModel):
    """Body of every non-2xx response: ``{"error": {"code", "message"}}``."""

    model_config = ConfigDict(frozen=True)
    error: ErrorBody


HTTP_STATUS: Final[dict[str, int]] = {
    IngestCode.invalid_source: 422,
    IngestCode.unsafe_archive: 422,
    IngestCode.ref_not_found: 404,
    IngestCode.size_limit_exceeded: 413,
    IngestCode.file_limit_exceeded: 413,
    IngestCode.clone_timeout: 504,
    IngestCode.licence_not_permitted: 403,
    ApiCode.retained_not_allowed: 403,
    ApiCode.tool_not_allowed: 403,
    ApiCode.persona_not_found: 404,
    ApiCode.snapshot_not_found: 404,
    ApiCode.job_not_found: 404,
    ReasonCode.MALFORMED: 400,
    ReasonCode.PATH_UNSAFE: 400,
    ReasonCode.RANGE_INVALID: 400,
    ReasonCode.RANGE_OUT_OF_BOUNDS: 400,
    ReasonCode.FILE_NOT_FOUND: 404,
    ReasonCode.SYMLINK: 403,
    # Claim-level reasons are normally banishments inside a 200 answer; if one
    # is ever raised as a request error it is an unprocessable request.
    ReasonCode.FILE_UNREADABLE: 422,
    ReasonCode.QUOTE_MISMATCH: 422,
    ReasonCode.UNCITED_CLAIM: 422,
    ReasonCode.FIGURE_NOT_IN_METRICS: 422,
    ReasonCode.FIGURE_NOT_CITED: 422,
    ReasonCode.UNBACKED_NUMBER: 422,
}


def status_for(code: str) -> int:
    """HTTP status for ``code``. Unknown codes raise ``KeyError`` (never guessed)."""
    return HTTP_STATUS[str(code)]


def error_response(code: str, message: str) -> ErrorResponse:
    """Build the body, keeping the machine code separate from the message."""
    return ErrorResponse(error=ErrorBody(code=str(code), message=message))
