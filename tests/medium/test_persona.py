"""The ghost persona (medium R2)."""
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from skeleton.api.app import create_app
from skeleton.mcp.contract import TOOL_NAMES
from skeleton.personas.llm import FakeLLMClient
from skeleton.personas.loader import load_persona, load_personas

PERSONA_DIR = Path(__file__).resolve().parents[2] / "medium" / "personas"
GHOST = PERSONA_DIR / "ghost.toml"


def test_loads_without_warnings() -> None:
    persona = load_persona(GHOST)
    assert persona.name == "ghost"
    assert persona.theme == "seance"
    assert persona.warnings == []


def test_no_digit_in_any_text_field() -> None:
    p = load_persona(GHOST)
    texts = [p.voice, p.decline_line, *p.goals, *p.example_lines]
    assert [t for t in texts if any(ch.isdigit() for ch in t)] == []


def test_allowed_tools_subset_of_contract() -> None:
    p = load_persona(GHOST)
    assert p.allowed_tools and set(p.allowed_tools) <= TOOL_NAMES
    assert {"list_findings", "get_file_facts", "read_lines"} <= set(p.allowed_tools)


def test_persona_wording_rules() -> None:
    p = load_persona(GHOST)
    assert "I suspect" in p.voice and "figures" in p.voice
    assert "no tool result supports" in p.voice


def test_directory_with_only_ghost(tmp_path: Path) -> None:
    shutil.copy(GHOST, tmp_path / "ghost.toml")
    assert list(load_personas(tmp_path)) == ["ghost"]
    assert list(load_personas(PERSONA_DIR)) == ["ghost"]


def test_create_app_starts_with_ghost(tmp_path: Path) -> None:
    app = create_app(store=tmp_path, llm=FakeLLMClient([]), persona_dir=PERSONA_DIR)
    with TestClient(app):
        pass
