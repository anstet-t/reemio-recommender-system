# Performance Benchmark Results

**Date:** 2026-02-10
**Baseline commit:** `5e515c2` (before optimization)
**Optimized commit:** `2a49564` (after optimization)
**Config:** 5 concurrent clients, 6 requests per endpoint (24 total), with warmup

## Summary

| Metric | Before | After | Change |
|---|---|---|---|
| Total wall time | 3.64s | 2.68s | 26.5% faster |
| Throughput (RPS) | 6.6 | 9.0 | +36.0% |

## Average Latency by Endpoint

| Endpoint | Before | After | Change |
|---|---|---|---|
| `/recommendations/homepage` | 1065ms | 779ms | 26.9% faster |
| `/recommendations/product/{id}` | 803ms | 556ms | 30.7% faster |
| `/recommendations/frequently-bought-together/{id}` | 892ms | 658ms | 26.3% faster |
| `/health` | 1.6ms | 2.2ms | ~same (sub-ms noise) |

## P50 / P95 Latency

| Endpoint | P50 Before | P50 After | P95 Before | P95 After |
|---|---|---|---|---|
| homepage | 1047ms | 785ms | 1138ms | 960ms |
| product | 769ms | 490ms | 1003ms | 805ms |
| frequently-bought-together | 889ms | 626ms | 923ms | 925ms |

## What Changed

1. **Numpy vectorized cosine similarity** - replaced Python loop over 200 products with batch `np.dot()` matrix operation
2. **orjson** - replaced `json.loads/dumps` with 3-5x faster alternative
3. **Connection pooling** - switched from `NullPool` (new TCP per query) to `AsyncAdaptedQueuePool` (5 reusable connections)
4. **Database indexes** - partial indexes matching exact query WHERE clauses
5. **Redis caching** - user embeddings (1hr TTL), popular products (30min TTL)

## How to Reproduce

```bash
# Run the A/B benchmark script against a running server
uv run python scripts/bench_ab.py http://localhost:8000

# Or use the full benchmark suite
uv run python scripts/benchmark.py --base-url http://localhost:8000 --concurrency 5 --requests 24
```

## Raw Data

- [`baseline_5e515c2.json`](baseline_5e515c2.json) - pre-optimization results
- [`optimized_2a49564.json`](optimized_2a49564.json) - post-optimization results
