"""Harness runner (medium R3.4, R3.5, R3.9 to R3.13) with a scripted fake provider."""

import dataclasses
import functools
import json
import re
from pathlib import Path

import pytest

from medium.eval import __main__ as runner
from medium.eval.metrics import breaches, compute, render
from providers.errors import ProviderError
from skeleton.ingest import ingest_url
from skeleton.personas.llm import LLMRequest, LLMResponse
from skeleton.verify.models import AnswerResult
from tests.fixtures.make_repo import FixtureRepo

URL = "https://example.com/owner/repo.git"
MIT = (
    "MIT License\n\nPermission is hereby granted, free of charge, to any person "
    "obtaining a copy of this software, to deal in the Software without restriction.\n"
)
GUESS = LLMResponse(text=json.dumps({"claims": [{"text": "I suspect it is old.", "guess": True}]}))


class _Repeat:
    """Answers every call with the same response; records each request."""

    def __init__(self, response: LLMResponse) -> None:
        self.response = response
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return self.response


class _AlwaysFails:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        raise ProviderError("boom")


@pytest.fixture
def env(tmp_path: Path):
    repo = FixtureRepo(tmp_path / "src")
    repo.commit(
        {"LICENSE": MIT, "a.py": "# TODO: fix\ndef f():\n    pass\n"},
        date="2024-01-01T00:00:00+0000",
    )
    wrapper = tmp_path / "git-wrapper.sh"
    wrapper.write_text(
        "#!/bin/sh\n"
        'for a in "$@"; do\n'
        f'  if [ "$a" = "{URL}" ]; then a="{repo.path}"; fi\n'
        '  set -- "$@" "$a"; shift\n'
        "done\n"
        'exec git "$@"\n'
    )
    wrapper.chmod(0o755)
    ingest = functools.partial(
        ingest_url,
        resolver=lambda _h: ["93.184.216.34"],
        git_bin=str(wrapper),
        _allow_protocols="file",
    )
    return {
        "ingest_fn": ingest,
        "patient": {"clone_url": URL, "commit": repo.head()},
        "out_dir": tmp_path / "runs",
    }


def _run(env, client, *argv, lines=None):
    sink = [] if lines is None else lines
    code = runner.main(list(argv), client=client, out=sink.append, **env)
    return code, sink


def test_every_question_goes_through_ask(env) -> None:
    # The provider is reachable only from /ask, so its recorded requests are the spy.
    client = _Repeat(GUESS)
    _run(env, client, "--runs", "1")
    expected = [text for _, text in runner.load_questions(runner.DEFAULT_QUESTIONS)]
    asked = {m.content for req in client.requests for m in req.messages if m.role == "user"}
    for text in expected:
        assert any(text in a for a in asked), text
    assert len(expected) == 20


def test_all_guess_run_breaches_and_names_bands(env) -> None:
    code, lines = _run(env, _Repeat(GUESS), "--runs", "1", "--max-turns", "5")
    text = "\n".join(lines)
    assert code != 0
    for band in ("guess_share", "all_guess_turns", "verified_share", "banished_turns"):
        assert band in text


def test_three_consecutive_provider_errors_abort(env) -> None:
    client = _AlwaysFails()
    code, lines = _run(env, client, "--runs", "2")
    assert code != 0
    assert "ABORTED" in "\n".join(lines)
    # the flow regenerates once per turn, so each failed turn costs two calls
    assert client.calls == 2 * runner.MAX_CONSECUTIVE_PROVIDER_ERRORS
    files = list(env["out_dir"].glob("*.json"))
    assert len(files) == 1  # the second run never starts
    assert json.loads(files[0].read_text())["aborted"]


def test_run_file_parses_back_to_same_report(env) -> None:
    _, lines = _run(env, _Repeat(GUESS), "--runs", "2", "--max-turns", "4")
    files = sorted(env["out_dir"].glob("*-*.json"))
    assert [f.name.rsplit("-", 1)[1] for f in files] == ["1.json", "2.json"]
    assert re.fullmatch(r"\d{8}T\d{6}Z-[12]\.json", files[0].name)
    data = json.loads(files[0].read_text())
    qs = {q.id: q for q, _ in runner.load_questions(runner.DEFAULT_QUESTIONS)}
    pairs = [(qs[r["id"]], AnswerResult.model_validate(r["result"])) for r in data["results"]]
    report = compute(pairs)
    assert dataclasses.asdict(report) == data["report"]
    assert [dataclasses.asdict(b) for b in breaches(report)] == data["breaches"]
    assert render(report) in "\n".join(lines)


def test_module_imports_no_verifier_internals() -> None:
    src = Path(runner.__file__).read_text()
    for name in ("run_grounded_turn", "verify_claim", "ToolLoopGenerator"):
        assert name not in src, name


def test_provider_failed_turn_records_attempt_cause(env) -> None:
    code, lines = _run(env, _AlwaysFails(), "--runs", "1")
    assert code != 0
    (f,) = env["out_dir"].glob("*.json")
    error = json.loads(f.read_text())["errors"][0]["error"]
    assert error.startswith("ProviderError: every attempt failed with generator_error")
    assert error.endswith("ProviderError: boom")
    assert error.count("boom") == 1  # two identical attempts are listed once
    assert any(line.startswith("  ") and "boom" in line for line in lines)
