# Development Journal — Grounded

## 2026-10-13 — Stage -1 complete; Stage 0 spike scaffolded

### Done today
- Verified project skeleton: `patterns/grounding_guard/{question.py, decider_client.py, thresholds.py}`,
  `policy/{limits.py, rules.yaml}`, `eval/schema.json`, `tests/test_core.py` all present.
- Created `scripts/spike_decider.py` (20 cases, mock backend, p50/p95 timing).
- Built `patterns/grounding_guard/handler.py` — GroundingGuard InterventionHandler.
- Built `agent/` — Strands agent + 4 mock tools + 5 scripted demo scenarios.
- Built `policy/` tests.
- Built `eval/` — 60-case dataset draft + 5 baselines + `scripts/run_eval.py`.
- Built `backend/` — FastAPI + SSE + SQLite audit log.
- Built `website/` — Vite+React+TS+Tailwind+Recharts dashboard.
- Built `scripts/seed_demo.py`.

### Stage 0 — Decider 2B API (UNVERIFIED)
- **Real API: NOT YET CONFIRMED.** `RealDecider` in `decider_client.py` raises `NotImplementedError`.
- Mock backend passes 20 spike cases (see `docs/journal/spike_results.json` after running
  `python scripts/spike_decider.py`).
- TODO: Find official Decider 2B model card / docs, paste link here, then implement `RealDecider`.

### Stage 0 spike — items to fill after real model confirmed
```
Input format : UNVERIFIED (see question.py render_state — may need adjustment)
Output format: UNVERIFIED (label field name, confidence field, options encoding)
Hardware req : UNVERIFIED (GPU RAM, VRAM)
Install cmd  : UNVERIFIED (pip install ???)
Model path   : UNVERIFIED
p50 latency  : not yet measured (real hardware)
p95 latency  : not yet measured (real hardware)
```

### GO/NO-GO gate (end Oct 17)
Not yet reached. Will re-evaluate after real Decider is wired.

## 2026-10-13 — Stage A(a) complete (Decider Adapter scaffolded, tests 31/31 green)

### Done
- Fixed `MockDecider` regex to reliably extract target values from question templates without breaking on apostrophes (e.g., "user's"). Kept clearly labelled `backend = "mock"`.
- Modernized datetime handling in `handler.py` to `datetime.now(datetime.timezone.utc)`.
- Purged unmeasured claims ("~115 ms", "sub-100ms", "14x") across documentation and replaced with measured/TBD policy; cited official M3 Pro median (~153 ms warm) as machine-specific.
- Implemented `HttpDecider` in `patterns/grounding_guard/decider_client.py`: request builder (`POST /v1/systemone`), timeout handling, high-precision latency measurement via `time.perf_counter()`, and fail-closed error handling. Response parser intentionally deferred pending verified response shape.
- Created `scripts/capture_response.py` to send a 3-question batched `noul` probe with shared state prefix to `DECIDER_URL` and save raw JSON to `docs/journal/sample_response.json`.
- All 31 pytest tests pass green (0.28s).

### Verification status
- Response JSON schema: UNVERIFIED (awaiting real response capture from user's cloud server).
- Hardware / latency: UNVERIFIED on cloud target (awaiting live capture).

## 2026-10-20 — 6 Priority Architecture & Guardrail Fixes Complete (tests 35/35 green)

### Done
1. **Strands API Verified & Real Bedrock Agent Wired**:
   - Inspected installed `strands-agents` 1.61.1 source (`strands.interventions.handler.InterventionHandler`, `BeforeToolCallEvent`, `Deny`, `Guide`, `Proceed`).
   - Wired `GroundingGuardHandler` through the real Strands tool-call intervention lifecycle.
   - Built `create_grounded_agent` factory in `agent/__init__.py` with `@tool` registration and BedrockModel support.
   - Kept `SimpleGroundedAgent` as an offline test fixture.
2. **Canonical Typed Question Verdicts**:
   - Implemented `normalise_label()` in `thresholds.py` mapping `unique`/`multiple`/`none` (Q_RECIPIENT) and `user_origin`/`untrusted_origin` (Q_INJECTION) to canonical `grounded`/`ambiguous`/`not_grounded`.
   - Gate routing accepts canonical labels with fail-closed default for unknown labels.
3. **Provenance & Disambiguation System Lookup Section**:
   - Added `SYSTEM LOOKUP (not user-authored)` section to `render_state` in `question.py`.
   - Explicitly labelled tool outputs so Decider can disambiguate user-mentioned entities without introducing new values.
4. **Batched Decider Requests**:
   - Implemented batching per tool call via `decide_many()` with single shared state prefix for KV cache efficiency.
   - Graceful per-argument fallback when using `MockDecider`.
5. **Guarded Arguments & Numeric Normalization**:
   - Defined `GUARDED_ARGS` per tool; unguarded arguments pass through without Decider overhead.
   - Implemented `_normalize_numeric_value()` to normalize amounts prior to evaluation.
6. **Policy Hardening & Confirmation Flow**:
   - Hardened `policy/limits.py` to deny non-numeric, NaN, inf, negative, and zero amounts (`invalid_amount`).
   - Preserved strict rule check order: allowlist -> invalid_amount -> per_txn_cap -> daily_cap -> confirm_over.
   - Handled `needs_confirm` policy outcome as `clarify` in `handler.py` to prompt user for confirmation.
7. **Test Coverage**:
   - Added `TestStrandsHook` covering `Deny`, `Proceed`, and agent factory.
   - Added `TestPolicy.test_invalid_amounts`.
   - All 35 tests pass green.

