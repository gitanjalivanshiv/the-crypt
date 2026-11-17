from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from skeleton.ingest.models import (
    CodeGraph,
    FileEntry,
    FileHistory,
    IngestCode,
    IngestError,
    IngestLimits,
    SnapshotMeta,
)


def _entry(history: FileHistory | None) -> FileEntry:
    return FileEntry(
        path="a.py",
        size_bytes=3,
        line_count=1,
        is_symlink=False,
        parsed=True,
        decodable=True,
        has_syntax_errors=False,
        history=history,
    )


def test_limit_defaults():
    limits = IngestLimits()
    assert limits.max_bytes == 500 * 1024**2
    assert limits.clone_timeout_s == 180
    assert limits.max_files == 50_000


def test_codes_closed_set():
    assert {c.value for c in IngestCode} == {
        "invalid_source",
        "ref_not_found",
        "size_limit_exceeded",
        "file_limit_exceeded",
        "clone_timeout",
        "unsafe_archive",
        "licence_not_permitted",
    }


def test_ingest_error_carries_code_and_detail():
    err = IngestError(IngestCode.clone_timeout, "too slow")
    assert err.code is IngestCode.clone_timeout
    assert err.detail == "too slow"


def test_models_frozen_and_forbid_extra():
    entry = _entry(None)
    with pytest.raises(ValidationError):
        entry.path = "b.py"
    with pytest.raises(ValidationError):
        IngestLimits(bogus=1)


def test_history_none_round_trips():
    graph = CodeGraph(files=[_entry(None)], symbols={}, imports={})
    back = CodeGraph.model_validate_json(graph.model_dump_json())
    assert back == graph
    assert back.files[0].history is None


def test_history_present_round_trips():
    hist = FileHistory(
        commit_count=2, last_modified=datetime(2024, 1, 1, tzinfo=UTC), author_count=1
    )
    entry = _entry(hist)
    assert FileEntry.model_validate_json(entry.model_dump_json()) == entry


def test_snapshot_meta_json_round_trip():
    meta = SnapshotMeta(
        snapshot_id="abc",
        source="https://github.com/o/r",
        licence="MIT",
        retainable=True,
        intent="ephemeral",
        history_available=True,
        ingested_at=datetime(2024, 1, 2, tzinfo=UTC),
        file_count=1,
        total_bytes=3,
        pinned_commit_time=None,
    )
    assert SnapshotMeta.model_validate_json(meta.model_dump_json()) == meta
