import pytest

from skeleton.api.errors import HTTP_STATUS, ApiCode, error_response, status_for
from skeleton.api.models import AskRequest, JobStatus
from skeleton.ingest.models import IngestCode
from skeleton.verify.codes import ReasonCode

ALL_CODES = [*IngestCode, *ReasonCode, *ApiCode]


@pytest.mark.parametrize("code", ALL_CODES)
def test_every_code_maps_to_error_status(code):
    assert 400 <= status_for(code) < 600


def test_no_stale_entries():
    assert {str(c) for c in ALL_CODES} == {str(k) for k in HTTP_STATUS}


def test_unknown_code_is_not_mapped():
    with pytest.raises(KeyError):
        status_for("not_a_code")


@pytest.mark.parametrize(
    ("code", "status"),
    [
        (IngestCode.invalid_source, 422), (IngestCode.unsafe_archive, 422),
        (IngestCode.ref_not_found, 404), (IngestCode.size_limit_exceeded, 413),
        (IngestCode.file_limit_exceeded, 413), (IngestCode.clone_timeout, 504),
        (IngestCode.licence_not_permitted, 403), (ApiCode.retained_not_allowed, 403),
        (ApiCode.tool_not_allowed, 403), (ApiCode.persona_not_found, 404),
        (ApiCode.snapshot_not_found, 404), (ReasonCode.MALFORMED, 400),
        (ReasonCode.PATH_UNSAFE, 400), (ReasonCode.RANGE_INVALID, 400),
        (ReasonCode.RANGE_OUT_OF_BOUNDS, 400), (ReasonCode.FILE_NOT_FOUND, 404),
        (ReasonCode.SYMLINK, 403),
    ],
)
def test_design_table(code, status):
    assert status_for(code) == status


def test_error_body_shape_keeps_code_separate():
    body = error_response(IngestCode.clone_timeout, "took too long").model_dump()
    assert body == {"error": {"code": "clone_timeout", "message": "took too long"}}


def test_models_round_trip():
    assert AskRequest(persona="a", question="b").persona == "a"
    j = JobStatus(status="failed", error={"code": "clone_timeout", "message": "x"})
    assert j.error.code == "clone_timeout"
