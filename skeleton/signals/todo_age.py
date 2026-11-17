"""todo_age: TODO/FIXME/HACK/XXX markers in comments, aged by git blame.

Blame semantics (D10): `age_days` is "days since this line last changed". Blame
returns the commit that last touched the line, so rewording a TODO resets its
age. Age is measured against the pinned commit time, never the wall clock.
"""

import os
import re
import subprocess
from typing import ClassVar

from skeleton.ingest.parse import parse_python
from skeleton.ingest.snapshot import Snapshot
from skeleton.signals.models import AnalyzerOutput, Finding, SignalsConfig
from skeleton.verify.textnorm import normalised_lines

_MARKER = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
_HEADER = re.compile(r"^[0-9a-f]{40} \d+ (\d+)(?: \d+)?$")
_BLAME_TIMEOUT_S = 120


def todo_severity(age_days: int, saturation: int) -> float:
    return min(1.0, max(0, age_days) / saturation)


def _git_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        }
    )
    return env


def parse_blame(output: bytes) -> dict[int, int]:
    """Parse `git blame --porcelain` into {final line number: committer-time}.

    The `committer-time` header appears only the first time a commit is seen,
    so commit times are remembered and applied to later lines.
    """
    times: dict[str, int] = {}
    by_line: dict[int, int] = {}
    sha = ""
    line_no = 0
    for raw in output.split(b"\n"):
        line = raw.decode("utf-8", "replace")
        if line.startswith("\t"):
            if sha in times:
                by_line[line_no] = times[sha]
            continue
        m = _HEADER.match(line)
        if m:
            sha, line_no = line[:40], int(m.group(1))
        elif line.startswith("committer-time "):
            times[sha] = int(line.split(" ", 1)[1])
    return by_line


def _blame(snapshot: Snapshot, path: str) -> dict[int, int]:
    result = subprocess.run(
        ["git", "blame", "--porcelain", snapshot.meta.snapshot_id, "--", path],
        cwd=snapshot.repo,
        env=_git_env(),
        capture_output=True,
        check=True,
        timeout=_BLAME_TIMEOUT_S,
    )
    return parse_blame(result.stdout)


class TodoAge:
    name: ClassVar[str] = "todo_age"
    needs_history: ClassVar[bool] = True
    requires: ClassVar[frozenset[str]] = frozenset()

    def analyze(self, snapshot: Snapshot, cfg: SignalsConfig) -> AnalyzerOutput:
        pinned = snapshot.meta.pinned_commit_time
        if pinned is None:
            return AnalyzerOutput([])
        pinned_ts = int(pinned.timestamp())

        # path -> [(line, normalised line)], only files that have markers
        found: dict[str, list[tuple[int, str]]] = {}
        for entry in sorted(snapshot.graph.files, key=lambda e: e.path):
            if not entry.path.endswith(".py") or entry.is_symlink or not entry.decodable:
                continue
            data = snapshot.read_bytes(entry.path)
            if data is None:
                continue
            try:
                lines = normalised_lines(data)
            except UnicodeDecodeError:
                continue
            hits = sorted(
                {
                    ln
                    for ln, text in parse_python(data).comments
                    if _MARKER.search(text) and 1 <= ln <= len(lines)
                }
            )
            if hits:
                found[entry.path] = [(ln, lines[ln - 1]) for ln in hits]

        total = sum(len(v) for v in found.values())
        taken: list[str] = []
        running = 0
        for path, markers in found.items():
            if running + len(markers) > cfg.todo_max_markers:
                break
            running += len(markers)
            taken.append(path)
        truncated = len(taken) < len(found)

        findings: list[Finding] = []
        for path in taken:
            blame = _blame(snapshot, path)
            count = len(found[path])
            for ln, evidence in found[path]:
                committed = blame.get(ln)
                if committed is None:
                    continue
                age = max(0, (pinned_ts - committed) // 86400)
                findings.append(
                    Finding(
                        analyzer=self.name,
                        file=path,
                        line_start=ln,
                        line_end=ln,
                        evidence=evidence,
                        severity=todo_severity(age, cfg.todo_saturation_days),
                        metrics={"age_days": age, "todo_count_in_file": count},
                    )
                )
        return AnalyzerOutput(
            findings, truncated=truncated, total_found=total if truncated else None
        )
