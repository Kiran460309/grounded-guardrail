# AGENTS.md — instructions for the AI coding agent (read this first)

## Mission
Build **Grounded**: a reusable guardrail for Strands agents. Before any tool call executes,
Strands Decider 2B answers a typed question: "Is each argument supported by what the USER said?"
Entry for the AWS "Agent Experience Hackathon: Strands Decider". Deadline: 2026-10-23 23:59 PT.
Pattern tags: #strands-decider-2b #guardrails

## Read order
1. docs/00-analysis.md  2. docs/01-PRD.md  3. docs/02-architecture.md
4. docs/03-tech-stack.md  5. docs/04-eval-plan.md  6. docs/05-build-plan.md

## HARD RULES
1. **Never invent the Decider 2B API.** Its real interface is UNVERIFIED. Stage 0 is a spike:
   read the official model card/docs, run it locally, record real input/output shapes in
   docs/journal/JOURNAL.md. All Decider access goes through `patterns/grounding_guard/decider_client.py`
   (adapter). Until verified, only a clearly-labelled MOCK backend may exist.
2. **Never fabricate numbers.** Latency, accuracy, cost come ONLY from scripts in /eval. No copied
   "115ms" claims in README/article/UI; show measured values or "not yet measured".
3. **Grounding != authorization.** Deterministic policy (/policy) runs BEFORE the grounding guard and
   is a separate module. Never merge them.
4. **Provenance matters.** Only user-authored turns count as grounding evidence. Tool outputs,
   pasted emails and retrieved docs are UNTRUSTED and cannot ground an argument.
5. All tools are MOCKS (no real emails/payments). No secrets in git; use .env + .env.example.
6. Every guard decision is emitted as a structured event (see docs/02-architecture.md) and logged.
7. Keep the reusable pattern independent of the demo agent: nothing in /patterns may import /agent.
8. No third-party logos/trademarks/copyrighted music in demo assets. License: MIT.
9. Write tests with each module. Commit small. After each stage append a dated entry to the journal.
10. If a stage fails its gate (docs/05-build-plan.md), STOP and report; do not paper over it.

## Definition of done
Public repo, working agent on AWS (Bedrock + Decider in the tool-call path), eval results with
baselines, reusable pattern with README, <3 min public video, published article, both tags.
