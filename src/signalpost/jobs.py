"""Active job postings from NAV's public vacancy feed (pam-stilling-feed, free public API).

The feed is read once per run (shared across the whole batch). Feed entries only carry the employer's
display name, so names only generate *candidates*; a posting is published only after the full ad's
`employer.orgnr` equals the company's organisation number or one of its registered sub-units.
Only ACTIVE ads are published (NAV terms: inactive ads must not be shown); contact persons are never stored.
"""
from __future__ import annotations

import os
import re
import threading
import unicodedata
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from typing import Any

from .budget import BudgetExhausted
from .http import Fetcher, Snapshot
from .model import Claim, Evidence, ProfileBuilder

BASE = "https://pam-stilling-feed.nav.no"
TOKEN_URL = BASE + "/api/publicToken"
LEGAL = {"as", "asa", "ans", "da", "sa", "ba", "nuf", "enk", "iks", "kf", "stiftelsen", "avd", "avdeling"}


def norm_name(name: str | None) -> str:
    text = (name or "").casefold().translate(str.maketrans({"ø": "o", "å": "a", "æ": "ae"}))
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    tokens = [t for t in re.findall(r"[a-z0-9]+", text) if t not in LEGAL]
    return " ".join(tokens)


class JobFeed:
    """Background reader of the last `days` of feed pages; exposes latest status per ad."""

    def __init__(self, fetcher: Fetcher, *, days: int = 35, max_pages: int = 120):
        self.fetcher = fetcher
        self.days = days
        self.max_pages = max_pages
        self.ads: dict[str, dict[str, Any]] = {}
        self.pages = 0
        self.error: str | None = None
        self.token: str | None = os.environ.get("NAV_FEED_TOKEN") or None
        self.done = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name="nav-feed", daemon=True)
        self.thread.start()

    def wait(self, timeout: float) -> bool:
        return self.done.wait(timeout)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def _run(self) -> None:
        try:
            if not self.token:
                snap = self.fetcher.get(TOKEN_URL, phase="jobs", api=True)
                if not snap.ok:
                    self.error = f"token HTTP {snap.status}"
                    return
                lines = [line.strip() for line in snap.text().splitlines() if line.strip()]
                self.token = lines[-1] if lines else None
            since = format_datetime(datetime.now(timezone.utc) - timedelta(days=self.days), usegmt=True)
            snap = self.fetcher.get_json(BASE + "/api/v1/feed", phase="jobs", headers={**self._headers(), "If-Modified-Since": since}, retries=1, timeout=60)
            while snap.ok and self.pages < self.max_pages:
                self.pages += 1
                body = snap.json()
                items = body.get("items") or []
                for item in items:
                    entry = item.get("_feed_entry") or {}
                    uid = entry.get("uuid") or item.get("id")
                    if uid:
                        self.ads[uid] = {
                            "uuid": uid, "status": entry.get("status"), "title": entry.get("title") or item.get("title"),
                            "business_name": entry.get("businessName"), "municipal": entry.get("municipal"),
                            "modified": entry.get("sistEndret") or item.get("date_modified"), "url": BASE + (item.get("url") or ""),
                        }
                nxt = body.get("next_url")
                if not nxt or not items:
                    break
                snap = self.fetcher.get_json(BASE + nxt, phase="jobs", headers=self._headers(), retries=1, timeout=60)
            if not snap.ok and not self.ads:
                self.error = f"feed HTTP {snap.status} {snap.error or ''}"
        except BudgetExhausted:
            self.error = "budget"
        except Exception as exc:  # never let the feed thread crash the run
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            self.done.set()

    def candidates(self, names: list[str]) -> list[dict[str, Any]]:
        keys = {norm_name(n) for n in names if norm_name(n)}
        if not keys:
            return []
        out = []
        for ad in self.ads.values():
            if ad.get("status") != "ACTIVE":
                continue
            bn = norm_name(ad.get("business_name"))
            if not bn:
                continue
            if bn in keys:
                out.append((0, ad))
            elif any(len(k) >= 5 and bn.startswith(k + " ") for k in keys):
                out.append((1, ad))  # e.g. "xxl sport villmark avd bergen" — still verified by orgnr
        out.sort(key=lambda x: x[1].get("modified") or "", reverse=True)  # newest first…
        out.sort(key=lambda x: x[0])  # …exact name matches before prefix matches (stable sort)
        out = [ad for _, ad in out]
        return out


