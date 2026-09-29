#!/usr/bin/env python3
"""Evaluate each frozen case once through TypeSafe's public Jev endpoint."""
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "cases.jsonl"
EXPECTED_SHA = "0a68ef2adbbb7c923a9dce8012987488dd4a291fe9697767854e0e01f6a221bf"
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"


def load_dotenv():
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.strip().strip("\"'")
        if name.strip() == "JEV_API_KEY" and value and not os.environ.get(name.strip()):
            os.environ[name.strip()] = value


def append_jsonl(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def response_request_id(headers):
    for name in ("x-request-id", "request-id", "x-correlation-id"):
        value = headers.get(name)
        if value:
            return value
    return None


def send(case, key, digest):
    choices = case["choices"]
    request_body = {
        "model": MODEL,
        "state": case["state"],
        "questions": {
            "decision": {
                "type": "choice",
                "instructions": case["question"],
                "criteria": {c: f"The supplied evidence supports the classification {c}." for c in choices},
            }
        },
    }
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": "TypeSafe direct API",
        "requested_model_alias": MODEL,
        "endpoint": ENDPOINT,
        "cases_sha256": digest,
        "case_id": case["case_id"],
        "request_id": None,
        "request": request_body,
        "response": None,
        "http_status": None,
        "latency_ms": None,
        "error": None,
    }
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            event["http_status"] = response.status
            event["request_id"] = response_request_id(response.headers)
            try:
                event["response"] = json.loads(response.read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                event["error"] = {"kind": "invalid_json_response"}
    except urllib.error.HTTPError as error:
        event["http_status"] = error.code
        event["request_id"] = response_request_id(error.headers)
        event["error"] = {"kind": "http_error", "message": f"HTTP {error.code}"}
    except Exception as error:
        event["error"] = {"kind": "transport_error", "message": type(error).__name__}
    event["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return event


def main():
    load_dotenv()
    key = os.environ.get("JEV_API_KEY")
    if not key:
        raise SystemExit("Set JEV_API_KEY in .env or the environment; no credential is stored in this repository.")
    digest = hashlib.sha256(CASES.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA:
        raise SystemExit(f"Frozen cases SHA mismatch; expected {EXPECTED_SHA}, got {digest}. Stopped before requests.")
    cases = [json.loads(line) for line in CASES.read_text().splitlines() if line.strip()]
    if len(cases) != 160 or len({c["case_id"] for c in cases}) != 160:
        raise SystemExit("Expected 160 uniquely identified cases; stopped before requests.")
    run_id = os.environ.get("JEV_RUN_ID") or datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    out = ROOT / "results" / run_id
    raw = out / "raw-responses.jsonl"
    manifest_path = out / "run-manifest.json"
    existing = set()
    if raw.exists():
        for line in raw.read_text().splitlines():
            try:
                event = json.loads(line)
                if event.get("http_status") == 200 and event.get("response", {}).get("answers", {}).get("decision", {}).get("choice"):
                    existing.add(event["case_id"])
            except (ValueError, KeyError, TypeError):
                pass
    start = datetime.now(timezone.utc).isoformat()
    for index, case in enumerate(cases, 1):
        if case["case_id"] in existing:
            continue
        event = send(case, key, digest)
        append_jsonl(raw, event)
        if event["http_status"] == 503:
            time.sleep(1.5)
            retry = send(case, key, digest)
            retry["retry_of_status"] = 503
            append_jsonl(raw, retry)
            event = retry
        print(json.dumps({"case": case["case_id"], "completed": index, "total": len(cases), "status": event["http_status"]}), flush=True)
        if event["http_status"] in (401, 403, 429):
            raise SystemExit("Stopped after authentication or rate-limit response; inspect the recorded event before resuming.")
    events = [json.loads(line) for line in raw.read_text().splitlines() if line.strip()]
    resolved = sorted({e["response"].get("model") for e in events if e.get("response", {}).get("model")})
    manifest = {
        "benchmark_name": "System One Model Benchmark", "benchmark_version": "1.0",
        "cases_sha256": digest, "provider": "TypeSafe direct API", "endpoint": ENDPOINT,
        "requested_model_alias": MODEL, "resolved_models": resolved,
        "run_start_utc": events[0]["timestamp"] if events else start,
        "run_end_utc": events[-1]["timestamp"] if events else start,
        "request_events": len(events), "distinct_cases": len({e["case_id"] for e in events}),
        "retry_policy": "No retry for successful output; one retry for HTTP 503 with the same public input.",
        "expected_answer_sent_to_model": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
