"""Honest benchmark report for a run directory (coverage with 95% Wilson intervals, abstentions, cost).

    uv run python eval/benchmark.py out-dev [out-val ...] > reports/benchmark.md
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

FAMILIES = ["identity", "status", "industry", "financials", "leadership", "locations", "group", "website",
            "social_profiles", "contact", "description", "jobs", "activity"]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def report(run: Path) -> str:
    envs = [json.loads(line) for line in (run / "envelopes.jsonl").open(encoding="utf-8") if line.strip()]
    rep = json.loads((run / "run-report.json").read_text(encoding="utf-8"))
    n = len(envs)
    pub = lambda e: [c for c in e["claims"] if c.get("availability", "available") == "available"]  # noqa: E731
    lines = [f"### {run.name} — {rep.get('run_id')} @ {rep.get('agent_version')}", "",
             f"{n} companies · valid={rep['validation']['passed']} · requests={rep['operations']['requests']} · "
             f"time={rep['operations']['elapsed_seconds']}s · cost=${rep.get('third_party_cost_usd', 0)} · "
             f"p50/p95 per company={rep['operations'].get('p50_company_ms')}/{rep['operations'].get('p95_company_ms')} ms", "",
             "| Family | Available | 95% CI | Ambiguous (abstained) | Not available | Failed/blocked | Claims |", "|---|---|---|---|---|---|---|"]
    for fam in FAMILIES:
        states = [e["availability"].get(fam, {}).get("state", "failed") for e in envs]
        k = states.count("available")
        lo, hi = wilson(k, n)
        claims = sum(1 for e in envs for c in pub(e) if c["family"] == fam)
        lines.append(f"| {fam} | {k / n:.0%} | {lo:.0%}–{hi:.0%} | {states.count('ambiguous') / n:.0%} | {states.count('not_available') / n:.0%} | "
                     f"{(states.count('failed') + states.count('blocked')) / n:.0%} | {claims} |")
    extra = {
        "financial history (≥1 filed year)": sum(any(c["field"] == "filed_annual_accounts" for c in pub(e)) for e in envs),
        "material activity (excl. employee-count updates)": sum(any(c["family"] == "activity" and "employee count" not in str(c["value"]) for c in pub(e)) for e in envs),
        "real group relations (parent/subsidiary)": sum(any(c["field"] in ("parent_company", "subsidiary") for c in pub(e)) for e in envs),
        "company-owned news items": sum(any(c["field"] == "company_news" for c in pub(e)) for e in envs),
    }
    lines += ["", "| Derived coverage | Companies | 95% CI |", "|---|---|---|"]
    for label, k in extra.items():
        lo, hi = wilson(k, n)
        lines.append(f"| {label} | {k / n:.0%} | {lo:.0%}–{hi:.0%} |")
    incomplete = sum(1 for e in envs for c in pub(e) for i in c["evidence_ids"]
                     if not any(x["id"] == i and x.get("source_url") and x.get("retrieved_at") and x.get("content_sha256") and x.get("claim_span")
                                for x in e["evidence"] + e.get("prior_evidence", [])))
    total = sum(len(pub(e)) for e in envs)
    lines += ["", f"Published claims: {total} ({total / n:.1f}/company) · evidence-incomplete references: {incomplete} · "
              f"identity gate: {rep.get('identity_gate')}", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    print("# Benchmark report\n")
    for arg in sys.argv[1:]:
        print(report(Path(arg)))
