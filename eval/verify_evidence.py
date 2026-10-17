"""Re-fetch a random sample of evidence sources and check the claim span still appears (evidence validity).

    uv run python eval/verify_evidence.py out-dev/envelopes.jsonl --sample 50
Spans from JSON APIs are compared whitespace-insensitively; drift since the run (e.g. a changed CEO) is
reported as drift, not hidden.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from signalpost.budget import Budget  # noqa: E402
from signalpost.http import Fetcher  # noqa: E402


def compact(text: str) -> str:
    return re.sub(r"[\s\"'\\]+", "", text).casefold()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("envelopes")
    ap.add_argument("--sample", type=int, default=50)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    pool = []
    for line in open(args.envelopes, encoding="utf-8"):
        e = json.loads(line)
        ev = {x["id"]: x for x in e["evidence"]}
        for c in e["claims"]:
            if c.get("availability", "available") == "available" and c["evidence_ids"]:
                x = ev.get(c["evidence_ids"][0])
                if x and "replay.invalid" not in x["source_url"] and not x["source_url"].endswith(".csv"):
                    pool.append((e["organisation_number"], c, x))
    sample = random.Random(args.seed).sample(pool, min(args.sample, len(pool)))
    fetcher = Fetcher(Budget(max_requests=args.sample * 4 + 50))
    found = drift = errors = 0
    rows = []
    for org, claim, ev in sample:
        api = ev["source_class"] in ("official_registry", "public_api")
        snap = fetcher.get_json(ev["source_url"], phase="verify") if api else fetcher.get(ev["source_url"], phase="verify")
        if not snap.ok:
            errors += 1
            rows.append(("error", org, claim["field"], snap.status))
            continue
        body = compact(snap.text())
        span = ev["claim_span"]
        probe = [compact(p) for p in re.split(r"\s[—-]\s|: ", span) if len(compact(p)) >= 6][:3] or [compact(span)]
        value = claim["value"]
        core = value.get("year") or value.get("title") or value.get("name") if isinstance(value, dict) else value
        if claim["field"] == "registry_event":
            core = ev["claim_span"].split('"dato": "')[-1][:19]  # the event timestamp must exist at the source
        tokens = [compact(t) for t in re.findall(r"[\wæøåÆØÅ.-]{2,}", str(core))]
        ok = any(p in body for p in probe) or (bool(tokens) and all(t in body for t in tokens))
        found += ok
        drift += not ok
        if not ok:
            rows.append(("drift", org, claim["field"], span[:80]))
    n = len(sample)
    print(json.dumps({"sampled": n, "span_refound": found, "drift_or_changed": drift, "fetch_errors": errors,
                      "refound_rate": round(found / max(1, n - errors), 3)}, ensure_ascii=False))
    for row in rows[:20]:
        print("  ", row)
    fetcher.close()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    main()
