from __future__ import annotations

import time
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import (
        AsyncGenerator,
    )


@dataclass(slots=True)
class RequestMetrics:
    endpoint: str
    method: str
    duration: float
    success: bool
    cached: bool


class PerformanceMonitor:
    def __init__(
        self,
        max_metrics: int = 1000,
    ) -> None:
        self._metrics: list[RequestMetrics] = []
        self._max_metrics = max_metrics

    @asynccontextmanager
    async def track_request(
        self,
        endpoint: str,
        method: str,
        cached: bool = False,
    ) -> AsyncGenerator[None]:
        start_time = time.time()
        success = True

        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            duration = time.time() - start_time
            self._add_metric(
                RequestMetrics(
                    endpoint=endpoint,
                    method=method,
                    duration=duration,
                    success=success,
                    cached=cached,
                )
            )

    def _add_metric(
        self,
        metric: RequestMetrics,
    ) -> None:
        self._metrics.append(metric)
        if len(self._metrics) > self._max_metrics:
            self._metrics.pop(0)

    def _calculate_basic_stats(
        self,
        metrics: list[RequestMetrics],
    ) -> dict[str, Any]:
        if not metrics:
            return {
                "total_requests": 0,
                "avg_duration": 0,
                "success_rate": 0,
                "cache_hit_rate": 0,
            }

        total = len(metrics)
        successful = sum(
            1 for m in metrics if m.success
        )
        cached = sum(
            1 for m in metrics if m.cached
        )
        avg_duration = (
            sum(m.duration for m in metrics)
            / total
        )

        return {
            "total_requests": total,
            "avg_duration": round(
                avg_duration, 3
            ),
            "success_rate": round(
                (successful / total) * 100, 2
            ),
            "cache_hit_rate": round(
                (cached / total) * 100, 2
            ),
        }

    def get_stats(
        self,
        last_n: int = 100,
    ) -> dict[str, Any]:
        recent = (
            self._metrics[-last_n:]
            if self._metrics
            else []
        )
        stats = self._calculate_basic_stats(
            recent
        )

        if recent:
            stats["fastest_request"] = min(
                m.duration for m in recent
            )
            stats["slowest_request"] = max(
                m.duration for m in recent
            )

        return stats

    def get_endpoint_stats(
        self,
    ) -> dict[str, dict[str, Any]]:
        endpoint_metrics: defaultdict[
            str, list[RequestMetrics]
        ] = defaultdict(list)

        for metric in self._metrics:
            endpoint_metrics[
                metric.endpoint
            ].append(metric)

        return {
            endpoint: self._calculate_basic_stats(
                metrics
            )
            for endpoint, metrics in endpoint_metrics.items()
        }

    def clear_metrics(self) -> None:
        self._metrics.clear()
