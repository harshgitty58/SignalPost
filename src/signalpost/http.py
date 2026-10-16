"""Budgeted, polite HTTP client.

* every request (robots.txt and each redirect hop included) is charged to the Budget;
* outbound URL policy: http/https only, no credentials in URLs, no private/loopback/link-local
  targets (checked on every hop), bounded redirects, bounded body size;
* robots.txt is honoured for company websites (registry/API hosts are documented open APIs);
* per-host concurrency limits keep us polite and inside rate limits.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import threading
import time
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from .budget import Budget, BudgetExhausted

USER_AGENT = "SignalpostAgent/1.0 (+https://github.com/; company-research bot; respects robots.txt)"
MAX_BODY_BYTES = 3_000_000
MAX_REDIRECTS = 5


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class Snapshot:
    url: str
    final_url: str
    status: int
    retrieved_at: str
    body: bytes = b""
    content_type: str = ""
    sha256: str = ""
    elapsed_ms: int = 0
    error: str | None = None
    redirects: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300 and self.error is None

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))

    def text(self) -> str:
        charset = "utf-8"
        if "charset=" in self.content_type:
            charset = self.content_type.split("charset=")[-1].split(";")[0].strip() or "utf-8"
        try:
            return self.body.decode(charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")


class UrlPolicyError(Exception):
    pass


_dns_cache: dict[str, bool] = {}
_dns_lock = threading.Lock()


def host_is_public(host: str) -> bool:
    with _dns_lock:
        if host in _dns_cache:
            return _dns_cache[host]
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        ok = bool(infos) and all(ipaddress.ip_address(info[4][0].split("%")[0]).is_global for info in infos)
    except (socket.gaierror, UnicodeError, ValueError, OSError):
        ok = False
    with _dns_lock:
        _dns_cache[host] = ok
    return ok


def check_url(url: str) -> urllib.parse.SplitResult:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        raise UrlPolicyError(f"scheme not allowed: {parts.scheme}")
    if parts.username or parts.password:
        raise UrlPolicyError("credentials in URL not allowed")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host or "." not in host:
        raise UrlPolicyError("host not allowed")
    try:
        ipaddress.ip_address(host)
        raise UrlPolicyError("raw IP hosts not allowed")
    except ValueError:
        pass
    if parts.port not in (None, 80, 443):
        raise UrlPolicyError("non-standard port not allowed")
    if not host_is_public(host):
        raise UrlPolicyError("host does not resolve to a public address")
    return parts


class Fetcher:
    def __init__(self, budget: Budget, *, api_concurrency: int = 6, web_concurrency: int = 2):
        self.budget = budget
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en;q=0.6"},
            follow_redirects=False,
            timeout=httpx.Timeout(20.0, connect=8.0),
            limits=httpx.Limits(max_connections=64, max_keepalive_connections=32),
            verify=True,
        )
        self.api_concurrency = api_concurrency
        self.web_concurrency = web_concurrency
        self._host_sems: dict[str, threading.Semaphore] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._robots_locks: dict[str, threading.Lock] = {}
        self._lock = threading.Lock()
        self._min_interval: dict[str, float] = {}
        self._last_start: dict[str, float] = {}
        self.local = threading.local()  # per-thread request counter (per-company operations)

    def take_count(self) -> int:
        n = getattr(self.local, "count", 0)
        self.local.count = 0
        return n

    def close(self) -> None:
        self.client.close()

    def set_min_interval(self, host: str, seconds: float) -> None:
        self._min_interval[host] = seconds

    def _sem(self, host: str, api: bool) -> threading.Semaphore:
        with self._lock:
            if host not in self._host_sems:
                self._host_sems[host] = threading.Semaphore(self.api_concurrency if api else self.web_concurrency)
            return self._host_sems[host]

    def _pace(self, host: str) -> None:
        interval = self._min_interval.get(host)
        if not interval:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._last_start.get(host, 0.0) + interval - now
            self._last_start[host] = max(now, self._last_start.get(host, 0.0) + interval)
        if wait > 0:
            time.sleep(wait)

    # ------------------------------------------------------------------ robots
    def allowed_by_robots(self, url: str, phase: str) -> bool:
        parts = urllib.parse.urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        with self._lock:
            lock = self._robots_locks.setdefault(origin, threading.Lock())
        with lock:
            if origin not in self._robots:
                parser: urllib.robotparser.RobotFileParser | None = urllib.robotparser.RobotFileParser()
                snap = self._get(origin + "/robots.txt", phase=phase, api=False, max_bytes=300_000, timeout=8.0)
                if snap.status in (401, 403):
                    parser.disallow_all = True  # type: ignore[union-attr]
                elif snap.ok:
                    parser.parse(snap.text().splitlines())  # type: ignore[union-attr]
                else:
                    parser = None  # missing robots.txt => allowed
                self._robots[origin] = parser
            parser = self._robots[origin]
        if parser is None:
            return True
        return parser.can_fetch(USER_AGENT, url) and parser.can_fetch("*", url)

    # ------------------------------------------------------------------ fetch
    def get(self, url: str, *, phase: str, api: bool = False, headers: dict[str, str] | None = None,
            max_bytes: int = MAX_BODY_BYTES, timeout: float = 20.0, respect_robots: bool | None = None) -> Snapshot:
        if respect_robots is None:
            respect_robots = not api
        if respect_robots:
            try:
                check_url(url)
            except UrlPolicyError as exc:
                return Snapshot(url, url, 0, utc_now(), error=f"url_policy: {exc}")
            if not self.allowed_by_robots(url, phase):
                return Snapshot(url, url, 0, utc_now(), error="blocked_robots")
        return self._get(url, phase=phase, api=api, headers=headers, max_bytes=max_bytes, timeout=timeout)

    def _get(self, url: str, *, phase: str, api: bool, headers: dict[str, str] | None = None,
             max_bytes: int = MAX_BODY_BYTES, timeout: float = 20.0) -> Snapshot:
        current = url
        redirects: list[str] = []
        started = time.monotonic()
        for _hop in range(MAX_REDIRECTS + 1):
            try:
                parts = check_url(current) if not api else urllib.parse.urlsplit(current)
            except UrlPolicyError as exc:
                return Snapshot(url, current, 0, utc_now(), error=f"url_policy: {exc}", redirects=redirects)
            host = (parts.hostname or "").lower()
            self.budget.acquire(host, phase)  # may raise BudgetExhausted
            self.local.count = getattr(self.local, "count", 0) + 1
            sem = self._sem(host, api)
            with sem:
                self._pace(host)
                try:
                    with self.client.stream("GET", current, headers=headers or {}, timeout=timeout) as response:
                        if response.is_redirect and "location" in response.headers:
                            nxt = urllib.parse.urljoin(current, response.headers["location"])
                            redirects.append(nxt)
                            current = nxt
                            continue
                        chunks: list[bytes] = []
                        size = 0
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > max_bytes:
                                break
                            chunks.append(chunk)
                        body = b"".join(chunks)
                        return Snapshot(
                            url=url,
                            final_url=str(response.url),
                            status=response.status_code,
                            retrieved_at=utc_now(),
                            body=body,
                            content_type=response.headers.get("content-type", ""),
                            sha256=hashlib.sha256(body).hexdigest(),
                            elapsed_ms=int((time.monotonic() - started) * 1000),
                            redirects=redirects,
                            headers={k.lower(): v for k, v in response.headers.items() if k.lower() in {"etag", "last-modified", "date"}},
                        )
                except BudgetExhausted:
                    raise
                except (httpx.HTTPError, OSError, ValueError) as exc:
                    return Snapshot(url, current, 0, utc_now(), error=f"{type(exc).__name__}", redirects=redirects,
                                    elapsed_ms=int((time.monotonic() - started) * 1000))
        return Snapshot(url, current, 0, utc_now(), error="too_many_redirects", redirects=redirects)

    def get_json(self, url: str, *, phase: str, headers: dict[str, str] | None = None, retries: int = 1,
                 timeout: float = 30.0) -> Snapshot:
        hdrs = {"Accept": "application/json"}
        hdrs.update(headers or {})
        snap = self.get(url, phase=phase, api=True, headers=hdrs, timeout=timeout)
        attempt = 0
        while attempt < retries and (snap.status == 0 or snap.status == 429 or snap.status >= 500):
            attempt += 1
            time.sleep(1.0 * attempt)
            snap = self.get(url, phase=phase, api=True, headers=hdrs, timeout=timeout)
        return snap
