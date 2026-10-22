"""
GroundingGuard — grounding guard for Strands agents.

Contains two public classes:

  GroundingGuard   — standalone helper (our own API). Call intercept() from
                     any tool-call hook or test. Used by SimpleGroundedAgent
                     and tests.

  GroundingGuardHandler — REAL Strands InterventionHandler subclass (API
                     verified against strands-agents 1.61.1 installed at
                     .venv/Lib/site-packages/strands). Implements
                     before_tool_call(event: BeforeToolCallEvent) and bridges
                     to GroundingGuard.intercept(). Wire into a Strands Agent
                     via the intervention_handlers argument (see agent/ module).

ARCHITECTURE RULE: nothing here imports /agent. This module is standalone.

NOTE: InterventionHandler API source is at:
  strands.interventions.handler.InterventionHandler
BeforeToolCallEvent source is at:
  strands.hooks.events.BeforeToolCallEvent
These were read directly from site-packages on 2026-10-20. If strands-agents
version changes, grep site-packages/strands for InterventionHandler / hooks again.
"""
from __future__ import annotations

import uuid
import time
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from .question import Turn, Q_GROUNDED, Q_RECIPIENT, Q_INJECTION, Q_BINDING, render_state
from .decider_client import DeciderClient, MockDecider, Decision
from .thresholds import Thresholds, gate, combine, normalise_label

logger = logging.getLogger(__name__)

# ── Argument routing ────────────────────────────────────────────────────────
# Which typed question to use for each (tool, arg) pair. Defaults to Q_GROUNDED.
ARG_QUESTION_MAP: dict[str, Any] = {
    "send_email.to":         Q_RECIPIENT,
    "send_payment.recipient":Q_RECIPIENT,
    "create_event.attendee": Q_RECIPIENT,
}

# Per-tool list of arguments that must be grounded before the tool executes.
# Arguments NOT in this list are not sent to Decider (they pass through).
# Keeping the list minimal reduces latency and avoids false blocks on
# purely mechanical args (e.g. currency, message-id) that the LLM fills in.
GUARDED_ARGS: dict[str, set[str]] = {
    "send_email":    {"to", "subject", "body"},
    "send_payment":  {"recipient", "amount"},
    "create_event":  {"attendee", "date", "time"},
    "set_reminder":  {"text", "time"},
    # Any tool not listed here has ALL its args guarded (safe default).
}


def _normalise_value(value: Any) -> str:
    """Normalise a tool-argument value to a stable string for Decider.

    * Floats that are whole numbers are displayed as ints (50.0 -> '50').
    * Other floats are rendered with full precision.
    * Everything else uses str().
    """
    if isinstance(value, float):
        if value != value:          # NaN
            return "nan"
        if value in (float("inf"), float("-inf")):
            return str(value)
        if value == int(value):
            return str(int(value))
    return str(value)


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
    binding: dict | None = None

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
            "binding": self.binding,
        }


