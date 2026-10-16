"""Build the static showcase site from a run's envelopes.

Output works from a plain folder (file://) or any static host:
  index.html            app shell + inline run report + compact company index
  data/<orgnr>.js       one profile per company, loaded on demand via <script> (no fetch/CORS needed)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..synthesis import latest_accounts

HERE = Path(__file__).parent


def _index_row(env: dict[str, Any]) -> dict[str, Any]:
    claims = [c for c in env.get("claims", []) if c.get("availability", "available") == "available"]
    first = lambda field: next((c["value"] for c in claims if c["field"] == field), None)  # noqa: E731
    latest = latest_accounts(claims)
    rev = latest.get("revenue")
    res = latest.get("net_result")
    acts = sorted((c.get("effective_date") or "" for c in claims if c["family"] == "activity"), reverse=True)
    industry = first("industry_code") or ""
    return {
        "o": env["organisation_number"],
        "n": env.get("name") or first("legal_name") or "(unknown)",
        "b": first("public_brand"),
        "f": (first("legal_form") or "").split("(")[-1].rstrip(")") if first("legal_form") else None,
        "m": first("municipality"),
        "i": industry,
        "e": first("employees"),
        "r": rev["value"] if rev else None,
        "ru": rev.get("unit") if rev else None,
        "ry": (rev or res or {}).get("period", {}).get("to", "")[:4] if (rev or res) else None,
        "nr": res["value"] if res else None,
        "w": first("official_website"),
        "j": sum(1 for c in claims if c["family"] == "jobs"),
        "l": sum(1 for c in claims if c["family"] == "locations"),
        "s": {k: v["state"] for k, v in env.get("availability", {}).items()},
        "c": len(env.get("changes", [])),
        "k": len(claims),
        "a": acts[0] if acts else None,
        "ch": [{"t": ch["type"], "l": ch.get("label"), "d": ch.get("detected_at"), "p": ch.get("previous"), "v": ch.get("current")} for ch in env.get("changes", [])[:6]],
    }


def build_site(envelopes_path: Path, report_path: Path | None, output: Path) -> None:
    output = Path(output)
    (output / "data").mkdir(parents=True, exist_ok=True)
    rows = []
    with Path(envelopes_path).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            env = json.loads(line)
            rows.append(_index_row(env))
            payload = json.dumps(env, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
            (output / "data" / f"{env['organisation_number']}.js").write_text(
                f"window.SP_LOAD({json.dumps(env['organisation_number'])},{payload});\n", encoding="utf-8")
    report = json.loads(Path(report_path).read_text(encoding="utf-8")) if report_path and Path(report_path).exists() else {}
    template = (HERE / "template.html").read_text(encoding="utf-8")
    boot = json.dumps({"index": rows, "report": report}, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = template.replace("/*__BOOT__*/null", boot)
    (output / "index.html").write_text(html, encoding="utf-8")
