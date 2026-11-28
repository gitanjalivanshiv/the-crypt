"""Independence guards: import contracts and the secret guard (R7.1, R7.3, R7.4)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKELETON = ROOT / "skeleton"
PLANTED = SKELETON / "verify" / "_planted_violation.py"


def _lint() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(Path(sys.executable).parent / "lint-imports"), "--config", str(ROOT / ".importlinter")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_import_contracts_hold() -> None:
    result = _lint()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "7 kept, 0 broken" in result.stdout


@pytest.mark.parametrize(
    "source",
    [
        "from skeleton.api import errors\n",  # verify importing the top layer
        "from skeleton.ingest import models\n",  # verify importing a higher layer
        "import medium\n",
        "import providers\n",
        "import debt_collector\n",
        "import anthropic\n",
        "import openai\n",
        "import boto3\n",
        "from google import genai\n",
        "import google.genai\n",
    ],
)
def test_planted_violation_fails_lint(source: str) -> None:
    PLANTED.write_text(source)
    try:
        result = _lint()
    finally:
        PLANTED.unlink(missing_ok=True)
    assert result.returncode != 0, result.stdout
    assert "BROKEN" in result.stdout
    assert not PLANTED.exists()


COLLECTOR = ROOT / "debt-collector"


@pytest.mark.parametrize(
    ("name", "source", "contract"),
    [
        ("medium", "import medium\n", "debt-collector must not import medium"),
        ("sdk_anthropic", "import anthropic\n", "debt-collector must not import a model SDK"),
        ("sdk_google", "from google import genai\n", "debt-collector must not import a model SDK"),
        (
            "surface_citation",
            "import skeleton.verify.citation\n",
            "debt-collector uses only the skeleton public surface",
        ),
        (
            "surface_ingest",
            "from skeleton.ingest import snapshot\n",
            "debt-collector uses only the skeleton public surface",
        ),
        (
            "surface_store",
            "from skeleton.signals import store\n",
            "debt-collector uses only the skeleton public surface",
        ),
    ],
)
def test_planted_collector_violation_names_contract(name: str, source: str, contract: str) -> None:
    planted = COLLECTOR / f"_planted_{name}.py"
    planted.write_text(source)
    try:
        result = _lint()
    finally:
        planted.unlink(missing_ok=True)
    assert result.returncode != 0, result.stdout
    assert f"{contract} BROKEN" in result.stdout, result.stdout
    assert not planted.exists()


# --- secret guard -----------------------------------------------------------

PATTERN = re.compile(r"getenv|\benviron\b|API_KEY")

# (path relative to skeleton/, substring the line must contain). The git
# subprocess environment copies os.environ minus GIT_*; CRYPT_SNAPSHOT is the
# MCP server's snapshot-path variable.
ALLOWED = (
    ("ingest/archive.py", "os.environ.items() if not k.startswith(\"GIT_\")"),
    ("ingest/clone.py", "os.environ.items() if not k.startswith(\"GIT_\")"),
    ("ingest/history.py", "os.environ.items() if not k.startswith(\"GIT_\")"),
    ("signals/todo_age.py", "os.environ.items() if not k.startswith(\"GIT_\")"),
    # Store-directory default for the ingest CLI; not a secret.
    ("ingest/__main__.py", "SKELETON_STORE"),
    ("mcp/server.py", "CRYPT_SNAPSHOT"),
    ("mcp/server.py", "ENV_SNAPSHOT"),
)


def _python_files() -> list[Path]:
    return [p for p in SKELETON.rglob("*.py") if "node_modules" not in p.parts]


def test_no_secret_or_env_reads_outside_allow_list() -> None:
    offenders = []
    for path in _python_files():
        rel = path.relative_to(SKELETON).as_posix()
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not PATTERN.search(line):
                continue
            if any(rel == f and needle in line for f, needle in ALLOWED):
                continue
            offenders.append(f"skeleton/{rel}:{n}: {line.strip()}")
    assert not offenders, "\n".join(offenders)


def test_secret_guard_detects_a_planted_read() -> None:
    planted = SKELETON / "verify" / "_planted_secret.py"
    planted.write_text('import os\nkey = os.getenv("ANTHROPIC_API_KEY")\n')
    try:
        with pytest.raises(AssertionError):
            test_no_secret_or_env_reads_outside_allow_list()
    finally:
        planted.unlink(missing_ok=True)
