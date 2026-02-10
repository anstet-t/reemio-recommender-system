#!/usr/bin/env python3
"""Load test / benchmark script for the recommendation API.

Usage:
    uv run python scripts/benchmark.py --base-url http://localhost:8000 --concurrency 10 --requests 100
"""

import argparse
import asyncio
import statistics
import time

import httpx

ENDPOINTS = [
    ("/api/v1/recommendations/homepage", {"user_id": "user-001", "limit": "12"}),
    ("/api/v1/recommendations/product/prod-001", {"limit": "8"}),
    ("/api/v1/recommendations/frequently-bought-together/prod-001", {"limit": "4"}),
    ("/api/v1/recommendations/search", {"query": "Notebook", "limit": "12"}),
    ("/api/v1/recommendations/search", {"query": "Sugar", "user_id": "user-001", "limit": "8"}),
    ("/api/v1/health", {}),
]


async def make_request(
    client: httpx.AsyncClient, url: str, params: dict
) -> tuple[str, float, int]:
    start = time.perf_counter()
    try:
        resp = await client.get(url, params=params)
        duration = time.perf_counter() - start
        return url, duration, resp.status_code
    except Exception:
        duration = time.perf_counter() - start
        return url, duration, 0


async def run_benchmark(base_url: str, concurrency: int, total_requests: int) -> None:
    results: dict[str, list[float]] = {ep[0]: [] for ep in ENDPOINTS}
    errors: dict[str, int] = {ep[0]: 0 for ep in ENDPOINTS}

    sem = asyncio.Semaphore(concurrency)

    async def bounded_request(client: httpx.AsyncClient, path: str, params: dict) -> None:
        async with sem:
            url = f"{base_url}{path}"
            _, duration, status = await make_request(client, url, params)
            if 200 <= status < 300:
                results[path].append(duration)
            else:
                errors[path] += 1

    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = []
        for i in range(total_requests):
            path, params = ENDPOINTS[i % len(ENDPOINTS)]
            tasks.append(bounded_request(client, path, params))

        overall_start = time.perf_counter()
        await asyncio.gather(*tasks)
        overall_duration = time.perf_counter() - overall_start

    # Print report
    print(f"\n{'=' * 70}")
    print("REEMIO RECOMMENDER - BENCHMARK REPORT")
    print(f"{'=' * 70}")
    print(f"Total requests: {total_requests} | Concurrency: {concurrency}")
    print(f"Total time: {overall_duration:.2f}s | RPS: {total_requests / overall_duration:.1f}")
    print(f"{'=' * 70}\n")

    for path, latencies in results.items():
        if not latencies:
            print(f"{path}: No successful requests (errors: {errors[path]})")
            continue
        sorted_lat = sorted(latencies)
        p95_idx = min(int(len(sorted_lat) * 0.95), len(sorted_lat) - 1)
        print(f"{path}")
        print(f"  Requests : {len(latencies)} OK, {errors[path]} errors")
        print(f"  Avg      : {statistics.mean(latencies) * 1000:.1f}ms")
        print(f"  P50      : {statistics.median(latencies) * 1000:.1f}ms")
        print(f"  P95      : {sorted_lat[p95_idx] * 1000:.1f}ms")
        print(f"  Min/Max  : {min(latencies) * 1000:.1f}ms / {max(latencies) * 1000:.1f}ms")
        print()

    # Fetch server-side profile if available
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{base_url}/api/v1/benchmarks/profile")
            if resp.status_code == 200:
                profile = resp.json()
                print(f"{'=' * 70}")
                print("SERVER-SIDE PROFILE")
                print(f"{'=' * 70}")
                res = profile.get("system_resources", {})
                print(f"  CPU      : {res.get('cpu_percent', 'N/A')}%")
                print(f"  Memory   : {res.get('memory_rss_mb', 'N/A')} MB RSS")
                print(f"  Threads  : {res.get('threads', 'N/A')}")
                pool = profile.get("database_pool", {})
                print(f"  DB Pool  : {pool.get('checked_out', 'N/A')} out / {pool.get('pool_size', 'N/A')} size")
                cache = profile.get("cache_status", {})
                print(f"  Cache    : {'connected' if cache.get('connected') else 'disconnected'}")
                print()
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the Reemio recommendation API")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--requests", type=int, default=100)
    args = parser.parse_args()

    asyncio.run(run_benchmark(args.base_url, args.concurrency, args.requests))


if __name__ == "__main__":
    main()
