"""Build the static showcase site from a run's envelopes.

Output works from a plain folder (file://) or any static host:
  index.html            app shell + inline run report + compact company index + trust summary
  data/<orgnr>.js       one profile per company, loaded on demand via <script> (no fetch/CORS needed)

The site only re-presents what the envelopes say. Everything in the index and the trust summary is
counted from the envelopes (or copied from the run report); nothing is estimated.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from ..synthesis import latest_accounts

HERE = Path(__file__).parent
# Fylke (county) by the first two digits of the registry's kommunenummer (2024 county structure).
COUNTIES = {"03": "Oslo", "11": "Rogaland", "15": "Møre og Romsdal", "18": "Nordland", "31": "Østfold", "32": "Akershus",
            "33": "Buskerud", "34": "Innlandet", "39": "Vestfold", "40": "Telemark", "42": "Agder", "46": "Vestland",
            "50": "Trøndelag", "55": "Troms", "56": "Finnmark", "21": "Svalbard"}
KOMMUNENUMMER = re.compile(r'"kommunenummer":\s*"(\d{4})"')


def _published(env: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in env.get("claims", []) if c.get("availability", "available") == "available"]


def _county(env: dict[str, Any], claims: list[dict[str, Any]]) -> str | None:
    """County derived from the municipality number inside the business-address evidence span (as sourced)."""
    addr = next((c for c in claims if c["field"] == "business_address"), None)
    if not addr:
        return None
    evs = {e["id"]: e for e in env.get("evidence", [])}
    for eid in addr.get("evidence_ids", []):
        m = KOMMUNENUMMER.search((evs.get(eid) or {}).get("claim_span") or "")
        if m:
            return COUNTIES.get(m.group(1)[:2])
    return None


def _index_row(env: dict[str, Any]) -> dict[str, Any]:
    claims = _published(env)
    first = lambda field: next((c["value"] for c in claims if c["field"] == field), None)  # noqa: E731
    latest = latest_accounts(claims)
    rev = latest.get("revenue")
    res = latest.get("net_result")
    acts = sorted((c.get("effective_date") or "" for c in claims if c["family"] == "activity"), reverse=True)
    industry = first("industry_code") or ""
    legal_form = first("legal_form")
    return {
        "o": env["organisation_number"],
        "n": env.get("name") or first("legal_name") or "(unknown)",
        "b": first("public_brand"),
        "f": legal_form.split("(")[-1].rstrip(")") if legal_form else None,
        "m": first("municipality"),
        "co": _county(env, claims),
        "i": industry,
        "e": first("employees"),
        "r": rev["value"] if rev else None,
        "ru": rev.get("unit") if rev else None,
        "ry": (rev or res or {}).get("period", {}).get("to", "")[:4] if (rev or res) else None,
        "nr": res["value"] if res else None,
        "nu": res.get("unit") if res else None,
        "w": first("official_website"),
        "j": sum(1 for c in claims if c["family"] == "jobs"),
        "l": sum(1 for c in claims if c["family"] == "locations"),
        "s": {k: v["state"] for k, v in env.get("availability", {}).items()},
        "c": len(env.get("changes", [])),
        "k": len(claims),
        "a": acts[0] if acts else None,
        "ch": [{"t": ch["type"], "m": ch.get("material", True), "f": ch.get("family"), "l": ch.get("label"), "d": ch.get("detected_at"),
                "p": ch.get("previous"), "v": ch.get("current")} for ch in env.get("changes", [])[:50]],
    }


def _trust(envs: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts behind the overview's trust panel. All derived from the envelopes themselves."""
    n = len(envs)
    total = complete = stale = 0
    proofs: Counter[str] = Counter()
    decisions: Counter[str] = Counter()
    rejections = []
    abstained_companies = 0
    family_pairs = Counter()
    for env in envs:
        evs = {e["id"]: e for e in env.get("evidence", []) + env.get("prior_evidence", [])}
        for c in _published(env):
            total += 1
            stale += bool(c.get("stale_since"))
            items = [evs.get(i) for i in c.get("evidence_ids", [])]
            if items and all(e and e.get("source_url") and e.get("retrieved_at") and e.get("content_sha256") and e.get("claim_span") for e in items):
                complete += 1
            if c["field"] == "official_website":
                for e in items:
                    if e and e.get("identity_reason"):
                        proofs[e["identity_reason"].split(" — ")[0]] += 1
        states = [v.get("state") for v in env.get("availability", {}).values()]
        family_pairs.update(states)
        abstained_companies += "ambiguous" in states
        for cand in env.get("unpublished_candidates", []):
            decisions[cand.get("decision") or "unknown"] += 1
            if cand.get("decision") == "rejected":
                rejections.append({"o": env["organisation_number"], "n": env.get("name"), "f": cand.get("family"), "c": cand.get("candidate"), "r": cand.get("reason")})
    rejections.sort(key=lambda r: (r["f"] != "website", "different organisation number" not in (r["r"] or "")))
    return {"companies": n, "claims": total, "evidence_complete": complete, "carried_forward": stale,
            "website_proofs": dict(proofs.most_common()), "candidate_decisions": dict(decisions),
            "rejection_examples": rejections[:6], "abstained_companies": abstained_companies, "family_states": dict(family_pairs)}


def build_site(envelopes_path: Path, report_path: Path | None, output: Path) -> None:
    output = Path(output)
    (output / "data").mkdir(parents=True, exist_ok=True)
    rows, envs = [], []
    with Path(envelopes_path).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            env = json.loads(line)
            envs.append(env)
            rows.append(_index_row(env))
            payload = json.dumps(env, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
            (output / "data" / f"{env['organisation_number']}.js").write_text(
                f"window.SP_LOAD({json.dumps(env['organisation_number'])},{payload});\n", encoding="utf-8")
    report = json.loads(Path(report_path).read_text(encoding="utf-8")) if report_path and Path(report_path).exists() else {}
    trust = _trust(envs)
    # optional: result of eval/verify_evidence.py saved next to the envelopes (the live console writes it)
    verification = Path(envelopes_path).parent / "evidence-verification.json"
    if verification.exists():
        try:
            trust["verification"] = json.loads(verification.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    template = (HERE / "template.html").read_text(encoding="utf-8")
    boot = json.dumps({"index": rows, "report": report, "trust": trust}, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = template.replace("/*__BOOT__*/null", boot)
    (output / "index.html").write_text(html, encoding="utf-8")
