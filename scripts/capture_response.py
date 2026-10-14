#!/usr/bin/env python3
"""
scripts/capture_response.py — Stage A(a) spike & calibration tool.

Sends ONE batched POST /v1/systemone request (multiple noul questions sharing one state)
to the cloud Decider 2B server at DECIDER_URL.
Prints the raw response, records measured latency, and writes docs/journal/sample_response.json.

Usage:
    python scripts/capture_response.py [DECIDER_URL]
Or:
    export DECIDER_URL="http://<cloud-gpu-ip>:8000"
    python scripts/capture_response.py
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_URL = os.getenv("DECIDER_URL", "http://127.0.0.1:8000")
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "journal" / "sample_response.json"

# Realistic multi-argument test case with shared state
SAMPLE_STATE = """USER STATEMENTS:
[0] Please send 50 dollars to Sam for lunch today and email Priya at priya@example.com

PROPOSED CALL: send_payment(recipient='sam', amount=50.0, date='tomorrow')"""

SAMPLE_QUESTIONS = {
    "recipient_check": {
        "type": "noul",
        "instructions": "Does the user's text support 'sam' as the payment recipient?",
        "criteria": "The user explicitly mentioned Sam as the recipient of the payment.",
    },
    "amount_check": {
        "type": "noul",
        "instructions": "Does the user's text support '50.0' as the payment amount?",
        "criteria": "The user explicitly stated 50 dollars.",
    },
    "invented_date_check": {
        "type": "noul",
        "instructions": "Does the user's text support 'tomorrow' as the payment date?",
        "criteria": "The user explicitly specified tomorrow as the payment date.",
    },
}


def capture(url: str) -> int:
    endpoint = url.rstrip("/") + "/v1/systemone"
    payload = {
        "state": SAMPLE_STATE,
        "model": "hobson-latest",
        "questions": SAMPLE_QUESTIONS,
    }

    print("=" * 70)
    print("STAGE A(a) — DECIDER 2B RAW RESPONSE CAPTURE")
    print("=" * 70)
    print(f"Target endpoint: {endpoint}")
    print(f"Model: {payload['model']}")
    print(f"Questions in batch: {list(SAMPLE_QUESTIONS.keys())}")
    print("-" * 70)

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            raw_body = resp.read().decode("utf-8")
            latency_ms = (time.perf_counter() - t0) * 1000.0
            status_code = resp.status
    except urllib.error.HTTPError as exc:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        err_body = exc.read().decode("utf-8", errors="replace")
        print(f"\n[HTTP ERROR {exc.code} in {latency_ms:.1f}ms]: {err_body}")
        return 1
    except urllib.error.URLError as exc:
        print(f"\n[CONNECTION FAILED]: {exc.reason}")
        print("\nPlease ensure your cloud Decider server is running and reachable:")
        print("  1. Run on cloud GPU: strands-decider serve <checkpoint> --port 8000")
        print("  2. Set DECIDER_URL=http://<ip>:8000")
        print("  3. Check health: curl http://<ip>:8000/health")
        return 2
    except Exception as exc:
        print(f"\n[UNEXPECTED ERROR]: {exc}")
        return 3

    print(f"HTTP Status: {status_code}")
    print(f"Measured Round-Trip Latency: {latency_ms:.2f} ms")
    print("-" * 70)
    print("Raw Response Body:")
    print(raw_body)
    print("-" * 70)

    try:
        parsed = json.loads(raw_body)
    except Exception as exc:
        print(f"Could not parse response as JSON: {exc}")
        parsed = {"raw": raw_body}

    capture_record = {
        "_metadata": {
            "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "endpoint": endpoint,
            "measured_latency_ms": round(latency_ms, 2),
            "status_code": status_code,
        },
        "request_payload": payload,
        "response": parsed,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(capture_record, indent=2), encoding="utf-8")
    print(f"\nSaved capture record to: {OUTPUT_PATH}")
    print("=" * 70)
    print("Next step: Paste the raw response back to Antigravity to implement the parser in Stage A(b).")
    return 0


if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    sys.exit(capture(target_url))
