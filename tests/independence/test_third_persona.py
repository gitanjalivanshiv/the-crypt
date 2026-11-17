"""A third persona runs end to end with zero edits under skeleton/ (R7.2, R3.8)."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from skeleton.api.app import ApiConfig, create_app
from skeleton.personas.llm import FakeLLMClient, LLMResponse
from skeleton.personas.loader import load_persona
from tests.api.test_read_routes import REF, SNAP_ID, store  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
SKELETON = ROOT / "skeleton"
THIRD = ROOT / "tests" / "fixtures" / "personas" / "third.toml"
SKIP_PARTS = {"__pycache__", "node_modules", ".pytest_cache"}

# Task 8.2's grep guard lists persona copy as a forbidden pattern; it names the
# strings in order to ban them from src/, so it is not a leak.
UI_LINT_GUARD = "ui-shell/test/lint.test.ts"

GOOD = {"text": "It sleeps here.", "citations": [{"file": "a.py", "line_start": 1, "line_end": 1}]}


def _manifest() -> dict[str, str]:
    return {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(SKELETON.rglob("*"))
        if p.is_file() and not SKIP_PARTS & set(p.parts)
    }


def test_third_persona_needs_no_edits_under_skeleton(store: Path, tmp_path: Path) -> None:  # noqa: F811
    persona = load_persona(THIRD)
    persona_dir = tmp_path / "third_personas"
    persona_dir.mkdir()
    shutil.copy(THIRD, persona_dir / f"{persona.name}.toml")

    before = _manifest()
    assert before, "manifest must not be empty"

    llm = FakeLLMClient([LLMResponse(text=json.dumps({"claims": [GOOD]}))])
    client = TestClient(create_app(store=store, llm=llm, persona_dir=persona_dir, cfg=ApiConfig()))
    r = client.post(f"/snapshots/{REF}/ask", json={"persona": persona.name, "question": "Why?"})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "answered" and body["snapshot_id"] == SNAP_ID
    assert body["claims"][0]["text"] == GOOD["text"]
    assert len(llm.requests) == 1

    assert _manifest() == before


def test_persona_identity_absent_from_skeleton() -> None:
    persona = load_persona(THIRD)
    needles = [f'"{persona.name}"', f"'{persona.name}'", persona.display_name, *persona.example_lines, persona.decline_line]
    offenders = []
    for path in SKELETON.rglob("*"):
        if not path.is_file() or SKIP_PARTS & set(path.parts):
            continue
        if path.relative_to(SKELETON).as_posix() == UI_LINT_GUARD:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        offenders += [
            f"{path.relative_to(ROOT)}: {n}" for n in needles if n.lower() in text
        ]
    assert not offenders, "\n".join(offenders)
