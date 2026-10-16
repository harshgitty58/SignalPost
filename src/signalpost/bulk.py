"""Large-batch mode: Brreg nightly bulk files (one request each) instead of one request per company.

* roles:     /roller/totalbestand  (gzipped JSON array, same object shape as /enheter/{org}/roller)
* sub-units: /underenheter/lastned/csv (gzipped CSV, filtered on overordnetEnhet)
Both are streamed; only rows for the batch are kept. Results are wrapped as Snapshots so the normal
claim builders (roles_claims / subunit_claims) are reused unchanged.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import re
import tempfile
from typing import Any

import httpx

from .budget import Budget
from .http import USER_AGENT, Snapshot, utc_now
from .registry import ROLES_URL, SUBUNITS_URL, _unflatten

ROLES_BULK = "https://data.brreg.no/enhetsregisteret/api/roller/totalbestand"
SUBUNITS_BULK = "https://data.brreg.no/enhetsregisteret/api/underenheter/lastned/csv"
OBJ_START = re.compile(r'\{\s*"_links"\s*:\s*\{\s*"self"\s*:\s*\{\s*"href"\s*:\s*"https://data\.brreg\.no/enhetsregisteret/api/enheter/(\d{9})/roller"')


def _download(url: str, budget: Budget, phase: str, accept: str, attempts: int = 3) -> str:
    """Download fully to a temp file first (fast reader => server does not drop the connection), then parse."""
    fd, path = tempfile.mkstemp(suffix=".gz", prefix="signalpost-bulk-")
    os.close(fd)
    last: Exception | None = None
    for _ in range(attempts):
        budget.acquire("data.brreg.no", phase)
        try:
            with httpx.stream("GET", url, headers={"User-Agent": USER_AGENT, "Accept": accept},
                              timeout=httpx.Timeout(120.0, connect=15.0), follow_redirects=True) as response:
                response.raise_for_status()
                with open(path, "wb") as handle:
                    for chunk in response.iter_raw(1 << 20):
                        handle.write(chunk)
            return path
        except (httpx.HTTPError, OSError) as exc:
            last = exc
    raise RuntimeError(f"bulk download failed: {last}")


def _text(url: str, budget: Budget, phase: str, accept: str) -> io.TextIOWrapper:
    path = _download(url, budget, phase, accept)
    return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8-sig", newline="")


def _snap(url: str, obj: Any) -> Snapshot:
    body = json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return Snapshot(url, url, 200, utc_now(), body=body, content_type="application/json", sha256=hashlib.sha256(body).hexdigest())


def bulk_roles(orgs: set[str], budget: Budget) -> dict[str, Snapshot]:
    found: dict[str, Snapshot] = {}
    text = _text(ROLES_BULK, budget, "roles", "application/json")
    buf = ""
    while True:
        chunk = text.read(1 << 22)
        buf += chunk
        starts = [(m.start(), m.group(1)) for m in OBJ_START.finditer(buf)]
        # every object except the last one in the buffer is complete
        complete = starts if not chunk else starts[:-1]
        for i, (pos, org) in enumerate(complete):
            if org in orgs:
                end = starts[i + 1][0] if i + 1 < len(starts) else len(buf)
                piece = buf[pos:end].rstrip().rstrip("]").rstrip().rstrip(",")
                try:
                    found[org] = _snap(ROLES_URL.format(org=org), json.loads(piece))
                except json.JSONDecodeError:
                    pass
        if not chunk:
            break
        buf = buf[starts[-1][0]:] if starts else buf[-2000:]
        if len(found) == len(orgs):
            break
    return found


def bulk_subunits(orgs: set[str], budget: Budget) -> dict[str, Snapshot]:
    units: dict[str, list[dict[str, Any]]] = {}
    for row in csv.DictReader(_text(SUBUNITS_BULK, budget, "locations", "application/vnd.brreg.enhetsregisteret.underenhet.v2+gzip;charset=UTF-8")):
        parent = row.get("overordnetEnhet")
        if parent in orgs:
            units.setdefault(parent, []).append(_unflatten(row))
    return {org: _snap(SUBUNITS_URL.format(org=org), {"_embedded": {"underenheter": rows}}) for org, rows in units.items()}
