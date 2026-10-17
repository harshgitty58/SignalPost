"""Run-wide request/time/cost budget shared by every source.

Every outbound HTTP request (including robots.txt and redirects) goes through
`Budget.acquire`, so the run report's request count is the number the evaluator
cares about, and no phase can overspend the official daily limits.
"""
from __future__ import annotations

import threading
import time
from collections import Counter
from dataclasses import dataclass, field


class BudgetExhausted(Exception):
    """Raised when a phase may not spend more requests or time."""


@dataclass
class Budget:
    max_requests: int = 2000
    max_seconds: float = 45 * 60
    max_cost_usd: float = 10.0
    safety_requests: int = 100
    safety_seconds: float = 180.0
    started: float = field(default_factory=time.monotonic)
    requests: int = 0
    cost_usd: float = 0.0
    per_host: Counter = field(default_factory=Counter)
    per_phase: Counter = field(default_factory=Counter)
    phase_caps: dict[str, int] = field(default_factory=dict)
    refused: Counter = field(default_factory=Counter)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def usable_requests(self) -> int:
        return max(0, self.max_requests - self.safety_requests)

    @property
    def deadline_seconds(self) -> float:
        return max(0.0, self.max_seconds - self.safety_seconds)

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def time_left(self) -> float:
        return self.deadline_seconds - self.elapsed()

    def set_phase_cap(self, phase: str, cap: int) -> None:
        with self._lock:
            self.phase_caps[phase] = max(0, int(cap))

    def acquire(self, host: str, phase: str, n: int = 1) -> None:
        with self._lock:
            if self.elapsed() >= self.deadline_seconds:
                self.refused[phase] += n
                raise BudgetExhausted("time budget exhausted")
            if self.requests + n > self.usable_requests:
                self.refused[phase] += n
                raise BudgetExhausted("request budget exhausted")
            cap = self.phase_caps.get(phase)
            if cap is not None and self.per_phase[phase] + n > cap:
                self.refused[phase] += n
                raise BudgetExhausted(f"phase budget exhausted: {phase}")
            self.requests += n
            self.per_host[host] += n
            self.per_phase[phase] += n

    def phase_remaining(self, phase: str) -> int:
        with self._lock:
            cap = self.phase_caps.get(phase)
            global_left = self.usable_requests - self.requests
            if cap is None:
                return global_left
            return max(0, min(global_left, cap - self.per_phase[phase]))

    def report(self) -> dict:
        with self._lock:
            return {
                "requests": self.requests,
                "max_requests": self.max_requests,
                "elapsed_seconds": round(self.elapsed(), 1),
                "max_seconds": self.max_seconds,
                "third_party_cost_usd": round(self.cost_usd, 4),
                "max_cost_usd": self.max_cost_usd,
                "requests_by_host": dict(self.per_host.most_common()),
                "requests_by_phase": dict(self.per_phase),
                "phase_caps": dict(self.phase_caps),
                "refused_by_budget": dict(self.refused),
            }
