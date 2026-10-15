"""Load, connection and queue benchmarks against a real GreyGuard server (roadmap P3).

Starts the API with uvicorn in a throwaway data directory (SQLite) or against a PostgreSQL URL you
provide, then measures over real HTTP:

- read paths: /health and an authenticated GET /entitlements;
- the agent hot path: POST /tool-requests (authentication, policy evaluation, evidence writes);
- gateway policy distribution: GET /gateways/bundle (policy read plus an Ed25519 signature);
- connections: many concurrent /live-events streams held open, with /health latency under them;
- queue drain: security-export queue items processed per second through the real queue code with
  a no-op transport (network time excluded on purpose - it is the receiver's, not GreyGuard's).

Rate limits are raised for the run through the install-operator API, exactly as an operator would
for a load test. Results are observations of this machine, not capacity promises.

  python -m scripts.benchmark_load --output artifacts/benchmarks/sqlite.json
  python -m scripts.benchmark_load --database-url postgresql://... --output artifacts/benchmarks/postgres.json
"""
import argparse
import base64
import json
import os
import platform
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

ROOT = Path(__file__).resolve().parents[1]


def percentile(values, fraction):
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, max(0, int(len(ordered) * fraction) - 1))], 2) if ordered else None


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run_load(client, method, path, total, concurrency, **kwargs):
    latencies, statuses, lock = [], {}, threading.Lock()

    def one(_):
        started = time.perf_counter()
        try:
            status = client.request(method, path, **kwargs).status_code
        except httpx.HTTPError:
            status = 0
        elapsed = (time.perf_counter() - started) * 1000
        with lock:
            latencies.append(elapsed)
            statuses[status] = statuses.get(status, 0) + 1

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        list(pool.map(one, range(total)))
    elapsed = time.perf_counter() - started
    ok = sum(count for status, count in statuses.items() if 200 <= status < 300)
    return {"requests": total, "concurrency": concurrency, "succeeded": ok, "statuses": {str(k): v for k, v in sorted(statuses.items())},
            "throughput_per_second": round(total / elapsed, 1), "p50_ms": percentile(latencies, 0.50),
            "p95_ms": percentile(latencies, 0.95), "p99_ms": percentile(latencies, 0.99)}


