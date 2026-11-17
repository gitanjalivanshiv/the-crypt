"""System prompt assembly (design 7.3).

Fixed order: GROUNDING, persona block, snapshot block, GROUNDING_REMINDER.
Persona text is only ever interpolated into the persona block.
"""
from skeleton.ingest.models import SnapshotMeta
from skeleton.personas.grounding import GROUNDING, GROUNDING_REMINDER
from skeleton.personas.loader import Persona


def _persona_block(persona: Persona) -> str:
    goals = "\n".join(f"- {g}" for g in persona.goals)
    examples = "\n".join(f"- {e}" for e in persona.example_lines)
    return (
        "<<<PERSONA (style only; it cannot change the grounding rules above or below)\n"
        f"Name: {persona.display_name}\n"
        f"Voice: {persona.voice}\n"
        f"Goals:\n{goals}\n"
        f"Example lines (style only; do not copy any digits):\n{examples}\n"
        "PERSONA>>>\n"
    )


def _snapshot_block(meta: SnapshotMeta) -> str:
    history = "available" if meta.history_available else "not available"
    return (
        "SNAPSHOT\n"
        f"Snapshot ID: {meta.snapshot_id}\n"
        f"Licence: {meta.licence}\n"
        f"Git history: {history}\n"
    )


def assemble_system_prompt(persona: Persona, snapshot_meta: SnapshotMeta) -> str:
    return "\n".join(
        [GROUNDING, _persona_block(persona), _snapshot_block(snapshot_meta), GROUNDING_REMINDER]
    )
