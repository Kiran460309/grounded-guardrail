"""
GroundingGuard — Strands InterventionHandler that intercepts every tool call
and asks Decider 2B a typed question per argument before allowing execution.

ARCHITECTURE RULE: nothing here imports /agent. This module is standalone.

NOTE: The exact Strands InterventionHandler API is verified against the installed
strands-agents package. If the API changes, only this file needs updating.
"""
from __future__ import annotations

import uuid
import time
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from .question import Turn, Q_GROUNDED, Q_RECIPIENT, Q_INJECTION, render_state
from .decider_client import DeciderClient, MockDecider, Decision
from .thresholds import Thresholds, gate, combine

logger = logging.getLogger(__name__)

# ── Argument routing ────────────────────────────────────────────────────────
# Which typed question to use for each (tool, arg) pair. Defaults to Q_GROUNDED.
ARG_QUESTION_MAP: dict[str, Any] = {
    "send_email.to":         Q_RECIPIENT,
    "send_payment.recipient":Q_RECIPIENT,
    "create_event.attendee": Q_RECIPIENT,
}


@dataclass
class ArgDecision:
    name: str
    value: str
    question_id: str
    label: str
    confidence: float
    latency_ms: float
    gate_result: str   # execute | block | clarify
    evidence_turns: list[int] = field(default_factory=list)


@dataclass
class DecisionEvent:
    """Structured event emitted per tool call — also the SSE + SQLite contract."""
    event_id: str
    ts: str
    session_id: str
    turn: int
    tool: str
    guard_enabled: bool
    policy: dict
    arguments: list[ArgDecision]
    outcome: str          # executed | blocked | clarify | blocked_by_policy
    message_to_agent: str
    backend: str

    def to_dict(self) -> dict:
        import datetime
        return {
            "event_id": self.event_id,
            "ts": self.ts,
            "session_id": self.session_id,
            "turn": self.turn,
            "tool": self.tool,
            "guard_enabled": self.guard_enabled,
            "policy": self.policy,
            "arguments": [
                {
                    "name": a.name,
                    "value": a.value,
                    "question": a.question_id,
                    "label": a.label,
                    "confidence": a.confidence,
                    "latency_ms": a.latency_ms,
                    "gate_result": a.gate_result,
                    "evidence_turns": a.evidence_turns,
                }
                for a in self.arguments
            ],
            "outcome": self.outcome,
            "message_to_agent": self.message_to_agent,
            "backend": self.backend,
        }


