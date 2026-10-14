# 01 — Product Requirements Document: Grounded

## 1. Problem (real, current)
LLM agents fill tool-call arguments themselves. They sometimes **invent** (an amount the user never
gave), **guess** (which "Priya"), or get **hijacked** (an instruction hidden in a pasted email swaps
the recipient). Fixes today are bad: (a) trust the model, (b) ask a second LLM to judge every call
(adds seconds + tokens, so teams skip it), (c) human approval on everything (kills autonomy).
Result: agents either can't be trusted with real actions or are slowed to a crawl.

## 2. Solution
Grounded is a drop-in Strands guardrail. For each tool call, Decider 2B answers a typed question
per argument: *is this value supported by something the USER said?* -> label + calibrated confidence.
High confidence grounded -> run. Not grounded -> block with reason. Ambiguous/low confidence ->
agent asks a clarifying question. Deterministic policy (limits/allowlists) runs first, separately.

## 3. Users / personas
| Persona | Need | Success |
|---|---|---|
| **Agent developer** (primary) | A guard they can add in minutes that is fast, cheap, measurable | Copy pattern, 1 handler line, sees decisions + metrics |
| **End user of an agent** | Agent never acts on things they didn't say; asks when unsure | Fewer wrong emails/payments; sensible clarifying questions |
| **Hackathon jury** | Clear idea, real use of Decider+Bedrock, reusable, honest numbers | Understands in 20s; sees live decision; finds pattern + eval in repo |
| **Security/ops reviewer** | Audit trail, separation of concerns | Per-decision log; policy distinct from grounding |

## 4. Goals / non-goals
Goals: guard in real tool-call path; multi-turn + provenance-aware; 150-200 case eval; 5-way benchmark;
real-time dashboard; reusable documented pattern; polished video/article/site.
Non-goals: real payments/emails; proving safety (grounding is not authorization); training Decider;
production hardening; multi-language.

## 5. User stories
- As a dev I add `GroundingGuard(...)` to my Strands agent and every tool call is checked.
- As a dev I set per-tool, per-argument thresholds and see a threshold-vs-error curve.
- As a user, when I say "send it to her", the agent resolves "her" from my earlier turns.
- As a user, if the model invents an amount, the call is blocked and I'm told which value lacked support.
- As a user, if two contacts match, the agent asks me which one.
- As a reviewer I read an audit log: argument, evidence, label, confidence, latency, outcome.
- As a jury member I toggle guard OFF/ON on the same prompt and watch the difference live.

## 6. Functional requirements
| ID | Requirement | Priority |
|---|---|---|
| FR1 | Strands agent on Bedrock with 4 mock tools: send_email, create_event, send_payment, set_reminder | P0 |
| FR2 | InterventionHandler intercepts every tool call before execution | P0 |
| FR3 | Per-argument typed question to Decider via adapter; returns label+confidence+latency | P0 |
| FR4 | Gate logic: execute / block / clarify using per-arg thresholds | P0 |
| FR5 | Policy layer (deterministic): allowlist, per-txn cap, daily cap, confirmation required over X | P0 |
| FR6 | Provenance tagging: user vs tool/pasted/retrieved; only `user` grounds | P0 |
| FR7 | Structured decision event + SQLite audit log | P0 |
| FR8 | Real-time stream (SSE) of decision events to dashboard | P0 |
| FR9 | Dashboard: chat, per-call decision cards, confidence meter, latency, guard toggle, audit table | P0 |
| FR10 | Eval harness: dataset, 5 baselines, metrics, threshold curve, held-out split | P0 |
| FR11 | Side-by-side live compare: Grounded vs LLM-judge (latency counters) | P1 |
| FR12 | Reusable pattern package + README + 3 typed questions (grounding, recipient-ambiguity, injection) | P0 |
| FR13 | Public website: landing, live demo, results, how-to-integrate | P1 |
| FR14 | Deploy on AWS (EC2/App Runner + S3/CloudFront) | P1 |

## 7. Non-functional
- Guard overhead measured, reported as p50/p95 (no promised number until measured).
- Every decision reproducible from logged inputs.
- Fail-safe: if Decider errors/times out -> configurable `fail_closed` (default) -> clarify.
- Pattern has zero dependency on demo agent. Python 3.11+. Typed. Tested.

## 8. Success metrics (fill from /eval, never invent)
Accuracy, false-block rate, missed-block rate (overall + per category), p50/p95 latency, cost / 1k
checks vs LLM-judge; # multi-turn cases solved vs regex/embedding baselines.

## 9. Acceptance criteria (MVP)
1. Invented amount is blocked live. 2. Multi-turn pronoun resolves & executes. 3. Injected recipient
from pasted email is blocked. 4. Ambiguous contact triggers clarifying question. 5. Over-limit but
grounded payment is stopped by POLICY, not Grounded (shown in UI). 6. Results table has all 5 approaches.
7. Three submission artifacts published with both tags.
