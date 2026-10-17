"""Refresh: compare this run's profile with the previous one and emit typed, evidenced changes.

* Claims are matched on (family, key) — a stable identity of the fact, independent of value.
* Same snapshot => same claim IDs => zero changes (idempotent; tested).
* A family that could not be read this run (failed/blocked/budget) is `not_compared`: prior values are
  carried forward with `stale_since`, never reported as removed.
* Prior evidence is preserved: carried-forward claims keep their original evidence records.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CHANGE_TYPES = {
    ("leadership", "added"): "new_role", ("leadership", "removed"): "ended_role", ("leadership", "changed"): "changed_role",
    ("locations", "added"): "new_location", ("locations", "removed"): "closed_location", ("locations", "changed"): "changed_location",
    ("jobs", "added"): "new_job", ("jobs", "removed"): "closed_job", ("jobs", "changed"): "changed_job",
    ("financials", "added"): "new_filing", ("financials", "changed"): "restated_value", ("financials", "removed"): "removed_filing_value",
    ("activity", "added"): "new_activity", ("activity", "removed"): "aged_out_activity",
    ("website", "added"): "new_website", ("website", "removed"): "website_removed", ("website", "changed"): "website_change",
    ("status", "added"): "status_change", ("status", "changed"): "status_change", ("status", "removed"): "status_change",
    ("description", "changed"): "changed_description", ("description", "added"): "new_description",
    ("social_profiles", "added"): "new_profile", ("social_profiles", "removed"): "removed_profile", ("social_profiles", "changed"): "changed_profile",
}
UNREADABLE = {"failed", "blocked"}
FIELD_TYPES = {"business_address": "address_change", "postal_address": "address_change", "legal_name": "name_change",
               "employees": "employee_count_change", "share_capital": "capital_change", "legal_form": "legal_form_change",
               "industry_code": "industry_change", "official_website": "website_change", "ceo": "ceo_change"}
MINOR = {"employee_count_change", "aged_out_activity", "changed_location"}


def load_previous(path: str | Path | None) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    p = Path(path)
    if p.is_dir():
        p = next((p / n for n in ("envelopes.jsonl", "profiles.jsonl") if (p / n).exists()), p / "envelopes.jsonl")
    if not p.exists():
        return {}
    out = {}
    import gzip
    opener = gzip.open if p.suffix == ".gz" else open
    with opener(p, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                out[row["organisation_number"]] = row
    return out


def _index(envelope: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(c["family"], c.get("key") or c["field"]): c for c in envelope.get("claims", []) if c.get("availability", "available") == "available"}


def diff(previous: dict[str, Any] | None, current: dict[str, Any], *, detected_at: str) -> tuple[list[dict], dict[str, Any]]:
    """Return (changes, refresh_meta) and mutate `current` to carry forward unreadable families."""
    if not previous:
        for claim in current.get("claims", []):
            claim["first_seen"] = detected_at
        return [], {"mode": "baseline", "previous_run_id": None, "compared_families": [], "not_compared": []}
    prev_claims = _index(previous)
    cur_claims = _index(current)
    prev_evidence = {e["id"]: e for e in previous.get("evidence", [])}
    states = current.get("availability", {})
    prev_started = previous.get("run", {}).get("started_at") or previous.get("run", {}).get("completed_at")
    for key, claim in cur_claims.items():
        old = prev_claims.get(key)
        claim["first_seen"] = (old.get("first_seen") or prev_started) if old else detected_at
    changes: list[dict] = []
    not_compared: list[str] = []
    compared: list[str] = []
    families = sorted({f for f, _ in prev_claims} | {f for f, _ in cur_claims})
    for family in families:
        state = (states.get(family) or {}).get("state")
        if state in UNREADABLE or ((states.get(family) or {}).get("reason", "").startswith("request budget")):
            not_compared.append(family)
            # carry forward last supported values with their original evidence
            for (fam, key), claim in prev_claims.items():
                if fam == family and (fam, key) not in cur_claims:
                    carried = dict(claim)
                    carried["stale_since"] = claim.get("stale_since") or previous.get("run", {}).get("completed_at")
                    carried["availability"] = "available"
                    current["claims"].append(carried)
                    for eid in claim.get("evidence_ids", []):
                        if eid in prev_evidence and all(e["id"] != eid for e in current["evidence"]):
                            current["evidence"].append(prev_evidence[eid])
            continue
        compared.append(family)
        keys = {k for f, k in prev_claims if f == family} | {k for f, k in cur_claims if f == family}
        for key in sorted(keys):
            old = prev_claims.get((family, key))
            new = cur_claims.get((family, key))
            if old and new:
                if json.dumps(old.get("value"), sort_keys=True, ensure_ascii=False) == json.dumps(new.get("value"), sort_keys=True, ensure_ascii=False):
                    continue
                kind = "changed"
            elif new:
                kind = "added"
            else:
                kind = "removed"
            if family == "activity" and kind == "removed":
                continue  # activity items age out of the window; not a material change
            if family == "financials" and kind == "removed" and any(f == "financials" for f, _ in cur_claims):
                continue  # older filing years roll out of the API's 3-year window; not a material change
            ref = new or old
            changes.append({
                "id": f"chg-{ref['id']}-{kind}",
                "type": (ctype := FIELD_TYPES.get(ref["field"]) if kind == "changed" else None) or CHANGE_TYPES.get((family, kind), f"{kind}_value"),
                "material": (ctype or CHANGE_TYPES.get((family, kind), "")) not in MINOR,
                "family": family,
                "field": ref["field"],
                "key": key,
                "label": ref.get("label"),
                "previous": old.get("value") if old else None,
                "current": new.get("value") if new else None,
                "evidence_ids": (new or {}).get("evidence_ids") or [],
                "previous_evidence_ids": (old or {}).get("evidence_ids") or [],
                "detected_at": detected_at,
            })
    meta = {
        "mode": "refresh",
        "previous_run_id": previous.get("run", {}).get("run_id"),
        "previous_completed_at": previous.get("run", {}).get("completed_at"),
        "compared_families": compared,
        "not_compared": not_compared,
        "change_count": len(changes),
    }
    return changes, meta