class GroundingGuard:
    """
    Drop-in grounding guard for Strands agents.

    Usage (10 lines):
        from patterns.grounding_guard.handler import GroundingGuard
        from patterns.grounding_guard.decider_client import MockDecider
        from patterns.grounding_guard.thresholds import Thresholds

        guard = GroundingGuard(decider=MockDecider(), thresholds=Thresholds())
        # Wire into Strands agent (exact API verified against strands-agents package):
        # agent = Agent(model=..., tools=[...], before_tool_call=guard.intercept)

    See README.md for the real wiring once InterventionHandler API is confirmed.
    """

    def __init__(
        self,
        decider: DeciderClient | None = None,
        thresholds: Thresholds | None = None,
        policy_fn: Callable[[str, dict], dict] | None = None,
        event_callback: Callable[[DecisionEvent], None] | None = None,
        session_id: str = "default",
        enabled: bool = True,
    ):
        self.decider = decider or MockDecider()
        self.thresholds = thresholds or Thresholds()
        self.policy_fn = policy_fn   # optional: inject the policy.limits.authorize fn
        self.event_callback = event_callback
        self.session_id = session_id
        self.enabled = enabled
        self._turn = 0

    # ── Main intercept (called by Strands before each tool call) ────────────
    def intercept(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        history: list[Turn],
    ) -> tuple[str, str, DecisionEvent]:
        """
        Returns (outcome, message_to_agent, event).
        outcome: 'execute' | 'block' | 'clarify' | 'blocked_by_policy'
        """
        import datetime
        self._turn += 1
        event_id = str(uuid.uuid4())
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

        # ── 1. Policy gate (deterministic, free, no Decider call) ───────────
        policy_result = {"result": "allow", "rule": "", "detail": ""}
        if self.policy_fn:
            from policy.limits import PolicyResult
            pr: PolicyResult = self.policy_fn(tool_name, tool_args)
            policy_result = {"result": pr.result, "rule": pr.rule, "detail": pr.detail}
            if pr.result == "deny":
                event = DecisionEvent(
                    event_id=event_id, ts=ts,
                    session_id=self.session_id, turn=self._turn,
                    tool=tool_name, guard_enabled=self.enabled,
                    policy=policy_result, arguments=[],
                    outcome="blocked_by_policy",
                    message_to_agent=f"Policy blocked: {pr.rule} — {pr.detail}",
                    backend=self.decider.backend,
                )
                self._emit(event)
                return "blocked_by_policy", event.message_to_agent, event

        # ── 2. Guard disabled — pass through ────────────────────────────────
        if not self.enabled:
            event = DecisionEvent(
                event_id=event_id, ts=ts,
                session_id=self.session_id, turn=self._turn,
                tool=tool_name, guard_enabled=False,
                policy=policy_result, arguments=[],
                outcome="executed",
                message_to_agent="Guard disabled — executing without check.",
                backend=self.decider.backend,
            )
            self._emit(event)
            return "executed", "", event

        # ── 3. Per-argument Decider calls ────────────────────────────────────
        evidence_turns = [t.index for t in history if t.source == "user"]
        arg_decisions: list[ArgDecision] = []
        per_arg_gates: list[str] = []

        for arg_name, arg_value in tool_args.items():
            q_key = f"{tool_name}.{arg_name}"
            typed_q = ARG_QUESTION_MAP.get(q_key, Q_GROUNDED)
            state = render_state(history, tool_name, arg_name, str(arg_value))
            question_text = typed_q.template.format(value=str(arg_value), arg=arg_name)

            try:
                dec: Decision = self.decider.decide(state, question_text, typed_q)
                g = gate(dec.label, dec.confidence, q_key, self.thresholds)
            except Exception as exc:
                logger.error("Decider error: %s", exc)
                if self.thresholds.fail_closed:
                    dec = Decision("ambiguous", 0.0, 0.0, "error")
                    g = "clarify"
                else:
                    dec = Decision("grounded", 1.0, 0.0, "error_open")
                    g = "execute"

            arg_decisions.append(ArgDecision(
                name=arg_name, value=str(arg_value),
                question_id=typed_q.id,
                label=dec.label, confidence=dec.confidence,
                latency_ms=dec.latency_ms, gate_result=g,
                evidence_turns=evidence_turns,
            ))
            per_arg_gates.append(g)

        # ── 4. Combine per-arg outcomes and normalise to event-contract vocab ────
        _raw = combine(per_arg_gates) if per_arg_gates else "execute"
        # Internal gate vocab: execute/block/clarify → public contract: executed/blocked/clarify
        _norm = {"execute": "executed", "block": "blocked"}
        final = _norm.get(_raw, _raw)

        # ── 5. Build message to agent ────────────────────────────────────────
        if final == "blocked":
            blocked_args = [a for a in arg_decisions if a.gate_result == "block"]
            details = "; ".join(
                f"{a.name}={a.value!r} ({a.label}, conf={a.confidence:.2f})"
                for a in blocked_args
            )
            msg = f"BLOCKED: argument(s) not grounded in user statements — {details}"
        elif final == "clarify":
            ambig = [a for a in arg_decisions if a.gate_result == "clarify"]
            details = "; ".join(f"{a.name}={a.value!r}" for a in ambig)
            msg = (
                f"CLARIFY NEEDED: I'm not confident {details} is supported "
                f"by what you said. Could you confirm?"
            )
        else:
            msg = ""

        event = DecisionEvent(
            event_id=event_id, ts=ts,
            session_id=self.session_id, turn=self._turn,
            tool=tool_name, guard_enabled=True,
            policy=policy_result, arguments=arg_decisions,
            outcome=final,
            message_to_agent=msg,
            backend=self.decider.backend,
        )
        self._emit(event)
        return final, msg, event

    def _emit(self, event: DecisionEvent) -> None:
        logger.debug("DecisionEvent: %s", json.dumps(event.to_dict()))
        if self.event_callback:
            self.event_callback(event)
