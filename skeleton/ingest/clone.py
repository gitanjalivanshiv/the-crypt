"""Hardened git clone, SHA pin and limit enforcement (design section 4.3)."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from skeleton.ingest.models import IngestCode, IngestError, IngestLimits

POLL_INTERVAL_S = 0.5


def _env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return env


def _hardening(allow_protocols: str) -> list[str]:
    return [
        "-c", f"core.hooksPath={os.devnull}",
        "-c", "core.fsmonitor=false",
        "-c", "protocol.allow=never",
        "-c", f"protocol.{allow_protocols}.allow=always",
        "-c", "http.followRedirects=false",
    ]


def _dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _run_clone(cmd: list[str], dest: Path, limits: IngestLimits) -> None:
    """Run the clone, enforcing time and size limits. Raises IngestError."""
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(
            cmd,
            env=_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=err,
            start_new_session=True,
        )
        done = threading.Event()
        breach: list[IngestError] = []

        def watch() -> None:
            start = time.monotonic()
            while not done.wait(POLL_INTERVAL_S):
                if time.monotonic() - start > limits.clone_timeout_s:
                    breach.append(
                        IngestError(
                            IngestCode.clone_timeout,
                            f"clone exceeded {limits.clone_timeout_s}s",
                        )
                    )
                elif _dir_size(dest) > limits.max_bytes:
                    breach.append(
                        IngestError(
                            IngestCode.size_limit_exceeded,
                            f"clone exceeded {limits.max_bytes} bytes",
                        )
                    )
                if breach:
                    _kill_group(proc)
                    return

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        try:
            rc = proc.wait()
        finally:
            done.set()
            watcher.join()
            _kill_group(proc)
        if breach:
            raise breach[0]
        if rc != 0:
            err.seek(0)
            msg = err.read().decode("utf-8", "replace").strip()[:500]
            raise IngestError(IngestCode.invalid_source, f"git clone failed: {msg}")
        if _dir_size(dest) > limits.max_bytes:
            raise IngestError(
                IngestCode.size_limit_exceeded,
                f"clone exceeded {limits.max_bytes} bytes",
            )


def _git(
    git_bin: str, dest: Path, allow: str, *args: str
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [git_bin, *_hardening(allow), "-C", str(dest), *args],
        env=_env(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
    )


def _pin(git_bin: str, dest: Path, allow: str, ref: str | None, sha: str | None) -> str:
    if sha:
        probe = _git(git_bin, dest, allow, "cat-file", "-e", f"{sha}^{{commit}}")
        target = sha
        what = f"commit {sha}"
    else:
        target = ref or "HEAD"
        probe = None
        what = f"ref {target}"
    if probe is None or probe.returncode == 0:
        res = _git(git_bin, dest, allow, "rev-parse", "--verify", f"{target}^{{commit}}")
        if res.returncode == 0:
            return res.stdout.decode().strip()
    raise IngestError(IngestCode.ref_not_found, f"{what} not found in repository")


def clone_and_pin(
    url: str,
    *,
    ref: str | None,
    sha: str | None,
    limits: IngestLimits,
    dest: Path,
    git_bin: str = "git",
    _allow_protocols: str = "https",
) -> str:
    """Clone `url` into `dest` without checkout, pin a commit, return its SHA.

    On any failure `dest` is removed.
    """
    dest = Path(dest)
    try:
        _run_clone(
            [git_bin, *_hardening(_allow_protocols), "clone", "--no-checkout", url, str(dest)],
            dest,
            limits,
        )
        pinned = _pin(git_bin, dest, _allow_protocols, ref, sha)
        res = _git(git_bin, dest, _allow_protocols, "checkout", "--detach", pinned)
        if res.returncode != 0:
            raise IngestError(
                IngestCode.invalid_source,
                f"checkout failed: {res.stderr.decode('utf-8', 'replace').strip()[:500]}",
            )
        res = _git(git_bin, dest, _allow_protocols, "ls-files", "-z")
        count = len([p for p in res.stdout.split(b"\0") if p])
        if count > limits.max_files:
            raise IngestError(
                IngestCode.file_limit_exceeded,
                f"{count} files exceeds limit of {limits.max_files}",
            )
        return pinned
    except BaseException:
        shutil.rmtree(dest, ignore_errors=True)
        raise
