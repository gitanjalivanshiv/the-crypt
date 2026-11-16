"""Hypothesis strategies for grounded-answer tests."""

from dataclasses import dataclass, field

from hypothesis import strategies as st

from skeleton.verify.textnorm import normalise_line, split_lines

# Full Unicode range. Surrogates cannot be encoded to UTF-8, so they are excluded.
_TEXT = st.text(
    alphabet=st.characters(exclude_categories=("Cs",), exclude_characters="\r\n"),
    max_size=30,
)
_TRAILING = st.text(alphabet=" \t\f\v", max_size=3)
_TERMINATORS = st.sampled_from(["\n", "\r\n", "\r"])


@st.composite
def file_contents(draw) -> bytes:
    """UTF-8 bytes with mixed terminators and trailing whitespace; may be empty."""
    n = draw(st.integers(min_value=0, max_value=8))
    out = []
    for _ in range(n):
        out.append(draw(_TEXT) + draw(_TRAILING))
        out.append(draw(_TERMINATORS))
    if n and draw(st.booleans()):
        out.pop()  # no final terminator
    return "".join(out).encode("utf-8")


@dataclass(frozen=True)
class Tree:
    files: dict[str, bytes]
    findings: dict[str, tuple[str, dict[str, int | float]]] = field(default_factory=dict)


_METRICS = st.dictionaries(
    st.sampled_from(["commit_count", "age_days", "ratio", "todo_count_in_file"]),
    st.one_of(st.integers(0, 10_000), st.floats(0, 1000, allow_nan=False, allow_infinity=False)),
    min_size=1,
    max_size=3,
)


@st.composite
def file_trees(draw) -> Tree:
    """A tree with at least one file that has a line, plus findings on its files."""
    n = draw(st.integers(1, 4))
    files: dict[str, bytes] = {}
    for i in range(n):
        folder = draw(st.sampled_from(["", "d0/", "d1/sub/"]))
        files[f"{folder}f{i}.txt"] = draw(file_contents())
    first = next(iter(files))
    if not split_lines(files[first]):
        files[first] = b"seed line\n"
    findings = {}
    for i, path in enumerate(files):
        if draw(st.booleans()):
            findings[f"churn:{path}:{i}"] = (path, draw(_METRICS))
    return Tree(files=files, findings=findings)


def _non_empty_paths(tree: Tree) -> list[str]:
    return [p for p, d in tree.files.items() if split_lines(d)]


@st.composite
def valid_citation(draw, tree: Tree) -> dict:
    """A raw citation dict that is in range and whose quote matches the file."""
    path = draw(st.sampled_from(_non_empty_paths(tree)))
    lines = split_lines(tree.files[path])
    start = draw(st.integers(1, len(lines)))
    end = draw(st.integers(start, len(lines)))
    quote = "\n".join(normalise_line(b.decode("utf-8")) for b in lines[start - 1 : end])
    return {"file": path, "line_start": start, "line_end": end, "quote": quote}


@st.composite
def valid_figure(draw, findings) -> dict:
    """A raw figure dict referencing a real finding metric. findings must be non-empty."""
    fid = draw(st.sampled_from(sorted(findings)))
    _, metrics = findings[fid]
    key = draw(st.sampled_from(sorted(metrics)))
    return {"finding_id": fid, "key": key, "value": metrics[key]}


@st.composite
def answer(draw, tree: Tree) -> dict:
    """A raw answer object whose claims are all valid for tree.

    Claim text contains no digits, so the digit scan has nothing to flag.
    """
    claims = []
    for _ in range(draw(st.integers(1, 3))):
        cites = [draw(valid_citation(tree)) for _ in range(draw(st.integers(1, 2)))]
        claim: dict = {"text": "This code does something notable", "citations": cites}
        if draw(st.booleans()):
            claim["guess"] = True
        else:
            cited = {c["file"] for c in cites}
            usable = {k: v for k, v in tree.findings.items() if v[0] in cited}
            if usable and draw(st.booleans()):
                claim["figures"] = [draw(valid_figure(usable))]
        claims.append(claim)
    return {"claims": claims}
