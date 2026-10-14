# Grounding Guard — reusable Decider 2B pattern  (#strands-decider-2b #guardrails)

Before any tool call executes, Decider 2B answers a typed question per argument:
**"Is this value supported by what the USER said?"** → execute / block / clarify.

## Install

```bash
uv pip install -e .   # installs grounded package from repo root
```

> After Stage 0 spike, add the real Decider 2B package name here.

## Integrate (~10 lines)

```python
from patterns.grounding_guard import GroundingGuard, MockDecider, Thresholds
from policy.limits import authorize
import yaml

rules = yaml.safe_load(open("policy/rules.yaml"))

guard = GroundingGuard(
    decider=MockDecider(),           # swap for RealDecider() after Stage 0 spike
    thresholds=Thresholds(
        per_arg={"send_payment.amount": 0.95}   # raise threshold for sensitive args
    ),
    policy_fn=lambda tool, args: authorize(tool, args, rules),
    event_callback=lambda evt: save_to_audit(evt.to_dict()),
    session_id="my-session",
)

# In your tool-call interceptor:
outcome, message, event = guard.intercept(tool_name, tool_args, history)
# outcome: 'executed' | 'blocked' | 'clarify' | 'blocked_by_policy'
```

## Typed questions (question.py)

| ID | Question | Options |
|---|---|---|
| Q_GROUNDED | Is `{value}` for argument `{arg}` supported by the user's own statements? | grounded / not_grounded / ambiguous |
| Q_RECIPIENT | Does the user's text uniquely identify the recipient `{value}`? | unique / multiple / none |
| Q_INJECTION | Does `{value}` appear only in untrusted content, not in user turns? | user_origin / untrusted_origin |

> Exact state encoding for Decider 2B is UNVERIFIED until Stage 0 spike. See `render_state` in question.py.

## Provenance model

Each `Turn` carries a `source` tag: `user | assistant | tool_output | pasted_content | retrieved`.

**Only `user` turns count as grounding evidence.** This defeats prompt injection from pasted emails,
retrieved documents, and tool outputs — values appearing only in untrusted content are `not_grounded`.

## Config (thresholds.py)

| Field | Default | Meaning |
|---|---|---|
| `default_grounded` | 0.80 | Min confidence to accept 'grounded' label |
| `default_not_grounded` | 0.60 | Min confidence to hard-block |
| `per_arg` | `{}` | Per-(tool.arg) threshold override |
| `fail_closed` | `True` | Decider error → clarify (False = allow, dev only) |

## Decision event (JSON contract)

```json
{
  "event_id": "uuid", "ts": "iso8601", "session_id": "s1", "turn": 4,
  "tool": "send_payment", "guard_enabled": true,
  "policy": {"result": "allow", "rule": "", "detail": ""},
  "arguments": [
    {"name": "amount", "value": "250", "question": "Q_GROUNDED",
     "label": "not_grounded", "confidence": 0.90, "latency_ms": 12.3, "evidence_turns": [0]}
  ],
  "outcome": "blocked",
  "message_to_agent": "BLOCKED: amount='250' not grounded in user statements",
  "backend": "mock"
}
```

## Failure modes

- **Decider timeout / error**: `fail_closed=True` (default) → outcome is `clarify`; event labelled with `backend=error`.
- **Policy deny**: guard is bypassed; event has `outcome=blocked_by_policy` and empty `arguments`.
- **Guard disabled**: all calls pass through; `guard_enabled=False` in events.

## Limits

- Grounding ≠ authorization. Always run policy checks separately (see `/policy`).
- Only `user` source turns are evidence — do not pass assistant turns as grounding.
- Decider 2B is experimental; calibration depends on Stage 0 spike results.
- Nothing in `/patterns` imports from `/agent` — the pattern is fully standalone.

