"""Smoke test on a real repository (task 9.1). Needs network access.

Run with: uv run pytest -m network tests/integration
"""

import asyncio
import json
import time
from pathlib import Path

import pytest

from skeleton.ingest import ingest_url
from skeleton.signals import SignalsConfig, finding_id, run_all
from skeleton.signals.store import FINDINGS_FILE, AnalysedSnapshot
from skeleton.verify.flow import run_grounded_turn
from skeleton.verify.models import VerifyConfig

URL = "https://github.com/pallets/itsdangerous"


@pytest.mark.network
def test_itsdangerous_ingest_analyse_and_grounded_turn(tmp_path: Path) -> None:
    snapshot = ingest_url(URL, intent="retained", store=tmp_path / "store")
    assert snapshot.meta.retainable is True
    assert snapshot.meta.intent == "retained"
    assert snapshot.meta.licence == "BSD-3-Clause"
    assert len(snapshot.meta.snapshot_id) == 40

    started = time.perf_counter()
    found = run_all(snapshot, SignalsConfig())
    seconds = time.perf_counter() - started
    print(f"\nmeasured_analysis_seconds={seconds:.3f}")
    assert seconds >= 0

    root = snapshot.root
    (root / FINDINGS_FILE).write_text(found.model_dump_json(), encoding="utf-8")
    assert any(a.state == "ok" for a in found.analyzers)

    candidates = [f for f in found.findings if f.metrics and f.evidence.strip()]
    assert candidates, "expected at least one finding with metrics"
    finding = candidates[0]
    key, value = next(iter(finding.metrics.items()))

    view = AnalysedSnapshot.open(root)
    answer = json.dumps(
        {
            "claims": [
                {
                    "text": f"This code is flagged by the analyzer with {key} of {value!r}.",
                    "citations": [
                        {
                            "file": finding.file,
                            "line_start": finding.line_start,
                            "line_end": finding.line_end,
                            "quote": finding.evidence,
                        }
                    ],
                    "figures": [
                        {"finding_id": finding_id(finding), "key": key, "value": value}
                    ],
                }
            ]
        }
    )

    async def generate(attempt, feedback):  # type: ignore[no-untyped-def]
        return answer

    result = asyncio.run(
        run_grounded_turn(
            view, generate, decline_line="I can't ground that.", cfg=VerifyConfig()
        )
    )
    assert result.status == "answered", result.banishments
    assert result.banishments == ()
    assert len(result.claims) == 1
    assert result.claims[0].kind == "fact"
    assert result.claims[0].figures[0].value == value
