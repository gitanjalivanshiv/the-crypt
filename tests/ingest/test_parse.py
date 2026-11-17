from skeleton.ingest.parse import SUPPORTED_GRAMMARS, parse_python


def _syms(r):
    return [(s.name, s.kind, s.line_start, s.line_end) for s in r.symbols]


def test_smoke_and_grammars():
    assert SUPPORTED_GRAMMARS == ["python"]
    r = parse_python(b"x = 1\n")
    assert not r.has_errors


def test_nested_classes_and_methods():
    src = b"class A:\n    class B:\n        def g(self): pass\n    def f(self):\n        def inner(): pass\n\ndef top(): pass\n"
    r = parse_python(src)
    assert _syms(r) == [
        ("<module>", "module", 1, 7),
        ("A", "class", 1, 5),
        ("B", "class", 2, 3),
        ("g", "method", 3, 3),
        ("f", "method", 4, 5),
        ("inner", "function", 5, 5),
        ("top", "function", 7, 7),
    ]


def test_decorated_definitions():
    r = parse_python(b"@dec\ndef f(): pass\n\nclass A:\n    @property\n    def p(self): pass\n")
    kinds = {s.name: s.kind for s in r.symbols}
    assert kinds["f"] == "function"
    assert kinds["p"] == "method"


def test_imports_relative_and_parenthesised():
    src = b"import os, a.b as c\nfrom . import x\nfrom ..pkg.mod import (a,\n    b as bb)\nfrom m import *\n"
    r = parse_python(src)
    got = [(i.module, i.names, i.line, i.level) for i in r.imports]
    assert got == [
        ("os", [], 1, 0),
        ("a.b", [], 1, 0),
        ("", ["x"], 2, 1),
        ("pkg.mod", ["a", "b"], 3, 2),
        ("m", ["*"], 5, 0),
    ]


def test_syntax_error_recovers():
    r = parse_python(b"def ok(): pass\ndef broken(:\n    pass\nclass K: pass\n")
    assert r.has_errors
    names = {s.name for s in r.symbols}
    assert {"ok", "K"} <= names


def test_marker_in_string_not_a_comment():
    r = parse_python(b's = "# TODO not a comment"\n# TODO real\n')
    assert r.comments == [(2, "# TODO real")]


def test_docstring_range():
    r = parse_python(b'"""doc\nmore"""\nx = 1\n')
    assert r.docstring_range == (1, 2)
    assert parse_python(b"x = 1\n").docstring_range is None


def test_empty_input():
    r = parse_python(b"")
    assert not r.has_errors
    assert _syms(r) == [("<module>", "module", 1, 0)]
    assert r.imports == [] and r.comments == []
