import os

from skeleton.ingest.graph import build_graph


def _w(root, rel, data):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data if isinstance(data, bytes) else data.encode())


def _by_path(g):
    return {f.path: f for f in g.files}


def test_symlinks_recorded_not_followed(tmp_path):
    _w(tmp_path, "real/a.py", "x = 1\n")
    os.symlink("real/a.py", tmp_path / "link.py")
    os.symlink("real", tmp_path / "linkdir")
    g = build_graph(tmp_path)
    f = _by_path(g)
    assert f["link.py"].is_symlink and not f["link.py"].parsed
    assert f["linkdir"].is_symlink
    assert not any(p.startswith("linkdir/") for p in f)
    assert "link.py" not in g.symbols
    assert not f["real/a.py"].is_symlink


def test_git_dir_skipped_and_non_py_unparsed(tmp_path):
    _w(tmp_path, ".git/config", "x")
    _w(tmp_path, "README.md", "hi\n")
    g = build_graph(tmp_path)
    assert [x.path for x in g.files] == ["README.md"]
    assert g.files[0].parsed is False
    assert g.files[0].history is None


def test_non_utf8_file(tmp_path):
    _w(tmp_path, "bad.py", b"x = '\xff'\n\n")
    f = _by_path(build_graph(tmp_path))["bad.py"]
    assert not f.decodable and not f.parsed
    assert f.line_count == 2


def test_syntax_error_keeps_symbols(tmp_path):
    _w(tmp_path, "s.py", "def ok():\n    pass\n\ndef broken(:\n")
    g = build_graph(tmp_path)
    assert _by_path(g)["s.py"].has_syntax_errors
    assert "ok" in [s.name for s in g.symbols["s.py"]]
    assert g.symbols["s.py"][0].kind == "module"
    assert g.symbols["s.py"][0].line_start == 1


def test_empty_file(tmp_path):
    _w(tmp_path, "e.py", b"")
    assert _by_path(build_graph(tmp_path))["e.py"].line_count == 0


def test_import_resolution(tmp_path):
    _w(tmp_path, "pkg/__init__.py", "")
    _w(tmp_path, "pkg/a.py", "import pkg.b\nfrom . import c\nfrom .b import x\nimport os\nfrom .. import z\n")
    _w(tmp_path, "pkg/b.py", "x = 1\n")
    _w(tmp_path, "src/lib/__init__.py", "")
    _w(tmp_path, "m.py", "import lib\nimport pkg\n")
    g = build_graph(tmp_path)
    got = {(i.module, i.level): i.resolved_file for i in g.imports["pkg/a.py"]}
    assert got[("pkg.b", 0)] == "pkg/b.py"
    assert got[("b", 1)] == "pkg/b.py"
    assert got[("os", 0)] is None
    assert got[("", 1)] == "pkg/__init__.py" or got[("", 1)] is None
    assert got[("", 2)] is None
    m = {i.module: i.resolved_file for i in g.imports["m.py"]}
    assert m == {"lib": "src/lib/__init__.py", "pkg": "pkg/__init__.py"}


def test_deterministic_and_sorted(tmp_path):
    _w(tmp_path, "b.py", "import a\n")
    _w(tmp_path, "a.py", "def f(): pass\n")
    _w(tmp_path, "Z/c.py", "x=1\n")
    one = build_graph(tmp_path).model_dump_json()
    two = build_graph(tmp_path).model_dump_json()
    assert one == two
    assert [f.path for f in build_graph(tmp_path).files] == ["Z/c.py", "a.py", "b.py"]
