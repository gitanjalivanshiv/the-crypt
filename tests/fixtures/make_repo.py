"""Deterministic tiny git repos for tests.

Every commit takes an explicit date and author, so the same script always
gives the same SHAs. No network, no dependence on today's date or on the
user's git configuration.

    repo = FixtureRepo(tmp_path / "r")
    repo.commit({"a.py": "x = 1\\n"}, author="Ann <ann@example.com>", date="2024-01-01T00:00:00+0000")
    repo.rename("a.py", "b.py", date="2024-01-02T00:00:00+0000")
    repo.branch("feature")
    repo.commit({"c.py": "c\\n"}, date="2024-01-03T00:00:00+0000")
    repo.checkout("main")
    repo.commit({"d.py": "d\\n"}, date="2024-01-04T00:00:00+0000")
    repo.merge("feature", date="2024-01-05T00:00:00+0000")
"""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

DEFAULT_AUTHOR = "Test User <test@example.com>"
DEFAULT_BRANCH = "main"
_BASE_DATE = datetime(2024, 1, 1, tzinfo=UTC)


def _parse_author(author: str) -> tuple[str, str]:
    name, _, rest = author.partition("<")
    return name.strip(), rest.rstrip(">").strip()


class FixtureRepo:
    """A git repository in `path` driven by a script of commits."""

    def __init__(self, path: Path, branch: str = DEFAULT_BRANCH) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self._tick = 0
        self._git("init", "-q", "-b", branch)

    # -- low level -------------------------------------------------------
    def _env(self, author: str, date: str) -> dict[str, str]:
        name, email = _parse_author(author)
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("GIT_") and k not in ("HOME", "XDG_CONFIG_HOME")
        }
        env.update(
            {
                "HOME": str(self.path),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_AUTHOR_NAME": name,
                "GIT_AUTHOR_EMAIL": email,
                "GIT_COMMITTER_NAME": name,
                "GIT_COMMITTER_EMAIL": email,
                "GIT_AUTHOR_DATE": date,
                "GIT_COMMITTER_DATE": date,
                "TZ": "UTC",
                "LC_ALL": "C",
            }
        )
        return env

    def _git(
        self,
        *args: str,
        author: str = DEFAULT_AUTHOR,
        date: str | None = None,
    ) -> str:
        date = date or self._next_date()
        cmd = [
            "git",
            "-c", "commit.gpgsign=false",
            "-c", "tag.gpgsign=false",
            "-c", f"core.hooksPath={os.devnull}",
            "-c", "core.autocrlf=false",
            "-c", "init.defaultBranch=main",
            *args,
        ]
        result = subprocess.run(
            cmd,
            cwd=self.path,
            env=self._env(author, date),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout

    def _next_date(self) -> str:
        """Scripted fallback date: one day after the previous fallback."""
        self._tick += 1
        return (_BASE_DATE + timedelta(days=self._tick)).strftime("%Y-%m-%dT%H:%M:%S+0000")

    # -- scripting API ---------------------------------------------------
    def commit(
        self,
        files: dict[str, str] | None = None,
        *,
        message: str = "commit",
        author: str = DEFAULT_AUTHOR,
        date: str | None = None,
        delete: list[str] | None = None,
    ) -> str:
        """Write `files`, remove `delete`, commit, and return the SHA."""
        for rel, content in (files or {}).items():
            target = self.path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        for rel in delete or []:
            (self.path / rel).unlink()
        self._git("add", "-A")
        self._git("commit", "-q", "--allow-empty", "--no-verify", "-m", message,
                  author=author, date=date)
        return self.head()

    def rename(
        self,
        old: str,
        new: str,
        *,
        message: str | None = None,
        author: str = DEFAULT_AUTHOR,
        date: str | None = None,
    ) -> str:
        """`git mv` old to new and commit; returns the SHA."""
        (self.path / new).parent.mkdir(parents=True, exist_ok=True)
        self._git("mv", old, new)
        self._git("commit", "-q", "--no-verify", "-m", message or f"rename {old} -> {new}",
                  author=author, date=date)
        return self.head()

    def branch(self, name: str) -> None:
        """Create and switch to a new branch at HEAD."""
        self._git("checkout", "-q", "-b", name)

    def checkout(self, name: str) -> None:
        self._git("checkout", "-q", name)

    def merge(
        self,
        branch: str,
        *,
        message: str | None = None,
        author: str = DEFAULT_AUTHOR,
        date: str | None = None,
    ) -> str:
        """Non-fast-forward merge of `branch` into the current branch."""
        self._git("merge", "-q", "--no-ff", "--no-verify", "-m",
                  message or f"merge {branch}", branch, author=author, date=date)
        return self.head()

    def head(self) -> str:
        return self._git("rev-parse", "HEAD").strip()

    def log_shas(self) -> list[str]:
        return self._git("log", "--topo-order", "--format=%H").split()
