import json
from pathlib import Path

import pytest

from skeleton.mcp import contract

CONTRACT_JSON = Path(contract.__file__).with_name("contract.json")


def test_committed_json_equals_regenerated() -> None:
    assert CONTRACT_JSON.read_text() == contract.render_contract_json()


def test_tool_names() -> None:
    assert contract.TOOL_NAMES == {"get_snapshot", "list_findings", "get_file_facts", "read_lines"}


@pytest.mark.parametrize("name", sorted(contract.TOOL_NAMES))
def test_every_tool_has_input_and_output_schema(name: str) -> None:
    tool = json.loads(CONTRACT_JSON.read_text())["tools"][name]
    assert tool["input_schema"]["type"] == "object"
    assert tool["output_schema"]["type"] == "object"
    assert "snapshot_id" in tool["output_schema"]["properties"]


@pytest.mark.parametrize("code", list(contract.ErrorCode))
def test_every_error_code_has_description(code: contract.ErrorCode) -> None:
    assert contract.ERROR_DESCRIPTIONS[code].strip()
    assert code.value in json.loads(CONTRACT_JSON.read_text())["error_codes"]


def test_limits_and_metric_docs() -> None:
    data = json.loads(CONTRACT_JSON.read_text())
    assert data["limits"] == {"default_limit": 20, "max_limit": 100, "read_lines_max": 200}
    assert "commits since the current path was created" in data["metrics"]["commit_count"]
    assert "days since this line last changed" in data["metrics"]["age_days"].lower()
