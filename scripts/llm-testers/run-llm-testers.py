#!/usr/bin/env python3
"""Small, dependency-free OpenAI-compatible model verification suite.

The suite is intentionally deterministic: every task has a bounded answer
format and a local grader. Results include the server-reported model, latency,
usage, raw answers, and per-tester scores so throttling or substitution is
visible rather than hidden behind a single aggregate score.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


TASKS = [
    {"tester": "instruction-following", "id": "format", "system": "Return only valid JSON with exactly the keys answer and explanation. answer must be the integer 42.", "user": "What is the answer?", "grade": "json42"},
    {"tester": "instruction-following", "id": "constraint", "system": "Reply with exactly three words. No punctuation.", "user": "Name three primary colors.", "grade": "three_words"},
    {"tester": "reasoning", "id": "logic", "system": "Answer with only the requested letter.", "user": "A box has 3 red, 2 blue, and 1 green marble. Without looking, what is the minimum number drawn to guarantee two are the same color? Choose A=2, B=3, C=4, D=5.", "grade": "letter_c"},
    {"tester": "reasoning", "id": "arithmetic", "system": "Answer with only a number.", "user": "Compute (17 * 19) - (8 * 13).", "grade": "number219"},
    {"tester": "coding", "id": "bugfix", "system": "Return only the corrected one-line Python expression.", "user": "Fix this expression so it returns the larger value: min(a, b)", "grade": "max_expr"},
    {"tester": "knowledge", "id": "quoted-fact", "system": "Answer with only the requested word.", "user": "In the sentence 'The quick brown fox jumps over the lazy dog', what animal jumps?", "grade": "fox"},
]


def grade(kind: str, text: str) -> tuple[bool, str]:
    value = text.strip()
    if kind == "json42":
        try:
            obj = json.loads(value)
            ok = set(obj) == {"answer", "explanation"} and obj["answer"] == 42
        except (ValueError, TypeError):
            ok = False
        return ok, "valid JSON object with answer=42 and exactly two keys"
    if kind == "three_words":
        words = value.split()
        return len(words) == 3 and all(word.isalpha() for word in words), "exactly three alphabetic words"
    if kind == "letter_c":
        return value.upper() == "C", "answer C"
    if kind == "number219":
        return value == "219", "number 219"
    if kind == "max_expr":
        normalized = value.replace(" ", "").lower()
        return normalized in {"max(a,b)", "max(a,b)"}, "max(a, b) expression"
    if kind == "fox":
        return value.lower() == "fox", "word fox"
    return False, "unknown grader"


def endpoint(url: str) -> str:
    url = url.rstrip("/")
    return url if url.endswith("/chat/completions") else url + "/chat/completions"


def call(url: str, key: str, model: str, task: dict, temperature: float, max_tokens: int, timeout: int) -> dict:
    body = {"model": model, "messages": [{"role": "system", "content": task["system"]}, {"role": "user", "content": task["user"]}], "temperature": temperature, "max_tokens": max_tokens}
    request = urllib.request.Request(endpoint(url), data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        elapsed = time.perf_counter() - started
        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        text = message.get("content") or choice.get("text") or ""
        ok, rule = grade(task["grade"], text)
        return {"status": "ok", "http_model": payload.get("model"), "answer": text, "passed": ok, "rule": rule, "latency_ms": round(elapsed * 1000, 1), "usage": payload.get("usage"), "finish_reason": choice.get("finish_reason")}
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        elapsed = time.perf_counter() - started
        detail = getattr(exc, "read", lambda: b"")()
        return {"status": "error", "error": str(exc), "response": detail.decode(errors="replace")[:1000], "latency_ms": round(elapsed * 1000, 1), "passed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeatable A6API Sol/Luna verification testers")
    parser.add_argument("--base-url", default=os.getenv("A6API_BASE_URL"), help="OpenAI-compatible base URL, e.g. https://host/v1")
    parser.add_argument("--api-key", default=os.getenv("A6API_API_KEY"), help=argparse.SUPPRESS)
    parser.add_argument("--models", nargs="+", default=["gpt-6.1-sol", "gpt-6-luna"])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--max-tokens", type=int, default=120)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--out", default=None, help="JSON result path (default: monitoring/llm-test-<UTC>.json)")
    args = parser.parse_args()
    if not args.base_url:
        parser.error("--base-url or A6API_BASE_URL is required")
    if not args.api_key:
        parser.error("--api-key or A6API_API_KEY is required")
    if args.repeats < 1 or args.repeats > 20:
        parser.error("--repeats must be between 1 and 20")
    out = Path(args.out) if args.out else Path("monitoring") / ("llm-test-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
    results = []
    for model in args.models:
        for repeat in range(1, args.repeats + 1):
            for task in TASKS:
                result = call(args.base_url, args.api_key, model, task, args.temperature, args.max_tokens, args.timeout)
                results.append({"model_requested": model, "repeat": repeat, **{k: task[k] for k in ("tester", "id")}, **result})
                print(f"{model:16} {task['tester']:20} {task['id']:12} {'PASS' if result['passed'] else 'FAIL'} {result['latency_ms']:>8} ms")
    by_model = {}
    for model in args.models:
        rows = [r for r in results if r["model_requested"] == model]
        latencies = [r["latency_ms"] for r in rows if r["status"] == "ok"]
        by_model[model] = {"requests": len(rows), "passed": sum(bool(r["passed"]) for r in rows), "score": round(sum(bool(r["passed"]) for r in rows) / len(rows), 4) if rows else 0, "median_latency_ms": round(statistics.median(latencies), 1) if latencies else None, "errors": sum(r["status"] != "ok" for r in rows), "reported_models": sorted({r["http_model"] for r in rows if r.get("http_model")})}
    report = {"schema": "a6api-llm-test/v1", "generated_at": datetime.now(timezone.utc).isoformat(), "base_url_host": urllib.parse.urlparse(args.base_url).netloc, "models": by_model, "tasks": len(TASKS), "repeats": args.repeats, "results": results, "interpretation": "Scores test behavior and routing evidence; they cannot prove model identity. Compare repeated runs and reported_models against the requested model."}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(by_model, indent=2))
    print(f"Raw report: {out}")
    return 0 if all(v["errors"] == 0 for v in by_model.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
