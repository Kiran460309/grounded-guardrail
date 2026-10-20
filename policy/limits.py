"""Deterministic authorization. Runs BEFORE grounding. Grounded != authorized.

Rule check order for send_payment:
  1. allowlist       — tool must be in allowed_tools
  2. invalid_amount  — non-numeric, NaN, inf, negative, or zero  -> deny
  3. per_txn_cap     — amount > per-transaction cap            -> deny
  4. daily_cap       — spent_today + amount > daily limit       -> deny
  5. confirm_over    — amount > confirmation threshold          -> needs_confirm
"""
from dataclasses import dataclass
import math
from typing import Any


@dataclass
class PolicyResult:
    result: str   # allow | deny | needs_confirm
    rule: str = ""
    detail: str = ""


def authorize(
    tool: str,
    args: dict[str, Any],
    rules: dict[str, Any],
    spent_today: float = 0.0,
) -> PolicyResult:
    """Authorize a proposed tool call deterministically before Decider evaluation."""
    if tool not in rules.get("allowed_tools", []):
        return PolicyResult("deny", "allowlist", f"{tool} not allowed")

    if tool == "send_payment":
        r = rules.get("send_payment", {})
        raw_amt = args.get("amount")

        # Validate numeric amount
        if raw_amt is None:
            return PolicyResult("deny", "invalid_amount", "amount is required")
        try:
            amt = float(raw_amt)
        except (ValueError, TypeError):
            return PolicyResult("deny", "invalid_amount", f"non-numeric amount: {raw_amt!r}")

        if math.isnan(amt) or math.isinf(amt):
            return PolicyResult("deny", "invalid_amount", f"invalid numeric amount: {raw_amt!r}")

        if amt <= 0:
            return PolicyResult("deny", "invalid_amount", f"amount must be positive, got {amt}")

        # Check caps
        per_txn = r.get("per_txn_cap")
        if per_txn is not None and amt > per_txn:
            return PolicyResult("deny", "per_txn_cap", f"{amt} > {per_txn}")

        daily = r.get("daily_cap")
        if daily is not None and (spent_today + amt) > daily:
            return PolicyResult("deny", "daily_cap", f"daily cap exceeded ({spent_today} + {amt} > {daily})")

        confirm_over = r.get("confirm_over")
        if confirm_over is not None and amt > confirm_over:
            return PolicyResult("needs_confirm", "confirm_over", f"{amt} needs confirmation")

    return PolicyResult("allow")
