"""The debt collector stands beside the skeleton without touching it (debt-collector R7)."""
from __future__ import annotations

import ast
import hashlib
import importlib
import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from skeleton.personas.llm import FakeLLMClient, LLMResponse
from skeleton.personas.loader import load_persona
from tests.debt_collector.test_routes import OK, REF, _big_findings, make_store

api = importlib.import_module("debt-collector.api")

ROOT = Path(__file__).resolve().parents[2]
SKELETON = ROOT / "skeleton"
COLLECTOR = ROOT / "debt-collector"
PERSONA = COLLECTOR / "personas" / "collector.toml"
SKIP_PARTS = {"__pycache__", "node_modules", ".pytest_cache", "dist"}
FORBIDDEN_IMPORTS = {"anthropic", "openai", "boto3", "google", "medium"}

# Files under skeleton/ that may name the persona, with the reason checked by eye.
# skeleton/ingest/history.py: "collector" there means git history collection
# (a collector of commits), unrelated to the persona.
# ui-shell/test/lint.test.ts: the UI grep guard lists persona copy to ban it from src/.
ALLOWED_LEAKS = {
    "ingest/history.py": "word 'collector' means a git history collector",
    "ui-shell/test/lint.test.ts": "grep guard names the strings in order to ban them",
    "ui-shell/eslint.config.js": "no-restricted-imports rule bans importing from debt-collector/",
}


def _manifest() -> dict[str, str]:
    return {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(SKELETON.rglob("*"))
        if p.is_file() and not SKIP_PARTS & set(p.parts)
    }


def test_skeleton_unchanged_by_ledger_notice_and_plan() -> None:  # CP12
    claim = {"text": "It sleeps here.", "citations": [{"file": "a.py", "line_start": 1, "line_end": 1}]}
    llm = FakeLLMClient([LLMResponse(text=json.dumps({"claims": [claim]}))])
    with tempfile.TemporaryDirectory() as tmp:
        store = make_store(Path(tmp), _big_findings(), OK)
        client = TestClient(api.create_collector_app(store=store, llm=llm))
        before = _manifest()
        assert before, "manifest must not be empty"
        assert client.get(f"/collector/snapshots/{REF}/ledger").status_code == 200
        assert client.post(f"/collector/snapshots/{REF}/notice").status_code == 200
        assert client.get(f"/collector/snapshots/{REF}/plan").status_code == 200
        assert len(llm.requests) == 1
        assert _manifest() == before


def test_collector_identity_absent_from_skeleton() -> None:
    persona = load_persona(PERSONA)
    needles = [
        "debt-collector",
        "debt_collector",
        f'"{persona.name}"',
        f"'{persona.name}'",
        persona.display_name,
        *persona.example_lines,
        persona.decline_line,
    ]
    offenders = []
    seen_allowed: set[str] = set()
    for path in SKELETON.rglob("*"):
        if not path.is_file() or SKIP_PARTS & set(path.parts):
            continue
        rel = path.relative_to(SKELETON).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        hits = [n for n in needles if n.lower() in text]
        if not hits:
            continue
        if rel in ALLOWED_LEAKS:
            seen_allowed.add(rel)
            continue
        offenders.append(f"skeleton/{rel}: {hits}")
    assert not offenders, "\n".join(offenders)
    # An allow-list entry that no longer matches anything is stale; drop it.
    stale = set(ALLOWED_LEAKS) - seen_allowed
    assert not stale or all((SKELETON / s).exists() for s in stale)


def test_collector_folder_layout() -> None:
    assert COLLECTOR.is_dir()
    assert COLLECTOR.parent == ROOT
    assert not (COLLECTOR / "__init__.py").exists()


def test_collector_imports_no_sdk_or_medium() -> None:
    files = [p for p in COLLECTOR.rglob("*.py") if not SKIP_PARTS & set(p.parts)]
    assert files
    offenders = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            offenders += [
                f"{path.relative_to(ROOT)}:{node.lineno}: {n}"
                for n in names
                if n.split(".")[0] in FORBIDDEN_IMPORTS
            ]
    assert not offenders, "\n".join(offenders)
