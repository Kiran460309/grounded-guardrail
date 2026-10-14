# 05 — Build plan: stages, gates, and Antigravity prompts
Paste each prompt into Antigravity ONE AT A TIME. Review the diff, run tests, commit, then journal.

## Calendar
| Date | Stage |
|---|---|
| Oct 13-15 | Stage -1: profile, Bedrock access test, repo init, write 20 spike cases |
| Oct 16 | Stage 0: Decider SPIKE |
| Oct 17 | Stage 1: guard in tool-call path. **GO/NO-GO end of day** |
| Oct 18 | Stage 2: policy + gating + clarify; start eval set |
| Oct 19 | Stage 3: finish dataset, baselines, run eval |
| Oct 20 | Stage 4: dashboard + side-by-side; tune thresholds; pattern README |
| Oct 21 | Stage 5: record + upload video |
| Oct 22 | Stage 6: website polish, article published, tags added |
| Oct 23 | Buffer: incognito link check; submit early |

## Stage 0 — Spike (gate: real Decider returns label+confidence on 20 cases)
Prompt:
> Read AGENTS.md and docs/. Do NOT guess the Decider 2B API. Find the official docs/model card for
> Strands Decider 2B (I will paste the link/README). Write scripts/spike_decider.py that loads the
> model locally, asks one typed yes/no question, prints the raw output, label, confidence, and times 20
> runs (p50/p95). Record input/output format, hardware needs, and how to pass options in
> docs/journal/JOURNAL.md. Then implement the real backend in patterns/grounding_guard/decider_client.py
> behind the existing DeciderClient protocol. Keep the mock.

## Stage 1 — Guard in the real path (gate: blocked/allowed live on mock tools)
> Implement agent/ with a Strands agent on Bedrock and 4 mock tools. Verify the exact Strands
> InterventionHandler API from the installed package/docs, then implement
> patterns/grounding_guard/handler.py that intercepts each tool call, builds user-only evidence from
> provenance-tagged history, asks Decider per argument, and returns execute/block/clarify. Add
> pytest tests with the mock backend. Emit DecisionEvent per docs/02-architecture.md.

**GO/NO-GO (end Oct 17):** Decider gives usable decisions on >=20 hand-written cases AND runs in the
handler. If NO -> switch to #policy (classify request category) or #model-routing; keep adapter + eval harness.

## Stage 2 — Policy + gating + clarify
> Add /policy (allowlist, per-txn cap, daily cap, confirm-over-X from rules.yaml) executed BEFORE
> the guard. Add thresholds.py with per-tool/per-arg thresholds and fail_closed behavior. Add clarify
> path so the agent asks a question instead of acting. Tests for each acceptance criterion in the PRD.

## Stage 3 — Eval harness
> Create eval/ with dataset loader (schema in docs/04-eval-plan.md), 5 approaches, metrics, and
> scripts/run_eval.py that writes results.json + results.md + threshold_curve.png. Dev/test split enforced
> (thresholds tuned on dev only). Measure latency per call and Bedrock token cost for LLM-judge.
> I will provide the dataset; generate a first draft of 60 cases for me to review and correct.

## Stage 4 — Backend + dashboard (real-time)
> Build backend/ FastAPI with POST /chat, GET /events (SSE of DecisionEvent), POST /toggle-guard,
> GET /audit, SQLite. Build website/ (Vite+React+TS+Tailwind+Recharts): chat panel, live decision cards
> with confidence meter + latency + policy result, guard ON/OFF toggle, audit table, side-by-side
> Grounded vs LLM-judge with latency counters, and a "Try to trick it" scenario picker.

## Stage 5 — Demo & video
> Add scripts/seed_demo.py scripts the 5 demo scenarios deterministically. Add a README quickstart
> that works from a clean clone in <5 commands.

## Stage 6 — Docs, site, article
> Fill README with REAL measured results from eval/results.md. Finalize patterns/grounding_guard/README.md
> (install, 10-line integration, config, limits, failure modes). Generate the architecture diagram from
> docs/02-architecture.md.

## Quality gates (every stage)
`pytest` green, `ruff` clean, journal entry written, no unmeasured claims, committed.
