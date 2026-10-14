"""policy — deterministic authorization. Separate from grounding. Never merge."""
from .limits import authorize, PolicyResult
__all__ = ["authorize", "PolicyResult"]
