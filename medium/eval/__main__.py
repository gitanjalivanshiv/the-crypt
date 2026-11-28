"""Banishment-rate harness (design 5.1).

``python -m medium.eval --runs 2 [--max-turns N] [--questions PATH]``

Drives the same app and ``/ask`` route the demo uses. It builds no prompt, parses no
model output and verifies no claim itself. This is a live run (real provider, real
clone), so it is never collected by pytest; only its unit tests run by default.
"""

import argparse
import dataclasses
import json
import sys
import tempfile
import time
import tomllib
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from medium.eval.metrics import Question, Report, breaches, compute, render
from medium.plan import SECTION_QUESTIONS
from providers.errors import ProviderError
from providers.select import client_from_env, max_tokens_from_env, with_max_tokens
from skeleton.api.app import ApiConfig, create_app
from skeleton.personas.llm import LLMClient
from skeleton.verify.models import AnswerResult

ROOT = Path(__file__).resolve().parents[2]
PERSONA_DIR = ROOT / "medium" / "personas"
DEFAULT_QUESTIONS = Path(__file__).resolve().parent / "questions.toml"
DEFAULT_RUNS_DIR = Path(__file__).resolve().parent / "runs"
PATIENT_JSON = ROOT / "demo" / "patient.json"
PERSONA = "ghost"
MAX_CONSECUTIVE_PROVIDER_ERRORS = 3

EXIT_OK, EXIT_BREACH, EXIT_ABORT = 0, 1, 2


def load_questions(path: Path) -> list[tuple[Question, str]]:
    """Return (Question, text) pairs; ``plan:*`` ids resolve from SECTION_QUESTIONS."""
    out: list[tuple[Question, str]] = []
    for q in tomllib.loads(path.read_text(encoding="utf-8"))["questions"]:
        qid = q["id"]
        if qid.startswith("plan:"):
            text = SECTION_QUESTIONS[qid.split(":", 1)[1]]
        else:
            text = q["text"]
        out.append((Question(qid, q["category"]), text))
    return out


def _load_patient() -> dict[str, Any]:
    primary = json.loads(PATIENT_JSON.read_text(encoding="utf-8"))["primary"]
    return {"clone_url": primary["clone_url"], "commit": primary["commit"]}


def _default_client() -> LLMClient:
    return client_from_env()


def _provider_failed(r: AnswerResult) -> bool:
    """The flow swallows generator exceptions into a decline whose attempts all failed
    with ``generator_error``; that is how a provider outage shows through ``/ask``."""
    return (
        r.status == "declined"
        and bool(r.attempts)
        and all(a.outcome == "failed" and a.failure_kind == "generator_error" for a in r.attempts)
    )


