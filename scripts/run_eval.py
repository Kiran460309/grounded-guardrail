"""
Eval harness — 5 baselines compared on the same dataset.

Baselines:
  1. none       — always execute (no guard)
  2. regex      — substring/fuzzy match of arg value in user turns
  3. embedding  — cosine similarity (local stub; swap for Bedrock Titan if available)
  4. llm_judge  — Bedrock Claude call (optional; requires AWS creds)
  5. grounded   — MockDecider (real Decider after Stage 0 spike)

Run:  python scripts/run_eval.py [--split dev|test|all] [--approaches all]
Output: eval/results.json, eval/results.md
NOTE: report only from results.json/results.md — never invent numbers.
"""
from __future__ import annotations

import sys
import json
import time
import statistics
import pathlib
from dataclasses import dataclass, field
from typing import Callable

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DATASET_PATH = REPO_ROOT / "eval" / "data" / "dataset.json"
RESULTS_JSON = REPO_ROOT / "eval" / "results.json"
RESULTS_MD   = REPO_ROOT / "eval" / "results.md"
RULES_PATH   = REPO_ROOT / "policy" / "rules.yaml"

# ── Case loading ─────────────────────────────────────────────────────────────

def load_dataset(split: str = "all") -> list[dict]:
    raw = json.loads(DATASET_PATH.read_text())
    if split == "all":
        return raw
    return [c for c in raw if c["split"] == split]

# ── Baseline implementations ─────────────────────────────────────────────────

def _user_text(history: list[dict]) -> str:
    return " ".join(h["text"] for h in history if h["source"] == "user")


def baseline_none(case: dict) -> tuple[str, float]:
    """Always execute — no guard at all."""
    return "executed", 0.0


def baseline_regex(case: dict) -> tuple[str, float]:
    """Simple substring/fuzzy match of arg value in user turns."""
    try:
        from rapidfuzz import fuzz
        has_fuzz = True
    except ImportError:
        has_fuzz = False

    user_ctx = _user_text(case["history"]).lower()
    results = []
    t0 = time.perf_counter()
    for arg, val in case["proposed_args"].items():
        v = str(val).lower()
        if v in user_ctx:
            results.append("grounded")
        elif has_fuzz and fuzz.partial_ratio(v, user_ctx) >= 80:
            results.append("grounded")
        else:
            results.append("not_grounded")
    elapsed = (time.perf_counter() - t0) * 1000
    outcome = "executed" if all(r == "grounded" for r in results) else "blocked"
    return outcome, elapsed


def baseline_embedding(case: dict) -> tuple[str, float]:
    """
    Cosine similarity stub. Uses simple bag-of-words overlap until
    Bedrock Titan Embeddings is wired (avoids external dependency for offline dev).
    Replace body with real embeddings call after Stage 0.
    """
    t0 = time.perf_counter()
    user_ctx = set(_user_text(case["history"]).lower().split())
    results = []
    for arg, val in case["proposed_args"].items():
        val_tokens = set(str(val).lower().split())
        overlap = len(val_tokens & user_ctx) / max(len(val_tokens), 1)
        results.append("grounded" if overlap > 0.3 else "not_grounded")
    elapsed = (time.perf_counter() - t0) * 1000
    outcome = "executed" if all(r == "grounded" for r in results) else "blocked"
    return outcome, elapsed


def baseline_llm_judge(case: dict) -> tuple[str, float]:
    """
    LLM-as-judge via Bedrock. Stub that raises ImportError if boto3 not available.
    Real implementation needs AWS creds + model ID from bedrock console.
    """
    # Stub for offline dev
    return baseline_regex(case)   # TODO: replace with Bedrock call


def baseline_grounded(case: dict, rules: dict) -> tuple[str, float]:
    """Grounded with MockDecider (swap for RealDecider after Stage 0 spike)."""
    from patterns.grounding_guard.question import Turn
    from patterns.grounding_guard.handler import GroundingGuard
    from patterns.grounding_guard.decider_client import MockDecider
    from patterns.grounding_guard.thresholds import Thresholds
    from policy.limits import authorize

    history = [Turn(**h) for h in case["history"]]
    guard = GroundingGuard(
        decider=MockDecider(),
        thresholds=Thresholds(per_arg={"send_payment.amount": 0.95}),
        policy_fn=lambda tool, args: authorize(tool, args, rules),
    )
    t0 = time.perf_counter()
    outcome, _, event = guard.intercept(case["tool"], case["proposed_args"], history)
    elapsed = (time.perf_counter() - t0) * 1000
    # Normalize outcome for metric comparison
    norm = outcome if outcome != "block" else "blocked"
    return norm, elapsed


# ── Metrics ──────────────────────────────────────────────────────────────────

