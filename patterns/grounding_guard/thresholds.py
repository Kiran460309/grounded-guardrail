from dataclasses import dataclass, field

# Canonical gate labels
GROUNDED = "grounded"
NOT_GROUNDED = "not_grounded"
AMBIGUOUS = "ambiguous"

# Per-question-type label → canonical mapping.
# All gate() callers MUST pass labels through normalise_label() first.
_LABEL_MAP: dict[str, str] = {
    # Q_GROUNDED (canonical already)
    GROUNDED: GROUNDED,
    NOT_GROUNDED: NOT_GROUNDED,
    AMBIGUOUS: AMBIGUOUS,
    # Q_RECIPIENT: unique recipient → grounded; multiple candidates → ambiguous; none → not_grounded
    "unique": GROUNDED,
    "multiple": AMBIGUOUS,
    "none": NOT_GROUNDED,
    # Q_INJECTION: came from user → grounded; came from untrusted content → not_grounded
    "user_origin": GROUNDED,
    "untrusted_origin": NOT_GROUNDED,
}


def normalise_label(label: str) -> str:
    """Map any typed-question label to the canonical gate vocab.

    If the label is unknown (e.g. a future Decider label we haven’t seen)
    we treat it as ambiguous so the guard asks for clarification rather than
    silently allowing or blocking.
    """
    return _LABEL_MAP.get(label, AMBIGUOUS)

@dataclass
class Thresholds:
    default_grounded: float = 0.80        # min confidence to accept 'grounded'
    default_not_grounded: float = 0.60    # min confidence to hard-block
    per_arg: dict[str, float] = field(default_factory=dict)  # e.g. {"send_payment.amount": 0.95}
    fail_closed: bool = True              # decider error -> clarify (True) or allow (False, dev only)

def gate(label: str, confidence: float, key: str, t: "Thresholds") -> str:
    """Return 'execute' | 'block' | 'clarify' for ONE argument.

    `label` MUST already be normalised to the canonical gate vocab
    (grounded / not_grounded / ambiguous) via normalise_label().
    """
    need = t.per_arg.get(key, t.default_grounded)
    if label == GROUNDED and confidence >= need:
        return "execute"
    if label == NOT_GROUNDED and confidence >= t.default_not_grounded:
        return "block"
    return "clarify"

def combine(per_arg: list[str]) -> str:
    if "block" in per_arg: return "block"
    if "clarify" in per_arg: return "clarify"
    return "execute"