def report_to_dict(report: Report) -> dict[str, Any]:
    return dataclasses.asdict(report)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m medium.eval", description=__doc__)
    p.add_argument("--runs", type=int, default=2)
    p.add_argument("--max-turns", type=int, default=None)
    p.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    p.add_argument(
        "--delay-s",
        type=float,
        default=None,
        help=(
            "Seconds to wait between turns. A free-tier quota is per minute and one turn "
            "makes several calls, so an unpaced run bursts straight through the limit. "
            "Retrying afterwards is the fallback; not tripping it is the fix. Use 0 for a "
            "paid key."
        ),
    )
    return p.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
    *,
    client: LLMClient | None = None,
    ingest_fn: Callable[..., Any] | None = None,
    patient: dict[str, Any] | None = None,
    out_dir: Path | None = None,
    out: Callable[[str], None] = print,
) -> int:
    args = _parse_args(argv)
    questions = load_questions(args.questions)
    if args.max_turns is not None:
        questions = questions[: args.max_turns]
    patient = patient or _load_patient()
    out_dir = Path(out_dir) if out_dir is not None else DEFAULT_RUNS_DIR
    llm = with_max_tokens(
        client if client is not None else _default_client(), max_tokens_from_env()
    )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    exit_code = EXIT_OK
    with tempfile.TemporaryDirectory(prefix="medium-eval-") as tmp:
        extra: dict[str, Any] = {"ingest_fn": ingest_fn} if ingest_fn is not None else {}
        app = create_app(
            store=Path(tmp),
            llm=llm,
            persona_dir=PERSONA_DIR,
            cfg=ApiConfig(allow_retained=True),
            **extra,
        )
        with TestClient(app) as http:
            r = http.post(
                "/snapshots",
                json={"url": patient["clone_url"], "sha": patient["commit"], "intent": "retained"},
            )
            if r.status_code != 201:
                out(f"ingest failed: HTTP {r.status_code} {r.text}")
                return EXIT_ABORT
            ref = r.json()["ref"]
            snapshot_id = r.json()["snapshot_id"]

            # A real run paces itself against the per-minute quota; an injected client
            # is a test and must not sleep. The flag overrides either.
            delay_s = args.delay_s if args.delay_s is not None else (
                0.0 if client is not None else 15.0
            )
            for n in range(1, args.runs + 1):
                run_code = _one_run(
                    http, ref, snapshot_id, questions, n, stamp, out_dir, args.questions, out,
                    delay_s=delay_s,
                )
                exit_code = max(exit_code, run_code)
                if run_code == EXIT_ABORT:
                    break
    return exit_code


def _one_run(
    http: TestClient,
    ref: str,
    snapshot_id: str,
    questions: list[tuple[Question, str]],
    n: int,
    stamp: str,
    out_dir: Path,
    questions_path: Path,
    out: Callable[[str], None],
    delay_s: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    results: list[tuple[Question, AnswerResult]] = []
    errors: list[dict[str, str]] = []
    consecutive = 0
    aborted: str | None = None
    for index, (q, text) in enumerate(questions):
        if index and delay_s > 0:
            sleep(delay_s)
        failure: str | None = None
        answer: AnswerResult | None = None
        try:
            resp = http.post(f"/snapshots/{ref}/ask", json={"persona": PERSONA, "question": text})
        except ProviderError as exc:
            failure = f"ProviderError: {exc}"
        else:
            if resp.status_code != 200:
                consecutive = 0
                errors.append({"id": q.id, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"})
                continue
            answer = AnswerResult.model_validate(resp.json())
            if _provider_failed(answer):
                causes = dict.fromkeys(a.failure_detail or "" for a in answer.attempts)
                failure = "ProviderError: every attempt failed with generator_error: " + "; ".join(
                    causes
                )
        if failure is None:
            consecutive = 0
            assert answer is not None
            results.append((q, answer))
            continue
        # A provider-error turn has no verdict to measure, so it stays out of the metrics.
        consecutive += 1
        errors.append({"id": q.id, "error": failure})
        if consecutive >= MAX_CONSECUTIVE_PROVIDER_ERRORS:
            aborted = f"{consecutive} consecutive provider errors"
            break

    report = compute(results)
    found = breaches(report)
    record = {
        "run": n,
        "snapshot_id": snapshot_id,
        "questions_file": questions_path.name,
        "aborted": aborted,
        "errors": errors,
        "results": [
            {"id": q.id, "category": q.category, "result": r.model_dump(mode="json")}
            for q, r in results
        ],
        "report": report_to_dict(report),
        "breaches": [dataclasses.asdict(b) for b in found],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{stamp}-{n}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    out(f"run {n}: {path}")
    out(render(report))
    for b in found:
        out(f"BREACH {b.scope} {b.metric} = {b.value:.3f} (band {b.band})")
    if errors:
        out(f"{len(errors)} turn(s) failed: " + ", ".join(e["id"] for e in errors))
        for e in errors:
            out(f"  {e['id']}: {e['error']}")
    if aborted:
        out(f"ABORTED: {aborted}")
        return EXIT_ABORT
    return EXIT_BREACH if (found or errors) else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
