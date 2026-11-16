"""Claim verification, steps 1 to 5 of design 6.3. Never raises."""

import re

from skeleton.verify.citation import CitationOk, verify_citation
from skeleton.verify.codes import ReasonCode, render_message
from skeleton.verify.textnorm import normalise_line, normalise_quote
from skeleton.verify.models import (
    Banishment,
    BanishmentTarget,
    Citation,
    CitationTarget,
    Figure,
    FigureTarget,
    NumberTarget,
    SnapshotView,
    VerifiedClaim,
    VerifyConfig,
)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _ban(
    view: SnapshotView,
    text: str,
    attempt: int,
    code: ReasonCode,
    value: str = "",
    target: BanishmentTarget | None = None,
    message: str | None = None,
) -> Banishment:
    return Banishment(
        claim_text=text,
        reason=code,
        message=message if message is not None else render_message(code, value),
        target=target,
        attempt=attempt,
        snapshot_id=view.snapshot_id,
    )


def _parse_figure(item: object) -> Figure | None:
    if not isinstance(item, dict):
        return None
    fid, key, value = item.get("finding_id"), item.get("key"), item.get("value")
    if not isinstance(fid, str) or not isinstance(key, str) or not _is_number(value):
        return None
    return Figure(finding_id=fid, key=key, value=value)  # type: ignore[arg-type]


_SPANS = re.compile(r'"[^"]*"|“[^”]*”|`[^`]*`')
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_TOKEN = re.compile(r"(?<![A-Za-z0-9_])\d+(?:\.\d+)?(?![A-Za-z0-9_])")


def _figure_tokens(value: int | float) -> set[str]:
    if isinstance(value, int):
        return {str(value)}
    tokens = {repr(value)}
    if value.is_integer():
        tokens.add(str(int(value)))
    return tokens


def _first_unbacked_token(
    view: SnapshotView,
    text: str,
    citations: list[Citation],
    figures: list[Figure],
    cfg: VerifyConfig,
) -> str | None:
    quote_lines = [
        line for c in citations if c.quote is not None for line in normalise_quote(c.quote)
    ]

    def blank_exempt(match: re.Match[str]) -> str:
        content = normalise_line(match.group(0)[1:-1])
        if any(content in line for line in quote_lines):
            return " "
        return match.group(0)

    scanned = _SPANS.sub(blank_exempt, text)
    sid = view.snapshot_id
    if sid:
        scanned = scanned.replace(sid, " ")
        if len(sid) >= 7:
            scanned = scanned.replace(sid[:7], " ")
    scanned = _THOUSANDS.sub("", scanned)

    allowed: set[str] = set(cfg.allowed_numbers)
    for fig in figures:
        allowed |= _figure_tokens(fig.value)
    for c in citations:
        allowed |= {str(c.line_start), str(c.line_end)}
    for m in _TOKEN.finditer(scanned):
        if m.group(0) not in allowed:
            return m.group(0)
    return None


def verify_claim(
    view: SnapshotView, raw: object, attempt: int, cfg: VerifyConfig
) -> VerifiedClaim | Banishment:
    text = raw.get("text") if isinstance(raw, dict) else None
    claim_text = text if isinstance(text, str) else ""

    def malformed() -> Banishment:
        return _ban(view, claim_text, attempt, ReasonCode.MALFORMED)

    # 1. malformed
    if not isinstance(raw, dict) or not isinstance(text, str) or text == "":
        return malformed()
    guess = raw.get("guess", False)
    raw_citations = raw.get("citations", [])
    raw_figures = raw.get("figures", [])
    if not isinstance(guess, bool):
        return malformed()
    if not isinstance(raw_citations, list) or not isinstance(raw_figures, list):
        return malformed()
    figures: list[Figure] = []
    for item in raw_figures:
        fig = _parse_figure(item)
        if fig is None:
            return malformed()
        figures.append(fig)
    if guess and figures:  # D2
        return malformed()

    # 2. uncited_claim
    if not guess and not raw_citations:
        return _ban(view, text, attempt, ReasonCode.UNCITED_CLAIM)

    # 3. first failing citation
    citations: list[Citation] = []
    for i, item in enumerate(raw_citations):
        result = verify_citation(view, item)
        if not isinstance(result, CitationOk):
            target: CitationTarget | None = None
            if isinstance(item, dict):
                try:
                    target = CitationTarget(
                        index=i,
                        citation=Citation(
                            file=item["file"],
                            line_start=item["line_start"],
                            line_end=item["line_end"],
                            quote=item.get("quote"),
                        ),
                    )
                except (KeyError, ValueError):
                    target = None
            return _ban(
                view, text, attempt, result.code, target=target, message=result.message
            )
        citations.append(result.citation)

    # 4 and 5. figures
    cited_files = {c.file for c in citations}
    for i, fig in enumerate(figures):
        fig_target = FigureTarget(index=i, figure=fig)
        found = view.finding(fig.finding_id)
        if found is None or fig.key not in found[1] or found[1][fig.key] != fig.value:
            return _ban(
                view,
                text,
                attempt,
                ReasonCode.FIGURE_NOT_IN_METRICS,
                fig.finding_id,
                fig_target,
            )
        if found[0] not in cited_files:
            return _ban(
                view, text, attempt, ReasonCode.FIGURE_NOT_CITED, found[0], fig_target
            )

    # 6. prose digit scan
    token = _first_unbacked_token(view, text, citations, figures, cfg)
    if token is not None:
        return _ban(
            view,
            text,
            attempt,
            ReasonCode.UNBACKED_NUMBER,
            token,
            NumberTarget(token=token),
        )

    return VerifiedClaim(
        kind="guess" if guess else "fact",
        text=text,
        citations=tuple(citations),
        figures=tuple(figures),
    )
