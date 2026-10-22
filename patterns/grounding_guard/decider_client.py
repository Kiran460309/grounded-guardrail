"""Adapter between the guard and Decider 2B. Swap backends without touching the handler.

RULES:
- Mock backend is clearly labelled "mock" and must NEVER be used for reported numbers.
- Real backend (HttpDecider) talks to Decider 2B server over HTTP POST /v1/systemone.
- Response parser is intentionally deferred to Stage A(b) pending sample_response.json.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from .question import TypedQuestion

logger = logging.getLogger(__name__)


@dataclass
class Decision:
    label: str            # grounded | not_grounded | ambiguous (or raw response label)
    confidence: float     # 0..1 calibrated confidence
    latency_ms: float     # measured round-trip time in milliseconds
    backend: str          # "mock" | "real" | "decider_error"


class DeciderClient(Protocol):
    backend: str
    def decide(self, state: str, question: str, q: TypedQuestion) -> Decision: ...


class MockDecider:
    """CLEARLY A MOCK: naive substring check so the pipeline/tests run before the real model is wired.
    Never use for reported numbers. Always labelled 'mock'."""
    backend = "mock"

    def decide(self, state: str, question: str, q: TypedQuestion) -> Decision:
        t0 = time.perf_counter()
        # Robustly extract the target value from question templates without getting tripped by "user's"
        m = (
            re.search(r"'([^']+)' for argument", question)
            or re.search(r"recipient '([^']+)'", question)
            or re.search(r"Does '([^']+)'", question)
        )
        if m:
            value = m.group(1).lower()
        else:
            matches = re.findall(r"'([^']+)'", question)
            value = (matches[-1] if matches else "").lower()

        evidence = state.split("PROPOSED CALL")[0].lower()
        if q.id == "Q_BINDING":
            vals = [v.lower() for v in re.findall(r"\b\w+=['\"]([^'\"]+)['\"]", question)]
            aliases = {}
            if "system lookup" in evidence:
                parts = evidence.split("system lookup")
                user_section = parts[0]
                lookup_section = parts[1]
                for line in lookup_section.split("\n"):
                    m = re.search(r"([^:<]+)<([^>]+)>", line)
                    if m:
                        name = m.group(1).replace("contact", "").strip()
                        addr = m.group(2).strip()
                        aliases[addr] = name
            else:
                user_section = evidence

            clauses = [c.strip() for c in re.split(r"(?:,\s*(?:and\s+|but\s+)?|\.\s+|\n+|;\s*|\s+and\s+|\s+but\s+)", user_section) if c.strip()]
            matched = False
            for c in clauses:
                all_present = True
                for v in vals:
                    alias = aliases.get(v, v)
                    if v not in c and alias not in c:
                        all_present = False
                        break
                if all_present:
                    matched = True
                    break
            label = "grounded" if matched else "not_grounded"
        elif "recipient" in q.id.lower() and ("found 2" in evidence or "multiple" in evidence):
            label = "multiple"
        else:
            label = "grounded" if value and value in evidence else "not_grounded"

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return Decision(
            label=label,
            confidence=0.99 if label == "grounded" else 0.85 if label == "multiple" else 0.90,
            latency_ms=elapsed_ms,
            backend=self.backend,
        )


class HttpDecider:
    """HTTP client adapter for Strands Decider 2B server running on cloud GPU.
    Endpoint: POST /v1/systemone
    Sends batched questions sharing a common state prefix to leverage prefix caching.

    Per hackathon rules:
    - Never invent response shapes. Response parser is implemented ONLY after
      capturing a real response from the server into docs/journal/sample_response.json.
    - All network calls are timed with high-precision perf_counter.
    - Fail-closed: errors and timeouts yield ambiguous with confidence 0.0 and backend 'decider_error'.
    """
    backend = "real"

    def __init__(
        self,
        endpoint_url: str | None = None,
        model: str = "hobson-latest",
        timeout_s: float = 10.0,
        fail_closed: bool = True,
    ):
        self.endpoint_url = (endpoint_url or os.getenv("DECIDER_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.model = model
        self.timeout_s = timeout_s
        self.fail_closed = fail_closed

    def build_payload(self, state: str, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Build the POST /v1/systemone request body."""
        return {
            "state": state,
            "model": self.model,
            "questions": questions,
        }

    def _post(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, float, str | None]:
        """Send HTTP POST to /v1/systemone and measure exact round-trip latency.
        Returns: (response_json, latency_ms, error_message).
        """
        url = f"{self.endpoint_url}/v1/systemone"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8")
                latency_ms = (time.perf_counter() - t0) * 1000.0
                parsed = json.loads(raw)
                return parsed, latency_ms, None
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            logger.error("Decider HTTP error (%s): %s", url, exc)
            return None, latency_ms, str(exc)

    def decide_many(
        self,
        state: str,
        questions: dict[str, dict[str, Any]],
    ) -> dict[str, Decision]:
        """Send batched questions in one request.

        Stage A(a): Request building, timeouts, network timing, and fail-closed handling are live.
        Stage A(b): Response parser is deferred until sample_response.json is verified.
        """
        payload = self.build_payload(state, questions)
        resp_json, latency_ms, err = self._post(payload)

        if err is not None or resp_json is None:
            if self.fail_closed:
                return {
                    q_name: Decision("ambiguous", 0.0, latency_ms, "decider_error")
                    for q_name in questions
                }
            else:
                return {
                    q_name: Decision("grounded", 1.0, latency_ms, "error_open")
                    for q_name in questions
                }

        # Response parser deferred to Stage A(b) pending sample_response.json
        raise NotImplementedError(
            "Response parser deferred until real response shape is verified from docs/journal/sample_response.json"
        )

    def decide(self, state: str, question: str, q: TypedQuestion) -> Decision:
        """Single-question adapter compatibility."""
        q_spec = {
            "type": "noul",
            "instructions": question,
        }
        results = self.decide_many(state, {"q0": q_spec})
        return results["q0"]


# Backward-compatible alias
RealDecider = HttpDecider
