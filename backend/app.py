"""
FastAPI backend for Grounded.

Endpoints:
  POST /chat           — send a message to the demo agent; triggers guard
  GET  /events         — SSE stream of DecisionEvent objects
  POST /toggle-guard   — enable/disable the GroundingGuard
  GET  /audit          — paginated audit log from SQLite
  GET  /scenarios      — list available demo scenarios
  POST /run-scenario   — run a pre-scripted demo scenario

Run:
  uvicorn backend.app:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

import yaml
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path("backend/audit.db")
RULES_PATH = Path("policy/rules.yaml")


# ── Database ─────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id   TEXT UNIQUE,
                ts         TEXT,
                session_id TEXT,
                turn       INTEGER,
                tool       TEXT,
                outcome    TEXT,
                guard_on   INTEGER,
                payload    TEXT
            )
        """)
        conn.commit()


def insert_event(event_dict: dict) -> None:
    with get_db() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO audit
              (event_id, ts, session_id, turn, tool, outcome, guard_on, payload)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            event_dict["event_id"],
            event_dict["ts"],
            event_dict.get("session_id", "default"),
            event_dict.get("turn", 0),
            event_dict.get("tool", ""),
            event_dict.get("outcome", ""),
            1 if event_dict.get("guard_enabled") else 0,
            json.dumps(event_dict),
        ))
        conn.commit()


# ── SSE event queue ───────────────────────────────────────────────────────────

_event_queues: list[asyncio.Queue] = []


def broadcast_event(event_dict: dict) -> None:
    """Push a DecisionEvent to all connected SSE clients."""
    insert_event(event_dict)
    for q in _event_queues:
        try:
            q.put_nowait(event_dict)
        except asyncio.QueueFull:
            pass


# ── Guard & agent ─────────────────────────────────────────────────────────────

from patterns.grounding_guard.handler import GroundingGuard
from patterns.grounding_guard.decider_client import MockDecider
from patterns.grounding_guard.thresholds import Thresholds
from policy.limits import authorize

_rules: dict = {}
_guard: GroundingGuard | None = None


def _make_guard(enabled: bool = True) -> GroundingGuard:
    return GroundingGuard(
        decider=MockDecider(),
        thresholds=Thresholds(per_arg={"send_payment.amount": 0.95}),
        policy_fn=lambda tool, args: authorize(tool, args, _rules),
        event_callback=lambda evt: broadcast_event(evt.to_dict()),
        enabled=enabled,
    )


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _rules, _guard
    init_db()
    _rules = yaml.safe_load(RULES_PATH.read_text())
    _guard = _make_guard(enabled=True)
    logger.info("Grounded backend ready. Guard backend: %s", _guard.decider.backend)
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Grounded", description="Grounding guard demo backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── /chat ────────────────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(body: dict):
    """
    Simulate a chat turn. The agent proposes a tool call based on the message,
    then the guard intercepts it.

    Body: {"message": str, "session_id": str (optional), "history": [...] (optional)}
    """
    from patterns.grounding_guard.question import Turn
    from agent import DEMO_SCENARIOS, SimpleGroundedAgent

    message = body.get("message", "")
    session_id = body.get("session_id", str(uuid.uuid4()))
    raw_history = body.get("history", [{"index": 0, "source": "user", "text": message}])
    history = [Turn(**h) for h in raw_history]

    # Simple keyword → tool routing for demo
    tool, args = _route_message(message, raw_history)

    if tool is None:
        return {"reply": f"Echo: {message}", "event": None}

    _guard.session_id = session_id
    outcome, msg, event = _guard.intercept(tool, args, history)
    event_dict = event.to_dict()

    reply = msg if msg else f"✓ Tool `{tool}` executed with {args}"
    return {"reply": reply, "outcome": outcome, "event": event_dict}


def _route_message(message: str, history: list[dict]) -> tuple[str | None, dict]:
    """Very simple keyword router for demo purposes. In prod, the LLM decides."""
    m = message.lower()
    if "pay" in m or "transfer" in m or "send" in m and "dollar" in m:
        import re
        amt_m = re.search(r"(\d[\d,\.]*)", m)
        amount = float(amt_m.group(1).replace(",", "")) if amt_m else 250.0
        names = re.findall(r'\b[A-Z][a-z]+\b', message)
        recipient = names[0].lower() if names else "unknown"
        return "send_payment", {"recipient": recipient, "amount": amount}
    if "email" in m or "send" in m:
        import re
        email_m = re.search(r'[\w.+-]+@[\w-]+\.\w+', message)
        to = email_m.group(0) if email_m else "unknown@example.com"
        return "send_email", {"to": to, "subject": "from agent"}
    if "remind" in m:
        import re
        time_m = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', m)
        t = time_m.group(0) if time_m else "09:00"
        return "set_reminder", {"text": message, "time": t}
    if "meet" in m or "schedule" in m or "book" in m:
        return "create_event", {"attendee": "someone@example.com", "date": "tomorrow"}
    return None, {}


# ── /events (SSE) ────────────────────────────────────────────────────────────

@app.get("/events")
async def events():
    """Server-Sent Events stream of DecisionEvent objects."""
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _event_queues.append(q)

    async def generator():
        try:
            # Send hello
            yield {"data": json.dumps({"type": "connected", "ts": datetime.utcnow().isoformat()})}
            while True:
                try:
                    event_dict = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield {"data": json.dumps(event_dict)}
                except asyncio.TimeoutError:
                    yield {"data": json.dumps({"type": "heartbeat"})}
        finally:
            _event_queues.remove(q)

    return EventSourceResponse(generator())


# ── /toggle-guard ────────────────────────────────────────────────────────────

@app.post("/toggle-guard")
async def toggle_guard(body: dict):
    """Enable or disable the grounding guard. Body: {"enabled": bool}"""
    enabled = body.get("enabled", True)
    _guard.enabled = enabled
    return {"guard_enabled": enabled}


# ── /audit ───────────────────────────────────────────────────────────────────

@app.get("/audit")
async def audit(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session_id: str | None = Query(None),
):
    """Return paginated audit log rows."""
    with get_db() as conn:
        if session_id:
            rows = conn.execute(
                "SELECT payload FROM audit WHERE session_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
                (session_id, limit, offset)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT payload FROM audit ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
    return [json.loads(r["payload"]) for r in rows]


# ── /scenarios ───────────────────────────────────────────────────────────────

@app.get("/scenarios")
async def list_scenarios():
    from agent import DEMO_SCENARIOS
    return [
        {"key": k, "label": v["label"], "description": v["description"]}
        for k, v in DEMO_SCENARIOS.items()
    ]


@app.post("/run-scenario")
async def run_scenario(body: dict):
    """Run a pre-scripted demo scenario. Body: {"key": str}"""
    from agent import SimpleGroundedAgent

    key = body.get("key", "invented_amount")
    agent = SimpleGroundedAgent()
    agent.guard.event_callback = lambda evt: broadcast_event(evt.to_dict())
    result = agent.run_scenario(key)
    return result