def hold_streams(base, token, count, seconds):
    connected, stop = [], threading.Event()

    def stream():
        try:
            with httpx.Client(base_url=base, timeout=seconds + 10) as client:
                with client.stream("GET", "/live-events?include_history=false", headers={"X-Admin-Pin": token}) as response:
                    if response.status_code == 200:
                        connected.append(1)
                    for _ in response.iter_bytes():
                        if stop.is_set():
                            break
        except httpx.HTTPError:
            pass

    threads = [threading.Thread(target=stream, daemon=True) for _ in range(count)]
    for thread in threads:
        thread.start()
    return threads, stop, connected


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url", default="", help="PostgreSQL URL; SQLite in a temp directory when omitted")
    parser.add_argument("--requests", type=int, default=2000)
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--streams", type=int, default=100)
    parser.add_argument("--queue-items", type=int, default=2000)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    data_dir = tempfile.mkdtemp(prefix="greyguard-bench-")
    port, password = free_port(), secrets.token_urlsafe(24)
    signing_key = base64.urlsafe_b64encode(Ed25519PrivateKey.generate().private_bytes(
        Encoding.Raw, PrivateFormat.Raw, NoEncryption())).decode().rstrip("=")
    env = {**os.environ, "GREYGUARD_ENV": "test", "GREYGUARD_DATA_DIR": data_dir,
           "GREYGUARD_BOOTSTRAP_EMAIL": "bench@greyguard.local", "GREYGUARD_BOOTSTRAP_PASSWORD": password,
           "GREYGUARD_BOOTSTRAP_NAME": "Benchmark", "GREYGUARD_TRUSTED_HOSTS": "127.0.0.1,localhost",
           "GREYGUARD_DELIVERY_WORKER_ENABLED": "false", "GREYGUARD_DISTRIBUTION_SIGNING_KEY": signing_key}
    env.pop("GREYGUARD_ADMIN_PIN", None)
    if args.database_url:
        env["GREYGUARD_DATABASE_URL"] = args.database_url
    else:
        env.pop("GREYGUARD_DATABASE_URL", None)
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app.api:app", "--host", "127.0.0.1",
                               "--port", str(port), "--log-level", "warning"], cwd=ROOT, env=env)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(120):
            try:
                if httpx.get(base + "/health/live", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
        else:
            sys.exit("The server did not start.")
        limits = httpx.Limits(max_connections=args.concurrency * 2, max_keepalive_connections=args.concurrency * 2)
        client = httpx.Client(base_url=base, timeout=30, limits=limits)
        login = client.post("/auth/login", json={"email": "bench@greyguard.local", "password": password})
        login.raise_for_status()
        token = login.json()["access_token"]
        admin = {"X-Admin-Pin": token}
        for category in ("GENERAL", "AGENT_ACTION"):
            client.put(f"/abuse-protection/policies/{category}", headers=admin, json={
                "enabled": False, "request_limit": 10_000, "window_seconds": 1, "block_seconds": 1, "max_failed_attempts": 100}).raise_for_status()
        agent = client.post("/agents", headers=admin, json={"agent_name": "bench_agent", "scopes": ["read_file"]})
        agent.raise_for_status()
        agent_headers = {"X-Agent-Name": "bench_agent", "X-Agent-Key": agent.json()["credential"]}
        node = client.post("/gateways", headers=admin, json={"name": "bench-gateway"}).json()
        enrolled = client.post("/gateways/enroll", json={"token": node["enrollment_token"]}).json()
        node_headers = {"X-Gateway-Node": enrolled["node_id"], "X-Gateway-Key": enrolled["node_credential"]}

        n, c = args.requests, args.concurrency
        results = {
            "health": run_load(client, "GET", "/health", n, c),
            "authenticated_read_entitlements": run_load(client, "GET", "/entitlements", n, c, headers=admin),
            "agent_tool_request": run_load(client, "POST", "/tool-requests", n, c, headers=agent_headers,
                                           json={"action": "read_file", "target": "notes.txt", "dry_run": True}),
            "gateway_bundle": run_load(client, "GET", "/gateways/bundle", max(200, n // 4), c, headers=node_headers),
        }
        threads, stop, connected = hold_streams(base, token, args.streams, 30)
        time.sleep(5)
        under = run_load(client, "GET", "/health", 500, 8)
        results["connections"] = {"streams_requested": args.streams, "streams_connected": len(connected),
                                  "health_under_streams": under}
        stop.set()
        client.close()
    finally:
        server.terminate()
        server.wait(timeout=30)

    # Queue drain, in-process against the same database, through the real queue code.
    os.environ.update({k: v for k, v in env.items() if k.startswith("GREYGUARD_")})
    if not args.database_url:
        os.environ.pop("GREYGUARD_DATABASE_URL", None)
    sys.path.insert(0, str(ROOT))
    from backend.app import organizations, security_exports
    destination = security_exports.save_destination(
        "Benchmark SIEM", "SPLUNK", "https://siem.example.com/ingest", True, None, "STANDARD", 10_000, 3, "bench",
        org_id=organizations.DEFAULT_ORG_ID)
    for index in range(args.queue_items):
        security_exports.enqueue_export(destination["destination_id"], {"event_id": index, "summary": "benchmark"}, "bench",
                                        org_id=organizations.DEFAULT_ORG_ID)
    started, processed = time.perf_counter(), 0
    while processed < args.queue_items:
        batch = security_exports.process_queue(lambda *a, **k: None, limit=500)["processed"]
        if not batch:
            break
        processed += batch
    elapsed = time.perf_counter() - started
    results["queue_drain"] = {"items": args.queue_items, "processed": processed,
                              "items_per_second": round(processed / elapsed, 1) if elapsed else None}

    report = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "database": "postgresql" if args.database_url else "sqlite",
              "server": "uvicorn, 1 worker process",
              "machine": {"cpus": os.cpu_count(), "python": platform.python_version(), "platform": platform.platform()},
              "note": "Observations of this machine, not capacity commitments.", "results": results}
    print(json.dumps(report, indent=2))
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
