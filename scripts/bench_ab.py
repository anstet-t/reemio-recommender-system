#!/usr/bin/env python3
"""Standalone benchmark runner - outputs JSON results. No project dependencies needed."""

import asyncio
import json
import statistics
import sys
import time

import httpx

# Only endpoints that exist in BOTH old and new code
ENDPOINTS = [
    ("/api/v1/recommendations/homepage", {"user_id": "user-001", "limit": "12"}),
    ("/api/v1/recommendations/product/prod-001", {"limit": "8"}),
    ("/api/v1/recommendations/frequently-bought-together/prod-001", {"limit": "4"}),
    ("/api/v1/health", {}),
]

CONCURRENCY = 5
REQUESTS_PER_ENDPOINT = 6  # total = 24


async def make_request(client, url, params):
    start = time.perf_counter()
    try:
        resp = await client.get(url, params=params)
        return url, time.perf_counter() - start, resp.status_code
    except Exception:
        return url, time.perf_counter() - start, 0


async def run(base_url):
    results = {ep[0]: [] for ep in ENDPOINTS}
    errors = {ep[0]: 0 for ep in ENDPOINTS}
    sem = asyncio.Semaphore(CONCURRENCY)

    async def bounded(client, path, params):
        async with sem:
            _, dur, status = await make_request(client, f"{base_url}{path}", params)
            if 200 <= status < 300:
                results[path].append(dur)
            else:
                errors[path] += 1

    # Warmup - 1 request per endpoint to avoid cold start skew
    async with httpx.AsyncClient(timeout=60.0) as client:
        for path, params in ENDPOINTS:
            await make_request(client, f"{base_url}{path}", params)

    # Actual benchmark
    total = REQUESTS_PER_ENDPOINT * len(ENDPOINTS)
    async with httpx.AsyncClient(timeout=60.0) as client:
        tasks = []
        for _ in range(REQUESTS_PER_ENDPOINT):
            for path, params in ENDPOINTS:
                tasks.append(bounded(client, path, params))

        start = time.perf_counter()
        await asyncio.gather(*tasks)
        wall_time = time.perf_counter() - start

    output = {"wall_time": wall_time, "total_requests": total, "endpoints": {}}
    for path, lats in results.items():
        if not lats:
            output["endpoints"][path] = {"ok": 0, "errors": errors[path]}
            continue
        s = sorted(lats)
        output["endpoints"][path] = {
            "ok": len(lats),
            "errors": errors[path],
            "avg_ms": round(statistics.mean(lats) * 1000, 1),
            "p50_ms": round(statistics.median(lats) * 1000, 1),
            "p95_ms": round(s[min(int(len(s) * 0.95), len(s) - 1)] * 1000, 1),
            "min_ms": round(min(lats) * 1000, 1),
            "max_ms": round(max(lats) * 1000, 1),
        }

    json.dump(output, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    asyncio.run(run(base))
