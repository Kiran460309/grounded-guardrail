"""Deterministic authorization. Runs BEFORE grounding. Grounded != authorized."""
from dataclasses import dataclass

@dataclass
class PolicyResult:
    result: str   # allow | deny | needs_confirm
    rule: str = ""
    detail: str = ""

def authorize(tool: str, args: dict, rules: dict, spent_today: float = 0.0) -> PolicyResult:
    if tool not in rules.get("allowed_tools", []):
        return PolicyResult("deny", "allowlist", f"{tool} not allowed")
    if tool == "send_payment":
        r = rules["send_payment"]; amt = float(args.get("amount", 0))
        if amt > r["per_txn_cap"]:  return PolicyResult("deny", "per_txn_cap", f"{amt} > {r['per_txn_cap']}")
        if spent_today + amt > r["daily_cap"]: return PolicyResult("deny", "daily_cap", "daily cap exceeded")
        if amt > r["confirm_over"]: return PolicyResult("needs_confirm", "confirm_over", f"{amt} needs confirmation")
    return PolicyResult("allow")
