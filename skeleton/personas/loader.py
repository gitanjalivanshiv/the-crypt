"""Persona config schema and TOML loader (design 7.1, 7.2)."""
import tomllib
from pathlib import Path
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    computed_field,
    field_validator,
)

from skeleton.mcp.contract import TOOL_NAMES

NonBlank = Annotated[str, StringConstraints(strip_whitespace=False)]


class PersonaError(Exception):
    """A persona file could not be loaded."""

    def __init__(self, file: Path, field: str, message: str) -> None:
        super().__init__(f"{file}: {field}: {message}")
        self.file = file
        self.field = field
        self.message = message


class Persona(BaseModel):
    """Persona config. There is deliberately no field touching verification."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    name: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    display_name: NonBlank
    voice: NonBlank
    goals: list[NonBlank] = Field(min_length=1)
    allowed_tools: list[NonBlank]
    example_lines: list[NonBlank] = Field(min_length=1)
    decline_line: NonBlank
    theme: str | None = None

    @field_validator(
        "display_name", "voice", "decline_line", "theme", "goals", "allowed_tools", "example_lines"
    )
    @classmethod
    def _non_blank(cls, value: str | list[str] | None) -> str | list[str] | None:
        items = [value] if isinstance(value, str) else (value or [])
        if any(not item.strip() for item in items):
            raise ValueError("must not be blank")
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def warnings(self) -> list[str]:
        """Example lines containing a digit; models copy them and the verifier rejects them."""
        return [
            f"example_lines entry contains a digit: {line!r}"
            for line in self.example_lines
            if any(ch.isdigit() for ch in line)
        ]


def load_persona(path: Path, *, known_tools: frozenset[str] = TOOL_NAMES) -> Persona:
    path = Path(path)
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise PersonaError(path, "<toml>", str(exc)) from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise PersonaError(path, "<file>", str(exc)) from exc
    try:
        persona = Persona.model_validate(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        field = ".".join(str(part) for part in first["loc"]) or "<root>"
        raise PersonaError(path, field, first["msg"]) from exc
    for index, tool in enumerate(persona.allowed_tools):
        if tool not in known_tools:
            raise PersonaError(
                path, f"allowed_tools.{index}", f"unknown tool {tool!r}; known: {sorted(known_tools)}"
            )
    return persona


def load_personas(
    directory: Path, *, known_tools: frozenset[str] = TOOL_NAMES
) -> dict[str, Persona]:
    directory = Path(directory)
    result: dict[str, Persona] = {}
    sources: dict[str, Path] = {}
    for path in sorted(directory.glob("*.toml")):
        persona = load_persona(path, known_tools=known_tools)
        if persona.name in result:
            raise PersonaError(
                path, "name", f"duplicate persona name {persona.name!r} (also in {sources[persona.name]})"
            )
        result[persona.name] = persona
        sources[persona.name] = path
    return result
