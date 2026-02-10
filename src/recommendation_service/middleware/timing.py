"""Request timing middleware for API performance tracking."""

import time
from collections import defaultdict
from dataclasses import dataclass, field

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()

MAX_SAMPLES = 1000


@dataclass
class EndpointStats:
    """Track latency statistics for an endpoint."""

    latencies: list[float] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.latencies)

    @property
    def p50(self) -> float:
        if not self.latencies:
            return 0.0
        s = sorted(self.latencies)
        return s[len(s) // 2]

    @property
    def p95(self) -> float:
        if not self.latencies:
            return 0.0
        s = sorted(self.latencies)
        return s[min(int(len(s) * 0.95), len(s) - 1)]

    @property
    def avg(self) -> float:
        return sum(self.latencies) / len(self.latencies) if self.latencies else 0.0

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "avg_ms": round(self.avg * 1000, 2),
            "p50_ms": round(self.p50 * 1000, 2),
            "p95_ms": round(self.p95 * 1000, 2),
        }


_endpoint_stats: dict[str, EndpointStats] = defaultdict(EndpointStats)


def get_endpoint_stats() -> dict[str, dict]:
    """Get collected endpoint timing stats."""
    return {path: stats.to_dict() for path, stats in _endpoint_stats.items()}


def reset_endpoint_stats() -> None:
    """Reset all collected stats."""
    _endpoint_stats.clear()


class TimingMiddleware(BaseHTTPMiddleware):
    """Adds X-Response-Time-Ms header and collects per-endpoint latency stats."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        path = request.url.path
        stats = _endpoint_stats[path]
        stats.latencies.append(duration)
        if len(stats.latencies) > MAX_SAMPLES:
            stats.latencies = stats.latencies[-MAX_SAMPLES:]

        response.headers["X-Response-Time-Ms"] = str(round(duration * 1000, 2))

        logger.debug(
            "request_completed",
            path=path,
            method=request.method,
            status=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )

        return response
