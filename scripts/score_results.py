#!/usr/bin/env python3
"""Normalize a run and report accuracy by benchmark role and task family."""
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "cases.jsonl"
RUNS = ROOT / "results"
PRICE = 0.042


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def write_csv(path, rows):
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def quantile(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[max(0, math.ceil(q * len(xs)) - 1)]


def metrics(rows):
    valid = [r for r in rows if r["valid_response"]]
    correct = sum(r["correct"] for r in valid)
    latency = [r["latency_ms"] for r in valid if r["latency_ms"] is not None]
    return {
        "cases": len(rows), "valid_answers": len(valid), "correct": correct,
        "incorrect": len(valid) - correct, "provider_failures": len(rows) - len(valid),
        "accuracy": correct / len(valid) if valid else None,
        "mean_latency_ms": sum(latency) / len(latency) if latency else None,
        "p50_latency_ms": quantile(latency, .5), "p95_latency_ms": quantile(latency, .95),
        "input_tokens": sum(r["input_tokens"] or 0 for r in valid),
        "output_tokens": sum(r["output_tokens"] or 0 for r in valid),
        "estimated_cost_usd": sum(r["estimated_cost_usd"] or 0 for r in valid),
    }


def main():
    digest = hashlib.sha256(CASES.read_bytes()).hexdigest()
    expected_digest = json.loads((ROOT / "benchmark-manifest.json").read_text())["cases_sha256"]
    if digest != expected_digest:
        raise SystemExit("cases.jsonl differs from its frozen manifest; refusing to score.")
    cases = [json.loads(line) for line in CASES.read_text().splitlines() if line.strip()]
    for run_dir in sorted(p for p in RUNS.iterdir() if p.is_dir() and (p / "raw-responses.jsonl").exists()):
        events = [json.loads(line) for line in (run_dir / "raw-responses.jsonl").read_text().splitlines() if line.strip()]
        latest = {event["case_id"]: event for event in events}
        normalized = []
        for case in cases:
            event = latest.get(case["case_id"])
            response = (event or {}).get("response") or {}
            decision = (response.get("answers") or {}).get("decision") or {}
            probs = decision.get("probabilities")
            selected = decision.get("choice")
            valid = (event or {}).get("http_status") == 200 and selected in case["choices"] and isinstance(probs, dict) and set(probs) == set(case["choices"])
            ranked = sorted(((float(value), label) for label, value in (probs or {}).items()), reverse=True)
            top_p, top_label = ranked[0] if ranked else (None, None)
            second = ranked[1][0] if len(ranked) > 1 else None
            entropy = -sum(float(p) * math.log2(float(p)) for p in (probs or {}).values() if float(p) > 0) if probs else None
            usage = response.get("usage") or {}
            input_tokens = usage.get("input_tokens", usage.get("inputTokens"))
            output_tokens = usage.get("output_tokens", usage.get("outputTokens"))
            normalized.append({
                **case, "selected_answer": selected if valid else None,
                "probabilities": probs, "top_choice": top_label, "top_probability": top_p,
                "second_probability": second, "top_two_margin": top_p - second if top_p is not None and second is not None else None,
                "entropy_bits": entropy, "correct": selected == case["expected_answer"] if valid else None,
                "valid_response": valid, "provider_status": (event or {}).get("http_status"),
                "error": (event or {}).get("error"), "request_id": (event or {}).get("request_id"),
                "resolved_model": response.get("model"), "latency_ms": (event or {}).get("latency_ms"),
                "input_tokens": input_tokens, "output_tokens": output_tokens,
                "estimated_cost_usd": None if input_tokens is None else input_tokens * PRICE / 1_000_000,
            })
        (run_dir / "results.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in normalized))
        semantic = [r for r in normalized if r["benchmark_role"] == "semantic_decision"]
        controls = [r for r in normalized if r["benchmark_role"] == "deterministic_control"]
        ambiguous = [r for r in normalized if r["label_status"] == "INTENTIONAL_AMBIGUITY"]
        summary = {
            "benchmark_name": "System One Model Benchmark", "benchmark_version": "1.0", "cases_sha256": digest,
            "model": sorted({r["resolved_model"] for r in normalized if r["resolved_model"]}),
            "all_cases": metrics(normalized), "semantic_decisions": metrics(semantic),
            "deterministic_controls": metrics(controls), "intentional_ambiguity": metrics(ambiguous),
        }
        write_json(run_dir / "summary.json", summary)
        families=[]
        for family in sorted({r["task_family"] for r in semantic}):
            rows=[r for r in semantic if r["task_family"] == family]
            families.append({"task_family":family, **metrics(rows)})
        write_csv(run_dir / "task-family-results.csv", families)
        errors=[r for r in normalized if r["valid_response"] and not r["correct"] and r["top_probability"] >= .90]
        write_csv(run_dir / "high-confidence-errors.csv", [{
            "case_id":r["case_id"],"task_family":r["task_family"],"benchmark_role":r["benchmark_role"],
            "expected_answer":r["expected_answer"],"selected_answer":r["selected_answer"],
            "top_probability":r["top_probability"],"probabilities":json.dumps(r["probabilities"],sort_keys=True)
        } for r in errors])
        lines=["# First evaluation — Jev 1.13.0", "", f"Frozen cases SHA-256: `{digest}`.", "",
        "| Slice | Correct | Accuracy | Provider failures | Cost | Mean / p50 / p95 latency |", "|---|---:|---:|---:|---:|---:|"]
        for label,key in (("All cases","all_cases"),("Semantic decisions","semantic_decisions"),("Deterministic controls","deterministic_controls"),("Intentional ambiguity","intentional_ambiguity")):
            m=summary[key]
            lines.append(f"| {label} | {m['correct']}/{m['cases']} | {m['accuracy']:.1%} | {m['provider_failures']} | ${m['estimated_cost_usd']:.9f} | {m['mean_latency_ms']:.2f} / {m['p50_latency_ms']:.2f} / {m['p95_latency_ms']:.2f} ms |")
        lines += ["", "Task-family metrics are in `task-family-results.csv`. Run `python scripts/analyze_uncertainty.py` for exploratory error ranking.", ""]
        (run_dir / "summary.md").write_text("\n".join(lines))
        print(json.dumps({"run":run_dir.name,"all_cases":summary["all_cases"],"semantic_decisions":summary["semantic_decisions"]},indent=2))


if __name__ == "__main__":
    main()
