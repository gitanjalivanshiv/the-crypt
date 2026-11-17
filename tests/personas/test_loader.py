from pathlib import Path

import pytest

from skeleton.mcp.contract import TOOL_NAMES
from skeleton.personas.loader import PersonaError, load_persona, load_personas

FIXTURES = Path(__file__).parent.parent / "fixtures" / "personas"

VALID = """
name = "example"
display_name = "Example Ghost"
voice = "Dry."
goals = ["Cite facts"]
allowed_tools = ["list_findings"]
example_lines = ["It sleeps."]
decline_line = "Silent."
"""


def write(tmp_path: Path, text: str, name: str = "p.toml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def fail(tmp_path: Path, text: str) -> PersonaError:
    with pytest.raises(PersonaError) as info:
        load_persona(write(tmp_path, text))
    return info.value


def test_valid_load(tmp_path):
    p = load_persona(write(tmp_path, VALID))
    assert p.name == "example" and p.theme is None and p.warnings == []


def test_invalid_toml(tmp_path):
    assert fail(tmp_path, "name = ").field == "<toml>"


def test_missing_field(tmp_path):
    assert fail(tmp_path, VALID.replace('voice = "Dry."\n', "")).field == "voice"


def test_wrong_type(tmp_path):
    assert fail(tmp_path, VALID.replace('goals = ["Cite facts"]', 'goals = "x"')).field == "goals"


def test_empty_goals_and_example_lines(tmp_path):
    assert fail(tmp_path, VALID.replace('["Cite facts"]', "[]")).field == "goals"
    assert fail(tmp_path, VALID.replace('["It sleeps."]', "[]")).field == "example_lines"


def test_unknown_key_including_verify(tmp_path):
    err = fail(tmp_path, VALID + "verify = false\n")
    assert err.field == "verify"


def test_unknown_tool_named(tmp_path):
    err = fail(tmp_path, VALID.replace("list_findings", "launch_missiles"))
    assert "launch_missiles" in err.message and err.field.startswith("allowed_tools")


def test_blank_strings(tmp_path):
    assert fail(tmp_path, VALID.replace('"Dry."', '"   "')).field == "voice"
    assert fail(tmp_path, VALID.replace('["Cite facts"]', '[" "]')).field.startswith("goals")


def test_empty_allowed_tools_legal(tmp_path):
    p = load_persona(write(tmp_path, VALID.replace('["list_findings"]', "[]")))
    assert p.allowed_tools == []


def test_digit_warnings(tmp_path):
    p = load_persona(write(tmp_path, VALID.replace('["It sleeps."]', '["No digits", "Age 847"]')))
    assert len(p.warnings) == 1 and "847" in p.warnings[0]


def test_duplicate_names_error(tmp_path):
    write(tmp_path, VALID, "a.toml")
    write(tmp_path, VALID, "b.toml")
    with pytest.raises(PersonaError) as info:
        load_personas(tmp_path)
    assert info.value.field == "name"


def test_third_fixture_loads_without_skeleton_edit():
    p = load_persona(FIXTURES / "third.toml")
    assert p.name == "third"
    assert set(p.allowed_tools) <= TOOL_NAMES
    assert "third" in load_personas(FIXTURES)