def job_claims(pb: ProfileBuilder, feed: JobFeed, names: list[str], valid_orgs: set[str], *, max_verify: int = 6) -> None:
    if not feed.done.is_set():
        pb.set_state("jobs", "failed", "job feed not ready before deadline", BASE)
        return
    if feed.error and not feed.ads:
        pb.set_state("jobs", "blocked" if "403" in feed.error or "401" in feed.error else "failed", f"NAV feed unavailable: {feed.error}", BASE)
        return
    cands = feed.candidates(names)
    if not cands:
        pb.set_state("jobs", "not_available", f"no active NAV postings for this employer in the last {feed.days} days", BASE + "/api/v1/feed")
        return
    verified = 0
    rejected = 0
    for ad in cands[:max_verify]:
        try:
            snap: Snapshot = feed.fetcher.get_json(ad["url"], phase="jobs_verify", headers=feed._headers(), retries=1)
        except BudgetExhausted:
            break
        if not snap.ok:
            continue
        body = snap.json()
        content = body.get("ad_content") or {}
        employer = content.get("employer") or {}
        orgnr = str(employer.get("orgnr") or "")
        if body.get("status") != "ACTIVE" or orgnr not in valid_orgs:
            rejected += 1
            pb.candidates.append({"family": "jobs", "candidate": ad.get("title"), "employer_orgnr": orgnr or None,
                                  "decision": "rejected", "reason": "employer orgnr does not match company or its sub-units" if orgnr not in valid_orgs else "ad not active"})
            continue
        locs = content.get("workLocations") or []
        place = ", ".join(sorted({(l.get("city") or l.get("municipal") or "").title() for l in locs if (l.get("city") or l.get("municipal"))}))
        value = {
            "title": content.get("title") or ad.get("title"),
            "employer": employer.get("name"),
            "location": place or None,
            "published": str(content.get("published") or "")[:10] or None,
            "expires": str(content.get("expires") or "")[:10] or None,
            "url": content.get("link") or f"https://arbeidsplassen.nav.no/stillinger/stilling/{ad['uuid']}",
            "positions": content.get("positioncount"),
            "extent": content.get("extent"),
        }
        value = {k: v for k, v in value.items() if v not in (None, "")}
        reason = "employer.orgnr equals company organisation number" if orgnr == pb.org else f"employer.orgnr {orgnr} is a registered sub-unit of this company"
        ev = pb.add_evidence(Evidence(snap.url, "public_api", snap.retrieved_at, snap.sha256,
                                      f'"employer": {{"name": "{employer.get("name")}", "orgnr": "{orgnr}"}}, "title": "{value.get("title")}", "status": "ACTIVE"',
                                      "nav_pam_stilling_feed:ad_content.employer.orgnr", "NAV arbeidsplassen API terms", identity_reason=reason,
                                      reporting_period={"from": value.get("published", ""), "to": value.get("expires", "")}))
        pb.add(Claim("jobs", "job_posting", value, [ev], label="Active job posting", key=f"job:{ad['uuid']}", effective_date=value.get("published")))
        verified += 1
    if verified:
        extra = max(0, len(cands) - max_verify)
        pb.set_state("jobs", "available", f"{verified} verified active postings" + (f" (+{extra} more unverified candidates not published)" if extra else ""), BASE)
    elif rejected:
        pb.set_state("jobs", "ambiguous", "name-matched postings belong to a different organisation number", BASE)
    else:
        pb.set_state("jobs", "failed", "could not verify candidate postings", BASE)
