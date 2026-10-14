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