class GroundingGuard:
    """
    Standalone grounding guard helper.

    This class owns the core guard logic (policy → per-argument Decider
    questions → gate → event). It exposes intercept() as a plain method so
    SimpleGroundedAgent and tests can call it without depending on Strands.

    To wire into a real Strands Agent, use GroundingGuardHandler (below)
    which subclasses the verified InterventionHandler ABC and delegates to
    this class.

    Usage:
        guard = GroundingGuard(decider=MockDecider(), thresholds=Thresholds())
        outcome, msg, event = guard.intercept(tool_name, tool_args, history)
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
            if pr.result == "needs_confirm":
                # needs_confirm is a policy signal, not a grounding block.
                # Surface it as a clarify outcome so the agent asks the user
                # for explicit confirmation before proceeding.
                msg = (
                    f"CONFIRM NEEDED: {pr.detail}. "
                    f"Please ask the user to explicitly confirm before retrying."
                )
                event = DecisionEvent(
                    event_id=event_id, ts=ts,
                    session_id=self.session_id, turn=self._turn,
                    tool=tool_name, guard_enabled=self.enabled,
                    policy=policy_result, arguments=[],
                    outcome="clarify",
                    message_to_agent=msg,
                    backend=self.decider.backend,
                )
                self._emit(event)
                return "clarify", msg, event

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

        # ── 3. Batch Decider questions — one request per tool call ──────────────
        # Build the shared state once (all args share the same user-evidence prefix).
        # Then batch all guarded arguments into a single decide_many() call.
        evidence_turns = [t.index for t in history if t.source == "user"]

        # Filter to only guarded arguments for this tool.
        tool_guard_set = GUARDED_ARGS.get(tool_name, None)  # None → guard all
        guarded_items = [
            (arg_name, arg_value)
            for arg_name, arg_value in tool_args.items()
            if tool_guard_set is None or arg_name in tool_guard_set
        ]

        # Build question specs for decide_many() — keyed by "arg_name" plus optional "__binding__".
        state = render_state(history, tool_name, "(batch)", "(multiple)")
        questions_spec: dict[str, dict[str, Any]] = {}
        meta: dict[str, tuple[str, Any, Any]] = {}  # key -> (normalised_val, typed_q, q_key)

        for arg_name, arg_value in guarded_items:
            norm_val = _normalise_value(arg_value)
            q_key = f"{tool_name}.{arg_name}"
            typed_q = ARG_QUESTION_MAP.get(q_key, Q_GROUNDED)
            question_text = typed_q.template.format(value=norm_val, arg=arg_name)
            questions_spec[arg_name] = {
                "type": "noul",
                "instructions": question_text,
            }
            meta[arg_name] = (norm_val, typed_q, q_key)

        # Whole-call binding question (evaluates argument combination as a single action)
        binding_key = "__binding__"
        binding_call_summary = ", ".join(f"{name}='{_normalise_value(val)}'" for name, val in guarded_items)
        if len(guarded_items) >= 2:
            binding_text = Q_BINDING.template.format(tool=tool_name, call_summary=binding_call_summary)
            questions_spec[binding_key] = {
                "type": "noul",
                "instructions": binding_text,
            }
            meta[binding_key] = (binding_call_summary, Q_BINDING, f"{tool_name}.__binding__")

        # Send the batch (or fall back to per-call if MockDecider / missing decide_many).
        arg_decisions: list[ArgDecision] = []
        per_arg_gates: list[str] = []
        binding_info: dict | None = None

        if guarded_items:
            try:
                if hasattr(self.decider, "decide_many"):
                    batch_results = self.decider.decide_many(state, questions_spec)
                    # decide_many may raise NotImplementedError (HttpDecider Stage A(b))
                    # — fall through to per-call path in that case.
                else:
                    raise AttributeError("decide_many not available")
            except (NotImplementedError, AttributeError):
                # Fall back: call decide() once per question (MockDecider path).
                batch_results = {}
                for q_name, (norm_val, typed_q, q_key) in meta.items():
                    if q_name == binding_key:
                        arg_state = render_state(history, tool_name, "call", norm_val)
                        question_text = typed_q.template.format(tool=tool_name, call_summary=norm_val)
                    else:
                        arg_state = render_state(history, tool_name, q_name, norm_val)
                        question_text = typed_q.template.format(value=norm_val, arg=q_name)
                    try:
                        batch_results[q_name] = self.decider.decide(
                            arg_state, question_text, typed_q
                        )
                    except Exception as exc:
                        logger.error("Decider error for %s.%s: %s", tool_name, q_name, exc)
                        batch_results[q_name] = (
                            Decision("ambiguous", 0.0, 0.0, "decider_error")
                            if self.thresholds.fail_closed
                            else Decision("grounded", 1.0, 0.0, "error_open")
                        )
            except Exception as exc:
                logger.error("Decider batch error: %s", exc)
                # Fail-closed: treat all as ambiguous.
                batch_results = {
                    q_name: Decision("ambiguous", 0.0, 0.0, "decider_error")
                    for q_name in meta
                }

            # 1. Per-argument decisions
            for arg_name, arg_value in guarded_items:
                norm_val, typed_q, q_key = meta[arg_name]
                dec: Decision = batch_results.get(
                    arg_name,
                    Decision("ambiguous", 0.0, 0.0, "decider_error")
                    if self.thresholds.fail_closed
                    else Decision("grounded", 1.0, 0.0, "error_open"),
                )
                canonical = normalise_label(dec.label)
                g = gate(canonical, dec.confidence, q_key, self.thresholds)
                arg_decisions.append(ArgDecision(
                    name=arg_name, value=norm_val,
                    question_id=typed_q.id,
                    label=dec.label, confidence=dec.confidence,
                    latency_ms=dec.latency_ms, gate_result=g,
                    evidence_turns=evidence_turns,
                ))
                per_arg_gates.append(g)

            # 2. Whole-call binding decision
            if binding_key in batch_results:
                b_dec = batch_results[binding_key]
                b_canonical = normalise_label(b_dec.label)
                b_gate = gate(b_canonical, b_dec.confidence, f"{tool_name}.__binding__", self.thresholds)
                binding_info = {
                    "question_id": Q_BINDING.id,
                    "call_summary": binding_call_summary,
                    "label": b_dec.label,
                    "confidence": b_dec.confidence,
                    "gate_result": b_gate,
                    "latency_ms": b_dec.latency_ms,
                }

        # ── 4. Combine per-arg outcomes & apply binding gate rule ────────────────
        _raw = combine(per_arg_gates) if per_arg_gates else "execute"
        # Internal gate vocab: execute/block/clarify → public contract: executed/blocked/clarify
        _norm = {"execute": "executed", "block": "blocked"}
        final = _norm.get(_raw, _raw)

        # Gate rule: any per-argument block or a binding verdict below threshold produces block or clarify;
        # the message to the agent names the mismatched pair.
        if final != "blocked" and binding_info:
            if binding_info["gate_result"] == "block":
                final = "blocked"
            elif binding_info["gate_result"] == "clarify" and final == "executed":
                final = "clarify"

        # ── 5. Build message to agent ────────────────────────────────────────
        if final == "blocked":
            blocked_args = [a for a in arg_decisions if a.gate_result == "block"]
            if blocked_args:
                details = "; ".join(
                    f"{a.name}={a.value!r} ({a.label}, conf={a.confidence:.2f})"
                    for a in blocked_args
                )
                msg = f"BLOCKED: argument(s) not grounded in user statements — {details}"
            else:
                msg = (
                    f"BLOCKED: argument combination not grounded in user statements — "
                    f"{tool_name}({binding_call_summary}) is a mismatched pair."
                )
        elif final == "clarify":
            ambig = [a for a in arg_decisions if a.gate_result == "clarify"]
            if ambig:
                details = "; ".join(f"{a.name}={a.value!r}" for a in ambig)
                msg = (
                    f"CLARIFY NEEDED: I'm not confident {details} is supported "
                    f"by what you said. Could you confirm?"
                )
            else:
                msg = (
                    f"CLARIFY NEEDED: I'm not confident that {tool_name}({binding_call_summary}) "
                    f"is the intended combination. Could you confirm?"
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
            binding=binding_info,
        )
        self._emit(event)
        return final, msg, event

    def _emit(self, event: DecisionEvent) -> None:
        logger.debug("DecisionEvent: %s", json.dumps(event.to_dict()))
        if self.event_callback:
            self.event_callback(event)


# ── Real Strands InterventionHandler subclass ──────────────────────────────
# API verified from strands-agents 1.61.1 site-packages on 2026-10-20:
#   InterventionHandler  → strands.interventions.handler
#   BeforeToolCallEvent  → strands.hooks.events
#   BeforeToolCallEvent.tool_use is a ToolUse TypedDict with keys:
#     toolUseId, name, input  (input is the args dict)
#   BeforeToolCallEvent.invocation_state holds the conversation state list
#     under key 'messages' (list of dicts with 'role' and 'content').
#   Return Deny(reason=...) to cancel, Guide(feedback=...) to ask clarify,
#   or Proceed() to allow.

try:
    from strands import InterventionHandler  # type: ignore[import]
    from strands.hooks.events import BeforeToolCallEvent  # type: ignore[import]
    from strands.interventions.actions import Deny, Guide, Proceed  # type: ignore[import]

    class GroundingGuardHandler(InterventionHandler):
        """
        Real Strands InterventionHandler that runs GroundingGuard in the
        tool-call path. Wire via:

            from strands import Agent
            from patterns.grounding_guard.handler import GroundingGuardHandler

            handler = GroundingGuardHandler(guard=guard)
            agent = Agent(
                model=model,
                tools=[...],
                interventions=[handler],
            )

        The handler converts BeforeToolCallEvent → intercept() args, then maps
        the outcome back to Strands action objects (Deny / Guide / Proceed).
        History is reconstructed from event.agent.messages or invocation_state['messages'].
        """
        name = "grounding-guard"
        on_error: str = "deny"  # fail-closed: broken handler → Deny

        def __init__(self, guard: GroundingGuard):
            self._guard = guard

        def before_tool_call(
            self, event: "BeforeToolCallEvent", **kwargs: Any
        ) -> "Proceed | Deny | Guide":
            """Called by Strands before each tool execution."""
            tool_use = event.tool_use          # ToolUse TypedDict
            tool_name: str = tool_use["name"]
            tool_args: dict = tool_use.get("input", {})

            # Reconstruct Turn list from conversation messages.
            # Only 'user' role messages count as grounding evidence.
            history: list[Turn] = []
            messages = []
            if hasattr(event, "agent") and getattr(event, "agent", None) and hasattr(event.agent, "messages"):
                messages = event.agent.messages
            elif hasattr(event, "invocation_state") and isinstance(event.invocation_state, dict):
                messages = event.invocation_state.get("messages", []) or []

            for idx, msg in enumerate(messages):
                role = msg.get("role", "")
                if role != "user":
                    continue
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Anthropic-style: list of {type, text} blocks
                    text = " ".join(
                        block.get("text", "") for block in content
                        if isinstance(block, dict) and block.get("type") == "text"
                    )
                else:
                    text = str(content)
                history.append(Turn(index=idx, source="user", text=text))

            outcome, message, _event = self._guard.intercept(
                tool_name=tool_name,
                tool_args=tool_args,
                history=history,
            )

            if outcome in ("blocked", "block", "blocked_by_policy"):
                return Deny(reason=message or f"{tool_name} blocked by grounding guard")
            if outcome == "clarify":
                return Guide(feedback=message)
            return Proceed()

except ImportError:
    # strands-agents not installed or wrong version — GroundingGuardHandler unavailable.
    # Tests and SimpleGroundedAgent still work via GroundingGuard.intercept().
    class GroundingGuardHandler:  # type: ignore[no-redef]
        """Stub: strands-agents not importable. Install strands-agents to use."""
        def __init__(self, *a, **kw):
            raise ImportError(
                "GroundingGuardHandler requires strands-agents. "
                "Install it: pip install strands-agents"
            )
