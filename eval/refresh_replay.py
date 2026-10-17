"""Refresh replay: prove typed change detection, idempotency and carry-forward on real envelopes.

    uv run python eval/refresh_replay.py out-100-v2/envelopes.jsonl reports/refresh-replay.json

Takes a real profile as the "previous" run, applies controlled source mutations (new filing year, CEO change,
new job, closed workplace, address change), runs the same diff the agent uses, and checks:
  1. identical snapshot  -> 0 changes (idempotent)
  2. mutated snapshot    -> exactly the expected typed changes, each with evidence ids
  3. unreadable source   -> family not compared, prior values carried forward with original evidence
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from signalpost.model import Claim, Evidence, ProfileBuilder  # noqa: E402
from signalpost.refresh import diff  # noqa: E402


def published(env):
    return [c for c in env["claims"] if c.get("availability", "available") == "available"]


def add(env, family, field, key, value, **kw):
    pb = ProfileBuilder(env["organisation_number"])
    ev = Evidence("https://replay.invalid/" + key, "official_registry", "2026-10-17T06:00:00Z", "0" * 64, json.dumps(value, ensure_ascii=False), "replay_mutation")
    pb.add_evidence(ev)
    c = pb.add(Claim(family, field, value, [ev.id], key=key, **kw)).to_dict()
    env["claims"].append(c)
    env["evidence"].append(ev.to_dict())


def main(src: str, out: str) -> None:
    envs = [json.loads(line) for line in open(src, encoding="utf-8") if line.strip()]
    base = next(e for e in envs if any(c["field"] == "ceo" for c in published(e)) and any(c["family"] == "locations" for c in published(e)))
    prev = copy.deepcopy(base)
    prev["claims"] = published(prev)
    results = {"organisation_number": base["organisation_number"], "name": base["name"], "checks": {}}

    same = copy.deepcopy(prev)
    ch, _ = diff(prev, same, detected_at="t1")
    results["checks"]["idempotent_rerun_zero_changes"] = {"passed": ch == [], "changes": len(ch)}

    cur = copy.deepcopy(prev)
    ceo = next(c for c in cur["claims"] if c["field"] == "ceo")
    cur["claims"].remove(ceo)
    add(cur, "leadership", "ceo", "role:DAGL:Kari Nordmann", "Kari Nordmann", label="Daglig leder")
    loc = next(c for c in cur["claims"] if c["family"] == "locations")
    cur["claims"].remove(loc)
    add(cur, "financials", "revenue", "revenue:SELSKAP:2026-12-31", 12345000, unit="NOK", period={"from": "2026-01-01", "to": "2026-12-31"}, note="account_type=SELSKAP")
    add(cur, "jobs", "job_posting", "job:replay-1", {"title": "Prosjektleder", "published": "2026-10-17"})
    addr = next((c for c in cur["claims"] if c["field"] == "business_address"), None)
    if addr:
        addr["value"] = "Testveien 1, 0150 OSLO"
    expected = {"new_role", "ended_role", "closed_location", "new_filing", "new_job"} | ({"address_change"} if addr else set())
    ch, meta = diff(prev, cur, detected_at="t2")
    got = {c["type"] for c in ch}
    results["checks"]["typed_changes_detected"] = {"passed": got == expected and all(c["evidence_ids"] or c["previous_evidence_ids"] for c in ch),
                                                   "expected": sorted(expected), "got": sorted(got), "changes": ch}

    unreadable = copy.deepcopy(prev)
    unreadable["claims"] = [c for c in unreadable["claims"] if c["family"] != "leadership"]
    unreadable["availability"]["leadership"] = {"state": "failed", "reason": "source error (simulated)"}
    ch, meta = diff(prev, unreadable, detected_at="t3")
    carried = [c for c in unreadable["claims"] if c["family"] == "leadership"]
    results["checks"]["unreadable_source_carried_forward"] = {
        "passed": not any(c["family"] == "leadership" for c in ch) and bool(carried) and all(c.get("stale_since") for c in carried)
        and "leadership" in meta["not_compared"], "carried_claims": len(carried), "not_compared": meta["not_compared"]}
    results["passed"] = all(v["passed"] for v in results["checks"].values())
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v["passed"] for k, v in results["checks"].items()}), "->", "PASS" if results["passed"] else "FAIL")
    raise SystemExit(0 if results["passed"] else 1)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    main(sys.argv[1], sys.argv[2])
