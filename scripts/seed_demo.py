"""Seed the demo database with scripted scenario results for the video recording."""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from agent import SimpleGroundedAgent, DEMO_SCENARIOS

def seed():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("Seeding demo scenarios...\n")
    agent = SimpleGroundedAgent()
    results = agent.run_all_scenarios()

    out = pathlib.Path("backend/seed_results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    print(f"\nSeeded {len(results)} scenarios → {out}")
    return results

if __name__ == "__main__":
    seed()
