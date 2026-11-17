"""Python source parsing with tree-sitter: symbols, imports, comments."""
from dataclasses import dataclass, field

import tree_sitter_python
from tree_sitter import Language, Node, Parser

from skeleton.ingest.models import Import, Symbol
from skeleton.verify.textnorm import split_lines

SUPPORTED_GRAMMARS = ["python"]

_PARSER = Parser(Language(tree_sitter_python.language()))


@dataclass(frozen=True)
class ParseResult:
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    has_errors: bool = False
    docstring_range: tuple[int, int] | None = None
    comments: list[tuple[int, str]] = field(default_factory=list)


def _text(node: Node) -> str:
    return (node.text or b"").decode("utf-8", errors="replace")


def _line_end(node: Node) -> int:
    row, col = node.end_point
    if col == 0 and row > node.start_point[0]:
        return row
    return row + 1


def _dotted(node: Node) -> tuple[str, int]:
    """Return (module, level) for a module_name node."""
    if node.type == "relative_import":
        level = 0
        module = ""
        for child in node.children:
            if child.type == "import_prefix":
                level = _text(child).count(".")
            elif child.type == "dotted_name":
                module = _text(child)
        return module, level
    return _text(node), 0


def _name_of(node: Node) -> str:
    """Name for a dotted_name or aliased_import (the imported name, not the alias)."""
    if node.type == "aliased_import":
        inner = node.child_by_field_name("name")
        return _text(inner) if inner is not None else ""
    return _text(node)


def _docstring_range(root: Node) -> tuple[int, int] | None:
    for child in root.named_children:
        if child.type == "comment":
            continue
        if child.type == "expression_statement" and child.named_children:
            first = child.named_children[0]
            if first.type == "string":
                return first.start_point[0] + 1, _line_end(first)
        return None
    return None


def parse_python(data: bytes) -> ParseResult:
    tree = _PARSER.parse(data)
    root = tree.root_node
    symbols = [Symbol(name="<module>", kind="module", line_start=1, line_end=len(split_lines(data)))]
    imports: list[Import] = []
    comments: list[tuple[int, str]] = []

    # Stack of (node, kind of nearest enclosing definition or None).
    stack: list[tuple[Node, str | None]] = [(root, None)]
    while stack:
        node, enclosing = stack.pop()
        kind_here = enclosing
        if node.type == "comment":
            comments.append((node.start_point[0] + 1, _text(node)))
        elif node.type in ("class_definition", "function_definition"):
            name_node = node.child_by_field_name("name")
            if name_node is not None and _text(name_node):
                if node.type == "class_definition":
                    kind = "class"
                else:
                    kind = "method" if enclosing == "class" else "function"
                symbols.append(
                    Symbol(
                        name=_text(name_node),
                        kind=kind,  # type: ignore[arg-type]
                        line_start=node.start_point[0] + 1,
                        line_end=_line_end(node),
                    )
                )
            kind_here = "class" if node.type == "class_definition" else "function"
        elif node.type == "import_statement":
            line = node.start_point[0] + 1
            for child in node.children_by_field_name("name"):
                module = _name_of(child)
                if module:
                    imports.append(
                        Import(module=module, names=[], line=line, level=0, resolved_file=None)
                    )
        elif node.type == "import_from_statement":
            module_node = node.child_by_field_name("module_name")
            module, level = _dotted(module_node) if module_node is not None else ("", 0)
            names = [n for n in (_name_of(c) for c in node.children_by_field_name("name")) if n]
            if any(c.type == "wildcard_import" for c in node.children):
                names.append("*")
            imports.append(
                Import(
                    module=module,
                    names=names,
                    line=node.start_point[0] + 1,
                    level=level,
                    resolved_file=None,
                )
            )
        for child in reversed(node.children):
            stack.append((child, kind_here))

    symbols.sort(key=lambda s: (s.line_start, s.name))
    imports.sort(key=lambda i: i.line)
    comments.sort()
    return ParseResult(
        symbols=symbols,
        imports=imports,
        has_errors=root.has_error,
        docstring_range=_docstring_range(root),
        comments=comments,
    )
