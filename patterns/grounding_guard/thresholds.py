from dataclasses import dataclass, field

@dataclass
class Thresholds:
    default_grounded: float = 0.80        # min confidence to accept 'grounded'
    default_not_grounded: float = 0.60    # min confidence to hard-block
    per_arg: dict[str, float] = field(default_factory=dict)  # e.g. {"send_payment.amount": 0.95}
    fail_closed: bool = True              # decider error -> clarify (True) or allow (False, dev only)

def gate(label: str, confidence: float, key: str, t: Thresholds) -> str:
    """Return 'execute' | 'block' | 'clarify' for ONE argument."""
    need = t.per_arg.get(key, t.default_grounded)
    if label == "grounded" and confidence >= need:
        return "execute"
    if label == "not_grounded" and confidence >= t.default_not_grounded:
        return "block"
    return "clarify"

def combine(per_arg: list[str]) -> str:
    if "block" in per_arg: return "block"
    if "clarify" in per_arg: return "clarify"
    return "execute"
