"""Small, repeatable HTTP concurrency baseline for a running GreyGuard API."""

import argparse
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(len(ordered) * fraction) - 1))]


def request_once(url: str, timeout: float) -> tuple[int, float]:
    started = time.perf_counter()
    try:
        response = httpx.get(url, timeout=timeout)
        return response.status_code, (time.perf_counter() - started) * 1000
    except httpx.HTTPError:
        return 0, (time.perf_counter() - started) * 1000


def benchmark(base_url: str, endpoint: str, requests: int, concurrency: int, timeout: float):
    url = base_url.rstrip("/") + "/" + endpoint.lstrip("/")
    started = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(request_once, url, timeout) for _ in range(requests)]
        for future in as_completed(futures):
            results.append(future.result())
    elapsed = time.perf_counter() - started
    statuses = Counter(status for status, _ in results)
    latencies = [latency for _, latency in results]
    successes = sum(count for status, count in statuses.items() if 200 <= status < 400)
    return {
        "url": url,
        "requests": requests,
        "concurrency": concurrency,
        "elapsed_seconds": round(elapsed, 4),
        "requests_per_second": round(requests / elapsed, 2),
        "success_rate": round(successes / requests, 4),
        "status_counts": {str(key): value for key, value in sorted(statuses.items())},
        "latency_ms": {
            "minimum": round(min(latencies), 2),
            "median": round(percentile(latencies, 0.50), 2),
            "p95": round(percentile(latencies, 0.95), 2),
            "maximum": round(max(latencies), 2),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--endpoint", default="/health")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--minimum-success-rate", type=float, default=1.0)
    parser.add_argument("--output", default="artifacts/performance-baseline.json")
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("requests and concurrency must be positive")
    result = benchmark(
        args.base_url, args.endpoint, args.requests, args.concurrency, args.timeout
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["success_rate"] < args.minimum_success_rate:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
