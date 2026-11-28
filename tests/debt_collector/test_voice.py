"""The collector persona and the notice question (debt-collector R2, R4.3)."""
import importlib
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from skeleton.api.app import create_app
from skeleton.mcp.contract import TOOL_NAMES
from skeleton.personas.llm import FakeLLMClient
from skeleton.personas.loader import load_persona, load_personas

PERSONA_DIR = Path(__file__).resolve().parents[2] / "debt-collector" / "personas"
COLLECTOR = PERSONA_DIR / "collector.toml"

LEVELS = importlib.import_module("debt-collector.interest").LEVELS
notice = importlib.import_module("debt-collector.notice")


def _has_digit(text: str) -> bool:
    return any(ch.isdigit() for ch in text)


def test_loads_without_warnings() -> None:
    p = load_persona(COLLECTOR)
    assert p.name == "collector"
    assert p.theme == "ledger"
    assert p.warnings == []


def test_no_digit_in_any_text_field() -> None:
    p = load_persona(COLLECTOR)
    texts = [p.voice, p.decline_line, *p.goals, *p.example_lines]
    assert [t for t in texts if _has_digit(t)] == []


def test_allowed_tools_subset_of_contract() -> None:
    p = load_persona(COLLECTOR)
    assert p.allowed_tools and set(p.allowed_tools) <= TOOL_NAMES
    assert {"list_findings", "get_file_facts", "read_lines"} <= set(p.allowed_tools)


def test_directory_with_only_collector(tmp_path: Path) -> None:
    shutil.copy(COLLECTOR, tmp_path / "collector.toml")
    assert list(load_personas(tmp_path)) == ["collector"]
    assert list(load_personas(PERSONA_DIR)) == ["collector"]


def test_create_app_starts_with_collector(tmp_path: Path) -> None:
    app = create_app(store=tmp_path, llm=FakeLLMClient([]), persona_dir=PERSONA_DIR)
    with TestClient(app):
        pass


def test_voice_wording_rules() -> None:
    voice = load_persona(COLLECTOR).voice
    for level in LEVELS:
        assert level in voice
    assert "figures" in voice and "I suspect" in voice
    assert "no tool result supports" in voice
    assert "Never state a principal, an interest or a total" in voice


def test_decline_line_has_no_digit() -> None:
    assert not _has_digit(load_persona(COLLECTOR).decline_line)


@pytest.mark.parametrize("level", LEVELS)
def test_notice_question_per_level(level: str) -> None:
    q = notice.notice_question(level)
    assert level in q
    assert not _has_digit(q)


def test_notice_question_rejects_unknown_word() -> None:
    with pytest.raises(ValueError):
        notice.notice_question("threat")
