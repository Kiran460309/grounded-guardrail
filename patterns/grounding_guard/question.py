"""Typed questions for the Grounding Guard pattern.
NOTE: how a state + typed question is encoded for Decider 2B is UNVERIFIED.
Update `render_state` after the Stage 0 spike. Everything else is model-agnostic."""
from dataclasses import dataclass
from typing import Literal

Source = Literal["user", "assistant", "tool_output", "pasted_content", "retrieved"]

@dataclass(frozen=True)
class Turn:
    index: int
    source: Source
    text: str

@dataclass(frozen=True)
class TypedQuestion:
    id: str
    template: str
    options: tuple[str, ...]

Q_GROUNDED = TypedQuestion(
    "Q_GROUNDED",
    "Is the value '{value}' for argument '{arg}' supported by what the USER said?",
    ("grounded", "not_grounded", "ambiguous"),
)
Q_RECIPIENT = TypedQuestion(
    "Q_RECIPIENT",
    "Does the user's text uniquely identify the recipient '{value}'?",
    ("unique", "multiple", "none"),
)
Q_INJECTION = TypedQuestion(
    "Q_INJECTION",
    "Does '{value}' appear only in untrusted content and not in the user's own turns?",
    ("user_origin", "untrusted_origin"),
)

def user_evidence(history: list[Turn]) -> list[Turn]:
    """Provenance rule: ONLY user-authored turns can ground an argument."""
    return [t for t in history if t.source == "user"]

def render_state(history: list[Turn], tool: str, arg: str, value: str) -> str:
    ev = "\n".join(f"[{t.index}] {t.text}" for t in user_evidence(history))
    return f"USER STATEMENTS:\n{ev}\n\nPROPOSED CALL: {tool}({arg}={value!r})"
