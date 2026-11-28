"""The Medium stands beside the skeleton without touching it (medium R8, R9.4)."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from medium.plan import SECTION_QUESTIONS
from tests.medium.test_plan_route import (  # noqa: F401  (make is a pytest fixture)
    GOOD,
    _client_with_snapshot,
    _reply,
    make,
)

ROOT = Path(__file__).resolve().parents[2]
SKELETON = ROOT / "skeleton"
MEDIUM = ROOT / "medium"
PROVIDERS = ROOT / "providers"
SKIP_PARTS = {"__pycache__", "node_modules", ".pytest_cache", "dist"}
FORBIDDEN_IMPORTS = {"anthropic", "openai", "boto3", "debt_collector", "debt-collector"}
NEEDLES = ("medium", "ghost", "providers", "anthropic")

# Files under skeleton/ that may name the needles, with the reason checked by eye.
# Each one names the strings only to ban them.
ALLOWED_LEAKS = {
    "ui-shell/test/contrast.test.ts": "regex of persona words the shell's own copy must not contain",
    "ui-shell/test/lint.test.ts": "grep guard names the strings in order to ban them",
    "ui-shell/eslint.config.js": "no-restricted-imports rule bans importing from medium/",
}

# Skeleton modules the Medium must not reach into (anything else under skeleton.verify
# except skeleton.verify.models is also banned; see _banned).
BANNED_MODULES = {
    "skeleton.personas.generator",
    "skeleton.personas.prompt",
    "skeleton.mcp.router",
}


def _manifest() -> dict[str, str]:
    return {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(SKELETON.rglob("*"))
        if p.is_file() and not SKIP_PARTS & set(p.parts)
    }


def _py_files(folder: Path) -> list[Path]:
    return [p for p in folder.rglob("*.py") if not SKIP_PARTS & set(p.parts)]


def _imports(path: Path) -> list[tuple[int, str]]:
    """Absolute imported module names, with `from m import n` expanded to `m.n`."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(node.lineno, a.name) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.append((node.lineno, node.module))
            out += [(node.lineno, f"{node.module}.{a.name}") for a in node.names]
    return out


def _banned(name: str) -> bool:
    if name == "skeleton.verify" or name.startswith("skeleton.verify."):
        # `from skeleton.verify import X` is only reachable as the bare package entry,
        # which is banned unless the expanded name is skeleton.verify.models.
        return name != "skeleton.verify.models" and not name.startswith("skeleton.verify.models.")
    return any(name == m or name.startswith(m + ".") for m in BANNED_MODULES)


def test_skeleton_unchanged_by_full_turn_and_full_plan(make, monkeypatch, tmp_path_factory) -> None:  # noqa: F811  (MP9)
    script = [_reply(GOOD)] * 4
    client, ref, llm = _client_with_snapshot(make, monkeypatch, tmp_path_factory, script)
    before = _manifest()
    assert before, "manifest must not be empty"
    ask = client.post(
        f"/snapshots/{ref}/ask", json={"persona": "ghost", "question": SECTION_QUESTIONS["requirements"]}
    )
    assert ask.status_code == 200, ask.text
    plan = client.post(f"/medium/snapshots/{ref}/plan")
    assert plan.status_code == 200, plan.text
    assert len(plan.json()["sections"]) == 3
    assert len(llm.requests) == 4
    assert _manifest() == before


def test_medium_identity_absent_from_skeleton() -> None:
    offenders = []
    seen_allowed: set[str] = set()
    for path in SKELETON.rglob("*"):
        if not path.is_file() or SKIP_PARTS & set(path.parts):
            continue
        rel = path.relative_to(SKELETON).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        hits = [n for n in NEEDLES if n in text]
        if not hits:
            continue
        if rel in ALLOWED_LEAKS:
            seen_allowed.add(rel)
            continue
        offenders.append(f"skeleton/{rel}: {hits}")
    assert not offenders, "\n".join(offenders)
    # An allow-list entry that no longer matches anything is stale; drop it.
    stale = set(ALLOWED_LEAKS) - seen_allowed
    assert not stale, f"stale allow-list entries: {sorted(stale)}"


def test_medium_imports_no_sdk_or_collector() -> None:
    files = _py_files(MEDIUM)
    assert files
    offenders = [
        f"{path.relative_to(ROOT)}:{line}: {name}"
        for path in files
        for line, name in _imports(path)
        if name.split(".")[0] in FORBIDDEN_IMPORTS
    ]
    assert not offenders, "\n".join(offenders)


def test_medium_uses_only_the_skeleton_public_surface() -> None:
    offenders = [
        f"{path.relative_to(ROOT)}:{line}: {name}"
        for path in _py_files(MEDIUM)
        for line, name in _imports(path)
        if _banned(name)
    ]
    assert not offenders, "\n".join(offenders)


def test_banned_helper_catches_what_it_should() -> None:
    assert _banned("skeleton.verify.claim")
    assert _banned("skeleton.verify")
    assert _banned("skeleton.personas.prompt")
    assert _banned("skeleton.personas.generator.ToolLoopGenerator")
    assert _banned("skeleton.mcp.router")
    assert not _banned("skeleton.verify.models")
    assert not _banned("skeleton.verify.models.AnswerResult")
    assert not _banned("skeleton.personas.llm")


def test_medium_and_providers_folders_at_repo_root() -> None:
    for folder in (MEDIUM, PROVIDERS):
        assert folder.is_dir()
        assert folder.parent == ROOT
    assert (MEDIUM / "personas" / "ghost.toml").is_file()
