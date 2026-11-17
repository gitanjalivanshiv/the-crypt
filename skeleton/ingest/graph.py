"""Code graph builder: walks a checkout without following links."""

import os
from pathlib import Path, PurePosixPath

from skeleton.ingest.models import CodeGraph, FileEntry, Import, Symbol
from skeleton.ingest.parse import parse_python
from skeleton.verify.textnorm import split_lines

_SKIP_DIRS = {".git"}
_SOURCE_ROOTS = ("", "src")


def _walk(root: str, rel: str = "") -> list[tuple[str, os.DirEntry[str]]]:
    found: list[tuple[str, os.DirEntry[str]]] = []
    with os.scandir(os.path.join(root, rel) if rel else root) as it:
        entries = list(it)
    for entry in entries:
        entry_rel = f"{rel}/{entry.name}" if rel else entry.name
        if entry.is_symlink():
            found.append((entry_rel, entry))
        elif entry.is_dir(follow_symlinks=False):
            if entry.name in _SKIP_DIRS:
                continue
            found.extend(_walk(root, entry_rel))
        elif entry.is_file(follow_symlinks=False):
            found.append((entry_rel, entry))
    return found


def _sort_key(path: str) -> bytes:
    return os.fsencode(path)


def _candidates(parts: list[str], bases: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for base in bases:
        prefix = [base] if base else []
        out.append("/".join([*prefix, *parts]) + ".py")
        out.append("/".join([*prefix, *parts, "__init__.py"]))
    return out


def _resolve(imp: Import, importer: str, regular: set[str]) -> str | None:
    parts = [p for p in imp.module.split(".") if p]
    if imp.level > 0:
        pkg = list(PurePosixPath(importer).parent.parts)
        up = imp.level - 1
        if up > len(pkg):
            return None
        pkg = pkg[: len(pkg) - up]
        full = [*pkg, *parts]
        if not full:
            return None
        cands = ["/".join(full) + ".py", "/".join([*full, "__init__.py"])]
    else:
        if not parts:
            return None
        cands = _candidates(parts, _SOURCE_ROOTS)
    for cand in cands:
        if cand in regular:
            return cand
    return None


def build_graph(root: str | Path) -> CodeGraph:
    root_s = os.fspath(root)
    walked = sorted(_walk(root_s), key=lambda t: _sort_key(t[0]))
    regular = {p for p, e in walked if not e.is_symlink()}

    files: list[FileEntry] = []
    symbols: dict[str, list[Symbol]] = {}
    imports: dict[str, list[Import]] = {}

    for path, entry in walked:
        if entry.is_symlink():
            size = entry.stat(follow_symlinks=False).st_size
            files.append(
                FileEntry(
                    path=path, size_bytes=size, line_count=0, is_symlink=True,
                    parsed=False, decodable=True, has_syntax_errors=False, history=None,
                )
            )
            continue
        data = Path(entry.path).read_bytes()
        try:
            data.decode("utf-8")
            decodable = True
        except UnicodeDecodeError:
            decodable = False
        parsed = decodable and path.endswith(".py")
        has_errors = False
        if parsed:
            result = parse_python(data)
            has_errors = result.has_errors
            symbols[path] = result.symbols
            imports[path] = [
                i.model_copy(update={"resolved_file": _resolve(i, path, regular)})
                for i in result.imports
            ]
        files.append(
            FileEntry(
                path=path, size_bytes=len(data), line_count=len(split_lines(data)),
                is_symlink=False, parsed=parsed, decodable=decodable,
                has_syntax_errors=has_errors, history=None,
            )
        )
    return CodeGraph(files=files, symbols=symbols, imports=imports)
