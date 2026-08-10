"""Lightweight metrics helpers shared by PayOrbit services."""

from __future__ import annotations

import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Iterator


class Counter:
    def __init__(self, name: str) -> None:
        self.name = name
        self._values: dict[tuple[tuple[str, str], ...], int] = defaultdict(int)

    def inc(self, amount: int = 1, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        self._values[key] += amount

    def get(self, **labels: str) -> int:
        key = tuple(sorted(labels.items()))
        return self._values[key]


class Timer:
    def __init__(self, name: str) -> None:
        self.name = name
        self._samples: list[float] = []

    @contextmanager
    def time(self) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self._samples.append(time.perf_counter() - start)

    def p95(self) -> float:
        if not self._samples:
            return 0.0
        ordered = sorted(self._samples)
        idx = max(0, int(len(ordered) * 0.95) - 1)
        return ordered[idx]


REQUESTS = Counter("payorbit_requests_total")
ERRORS = Counter("payorbit_errors_total")
LATENCY = Timer("payorbit_request_latency_seconds")