@dataclass
class Metrics:
    approach: str
    split: str
    n: int = 0
    correct: int = 0
    false_block: int = 0    # grounded call blocked
    missed_block: int = 0   # invented/injected call executed
    clarify_correct: int = 0
    latencies: list[float] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correct / self.n if self.n else 0.0

    @property
    def false_block_rate(self) -> float:
        valid = sum(1 for _ in range(self.n))  # recomputed outside
        return self.false_block / self.n if self.n else 0.0

    @property
    def missed_block_rate(self) -> float:
        return self.missed_block / self.n if self.n else 0.0

    @property
    def p50(self) -> float:
        return statistics.median(self.latencies) if self.latencies else 0.0

    @property
    def p95(self) -> float:
        s = sorted(self.latencies)
        return s[int(len(s) * 0.95)] if s else 0.0

    def to_dict(self) -> dict:
        return {
            "approach": self.approach,
            "split": self.split,
            "n": self.n,
            "accuracy": round(self.accuracy, 4),
            "false_block_rate": round(self.false_block_rate, 4),
            "missed_block_rate": round(self.missed_block_rate, 4),
            "p50_ms": round(self.p50, 3),
            "p95_ms": round(self.p95, 3),
        }


def _outcome_matches(predicted: str, expected: str) -> bool:
    """Normalize and compare outcomes."""
    mapping = {"block": "blocked", "execute": "executed"}
    p = mapping.get(predicted, predicted)
    e = mapping.get(expected, expected)
    return p == e


def evaluate(cases: list[dict], approach_fn: Callable, approach_name: str,
             split: str, rules: dict) -> tuple[Metrics, list[dict]]:
    m = Metrics(approach=approach_name, split=split)
    failures = []
    for case in cases:
        m.n += 1
        expected = case["expected"]["outcome"]
        try:
            if approach_name == "grounded":
                predicted, lat = approach_fn(case, rules)
            else:
                predicted, lat = approach_fn(case)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            predicted, lat = "error", 0.0

        m.latencies.append(lat)
        match = _outcome_matches(predicted, expected)
        if match:
            m.correct += 1
        else:
            # Classify failure type
            should_block = expected in ("blocked", "blocked_by_policy")
            did_block = predicted in ("blocked", "blocked_by_policy", "clarify")
            if should_block and not did_block:
                m.missed_block += 1
            elif not should_block and did_block:
                m.false_block += 1
            failures.append({
                "id": case["id"],
                "category": case["category"],
                "expected": expected,
                "predicted": predicted,
                "latency_ms": lat,
            })
    return m, failures


# ── Main ─────────────────────────────────────────────────────────────────────

def run_eval(split: str = "test", approaches: list[str] | None = None) -> None:
    rules = yaml.safe_load(RULES_PATH.read_text())
    cases = load_dataset(split)
    print(f"\nEval — split={split}, n={len(cases)} cases\n{'='*60}")

    approach_fns = {
        "none":      baseline_none,
        "regex":     baseline_regex,
        "embedding": baseline_embedding,
        "llm_judge": baseline_llm_judge,
        "grounded":  baseline_grounded,
    }
    if approaches:
        approach_fns = {k: v for k, v in approach_fns.items() if k in approaches}

    all_metrics = []
    all_failures = {}
    for name, fn in approach_fns.items():
        m, failures = evaluate(cases, fn, name, split, rules)
        all_metrics.append(m)
        all_failures[name] = failures
        print(f"  {name:12s} acc={m.accuracy:.1%}  fb={m.false_block_rate:.1%}  "
              f"mb={m.missed_block_rate:.1%}  p50={m.p50:.1f}ms  p95={m.p95:.1f}ms")

    # Write JSON
    output = {
        "NOTE": "Numbers from MockDecider — not real until RealDecider is wired.",
        "split": split,
        "n": len(cases),
        "metrics": [m.to_dict() for m in all_metrics],
        "failures": all_failures,
    }
    RESULTS_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nResults written to {RESULTS_JSON}")

    # Write markdown table
    rows = ["| Approach | Accuracy | False-block | Missed-block | p50 ms | p95 ms |",
            "|---|---|---|---|---|---|"]
    for m in all_metrics:
        rows.append(f"| {m.approach} | {m.accuracy:.1%} | {m.false_block_rate:.1%} | "
                    f"{m.missed_block_rate:.1%} | {m.p50:.1f} | {m.p95:.1f} |")
    md = "\n".join([
        "# Eval results",
        f"> split={split}, n={len(cases)}",
        "> ⚠ Numbers from MockDecider — replace after Stage 0 spike with RealDecider.",
        "",
        *rows,
    ])
    RESULTS_MD.write_text(md, encoding="utf-8")
    print(f"Results markdown written to {RESULTS_MD}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--split", default="test", choices=["dev", "test", "all"])
    p.add_argument("--approaches", nargs="+", default=None)
    args = p.parse_args()
    run_eval(args.split, args.approaches)
