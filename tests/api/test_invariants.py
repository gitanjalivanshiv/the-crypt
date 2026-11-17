"""API invariants (R9.1, R9.6, R9.7): read-only surface, one AnswerResult, no env or key access."""

import ast
import json
from pathlib import Path

from skeleton.api.app import ApiConfig, create_app
from skeleton.personas.llm import FakeLLMClient
from tests.api.test_read_routes import persona_dir, store  # noqa: F401

API_DIR = Path(__file__).resolve().parents[2] / "skeleton" / "api"

POST_ROUTES = {"/snapshots", "/snapshots/{ref}/ask"}
ALLOWED_METHODS = {"get", "post", "delete"}


def _openapi(store: Path, persona_dir: Path) -> dict:  # noqa: F811
    app = create_app(store=store, llm=FakeLLMClient([]), persona_dir=persona_dir, cfg=ApiConfig())
    return app.openapi()


def test_no_write_execute_or_proxy_routes(store: Path, persona_dir: Path) -> None:  # noqa: F811
    doc = _openapi(store, persona_dir)
    posts = set()
    for path, item in doc["paths"].items():
        methods = {m for m in item if m in {"get", "put", "post", "patch", "delete", "head", "options", "trace"}}
        assert methods <= ALLOWED_METHODS, f"{path} exposes {methods - ALLOWED_METHODS}"
        assert "put" not in methods and "patch" not in methods
        if "post" in methods:
            posts.add(path)
    assert posts == POST_ROUTES


def test_answer_result_appears_once(store: Path, persona_dir: Path) -> None:  # noqa: F811
    doc = _openapi(store, persona_dir)
    schemas = doc["components"]["schemas"]
    assert [n for n in schemas if n.startswith("AnswerResult")] == ["AnswerResult"]
    # Only the ask route may return it.
    users = [
        path
        for path, item in doc["paths"].items()
        if '"#/components/schemas/AnswerResult"' in json.dumps(item)
    ]
    assert users == ["/snapshots/{ref}/ask"]


def _env_access(tree: ast.AST) -> list[str]:
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in {"environ", "getenv", "putenv"}:
            hits.append(node.attr)
        elif isinstance(node, ast.Name) and node.id in {"environ", "getenv"}:
            hits.append(node.id)
        elif isinstance(node, ast.ImportFrom) and node.module in {"dotenv", "keyring"}:
            hits.append(node.module)
        elif isinstance(node, ast.Import):
            hits.extend(a.name for a in node.names if a.name in {"dotenv", "keyring"})
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if "api_key" in node.value.lower() or "apikey" in node.value.lower():
                hits.append(node.value)
        elif isinstance(node, (ast.Name, ast.arg)):
            name = node.id if isinstance(node, ast.Name) else node.arg
            if "api_key" in name.lower():
                hits.append(name)
    return hits


def test_api_package_reads_no_env_or_key() -> None:
    files = sorted(API_DIR.glob("*.py"))
    assert files
    for f in files:
        assert _env_access(ast.parse(f.read_text())) == [], f.name
