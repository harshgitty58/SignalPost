"""Deterministic, cited company brief.

Every sentence is built only from published claims and lists the claim IDs it rests on, so a reader can
verify each statement. Unknowns are stated explicitly with the reason. No numbers are invented: values
are formatted from the claims, and derived figures (e.g. margin, change %) are labelled as derived.
"""
from __future__ import annotations

from typing import Any

from .model import FAMILIES


def money(value: Any, unit: str | None) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    unit = unit or "NOK"
    a = abs(v)
    if a >= 1e9:
        s = f"{v / 1e9:.1f} bn"
    elif a >= 1e6:
        s = f"{v / 1e6:.1f} m"
    elif a >= 1e3:
        s = f"{v / 1e3:.0f} k"
    else:
        s = f"{v:.0f}"
    return f"{unit} {s}"


def money_no(value: Any, unit: str | None) -> str:
    """Norwegian formatting of the same value (decimal comma, mrd./mill.); the unit is kept as sourced."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    unit = unit or "NOK"
    a = abs(v)
    if a >= 1e9:
        s = f"{v / 1e9:.1f} mrd."
    elif a >= 1e6:
        s = f"{v / 1e6:.1f} mill."
    elif a >= 1e3:
        s = f"{v / 1e3:.0f} tusen"
    else:
        s = f"{v:.0f}"
    return f"{s.replace('.', ',', 1) if s[0].isdigit() or s[0] == '-' else s} {unit}"


CHANGE_NO = {"address_change": "adresseendring", "name_change": "navneendring", "employee_count_change": "endret antall ansatte",
             "capital_change": "kapitalendring", "legal_form_change": "endret organisasjonsform", "industry_change": "bransjeendring",
             "website_change": "endret nettsted", "ceo_change": "ny daglig leder", "new_role": "ny rolle", "ended_role": "avsluttet rolle",
             "changed_role": "endret rolle", "new_location": "nytt arbeidssted", "closed_location": "nedlagt arbeidssted",
             "changed_location": "endret arbeidssted", "new_job": "ny stillingsannonse", "closed_job": "avsluttet stillingsannonse",
             "changed_job": "endret stillingsannonse", "new_filing": "nytt regnskap", "restated_value": "korrigert verdi",
             "new_activity": "ny aktivitet", "new_website": "nytt nettsted", "website_removed": "nettsted fjernet", "status_change": "statusendring",
             "changed_description": "endret beskrivelse", "new_description": "ny beskrivelse", "new_profile": "ny profil",
             "removed_profile": "fjernet profil", "changed_profile": "endret profil"}


def _first(claims: list[dict], field: str) -> dict | None:
    return next((c for c in claims if c["field"] == field), None)


def latest_accounts(claims: list[dict]) -> dict[str, dict]:
    """Return {field: claim} for the latest company-level (SELSKAP) period, falling back to group."""
    fin = [c for c in claims if c["family"] == "financials" and c.get("period")]
    if not fin:
        return {}
    for account_type in ("SELSKAP", "KONSERN"):
        typed = [c for c in fin if f"account_type={account_type}" in (c.get("note") or "")]
        if typed:
            latest = max(c["period"].get("to") or "" for c in typed)
            return {c["field"]: c for c in typed if c["period"].get("to") == latest}
    return {}


def previous_accounts(claims: list[dict], latest_to: str, account_type: str) -> dict[str, dict]:
    fin = [c for c in claims if c["family"] == "financials" and c.get("period") and f"account_type={account_type}" in (c.get("note") or "")]
    older = sorted({c["period"].get("to") for c in fin if (c["period"].get("to") or "") < latest_to}, reverse=True)
    if not older:
        return {}
    return {c["field"]: c for c in fin if c["period"].get("to") == older[0]}


def build_brief(envelope: dict[str, Any]) -> dict[str, Any]:
    claims = envelope.get("claims", [])
    by = lambda fam: [c for c in claims if c["family"] == fam]  # noqa: E731
    sentences: list[dict[str, Any]] = []

    def say(text: str, *cs: dict | None, derived: bool = False, no: str | None = None) -> None:
        ids = [c["id"] for c in cs if c]
        if ids:
            sentences.append({"text": text, **({"text_no": no} if no else {}), "claim_ids": ids, **({"derived": True} if derived else {})})

    ident = by("identity")
    name = _first(ident, "legal_name")
    form = _first(ident, "legal_form")
    founded = _first(ident, "founded_date")
    muni = _first(ident, "municipality")
    brand = _first(ident, "public_brand")
    if name:
        kind = form["value"].split(" (")[0].lower() if form else "registered entity"
        parts = [f"{name['value']} is {'an' if kind[:1] in 'aeiouæøå' else 'a'} {kind}"]
        no = f"{name['value']} er registrert som {kind}" if form else f"{name['value']} er en registrert enhet"
        if muni:
            parts.append(f"based in {muni['value']}")
            no += f" i {muni['value']}"
        if founded:
            parts.append(f"founded {founded['value']}")
            no += f", stiftet {founded['value']}"
        say(", ".join(parts) + ".", name, form, muni, founded, no=no + ".")
    if brand:
        say(f"It presents itself publicly as “{brand['value']}”.", brand, no=f"Selskapet presenterer seg offentlig som «{brand['value']}».")

    industry = _first(by("industry"), "industry_code")
    desc = _first(by("description"), "self_description")
    if industry:
        activity, code = industry['value'].split(' ', 1)[-1].lower(), industry['value'].split(' ', 1)[0]
        say(f"Its registered primary activity is {activity} (NACE {code}).", industry, no=f"Registrert hovedaktivitet er {activity} (NACE {code}).")
    if desc:
        text = desc["value"]
        quote = f"{text[:220]}{'…' if len(text) > 220 else ''}"
        say(f"In its own words (company-owned copy): “{quote}”", desc, no=f"Med egne ord (selskapets egen tekst): «{quote}»")

    status = by("status")
    adverse = [c for c in status if c["field"] in ("konkurs", "underAvvikling", "underTvangsavviklingEllerTvangsopplosning", "deleted")]
    if adverse:
        flags = ", ".join(c["label"].lower() for c in adverse)
        say("Registry status flags: " + flags + ".", *adverse, no="Registeret har merknader: " + flags + ".")

    latest = latest_accounts(claims)
    if latest:
        rev, res, eq, assets = (latest.get(k) for k in ("revenue", "net_result", "equity", "total_assets"))
        anchor = rev or res or eq or assets
        period = anchor["period"]["to"][:4] if anchor else ""
        scope = "group" if "KONSERN" in (anchor.get("note") or "") else "company"
        bits, bits_no = [], []
        if rev:
            bits.append(f"operating revenue of {money(rev['value'], rev.get('unit'))}")
            bits_no.append(f"driftsinntekter på {money_no(rev['value'], rev.get('unit'))}")
        if res:
            bits.append(f"a net result of {money(res['value'], res.get('unit'))}")
            bits_no.append(f"et årsresultat på {money_no(res['value'], res.get('unit'))}")
        if eq:
            bits.append(f"equity of {money(eq['value'], eq.get('unit'))}")
            bits_no.append(f"egenkapital på {money_no(eq['value'], eq.get('unit'))}")
        if bits:
            say(f"For {period} ({scope} accounts) it reported " + ", ".join(bits) + ".", rev, res, eq,
                no=f"For {period} ({'konsernregnskap' if scope == 'group' else 'selskapsregnskap'}) rapporterte selskapet " + ", ".join(bits_no) + ".")
        if rev:
            prev = previous_accounts(claims, rev["period"]["to"], "KONSERN" if scope == "group" else "SELSKAP").get("revenue")
            try:
                if prev and float(prev["value"]) > 0:
                    pct = (float(rev["value"]) - float(prev["value"])) / float(prev["value"]) * 100
                    say(f"Revenue {'grew' if pct >= 0 else 'fell'} {abs(pct):.0f}% versus {prev['period']['to'][:4]} (derived from the two filings).", rev, prev, derived=True,
                        no=f"Driftsinntektene {'økte' if pct >= 0 else 'falt'} {abs(pct):.0f} % fra {prev['period']['to'][:4]} (avledet av de to regnskapene).")
            except (TypeError, ValueError):
                pass
    emp = _first(ident, "employees")
    if emp:
        say(f"The registry lists {emp['value']} employees" + (f" (as of {emp['effective_date']})" if emp.get("effective_date") else "") + ".", emp,
            no=f"Registeret oppgir {emp['value']} ansatte" + (f" (per {emp['effective_date']})" if emp.get("effective_date") else "") + ".")

    lead = by("leadership")
    ceo = _first(lead, "ceo")
    chair = _first(lead, "board_chair")
    if ceo or chair:
        bits, bits_no = [], []
        if ceo:
            bits.append(f"{ceo['value']} is CEO (daglig leder)")
            bits_no.append(f"{ceo['value']} er daglig leder")
        if chair:
            bits.append(f"{chair['value']} chairs the board")
            bits_no.append(f"{chair['value']} er styreleder")
        text = "; ".join(bits)
        say(text[:1].upper() + text[1:] + ".", ceo, chair, no="; ".join(bits_no) + ".")  # never re-case sourced names
    locs = by("locations")
    if locs:
        munis = sorted({(c["value"].get("municipality") or "") for c in locs if isinstance(c["value"], dict)} - {""})
        where = f"{', '.join(munis[:4])}{'…' if len(munis) > 4 else ''}"
        say(f"It has {len(locs)} registered workplace{'s' if len(locs) != 1 else ''}" + (f" in {where}" if munis else "") + ".", *locs[:5],
            no=f"Selskapet har {len(locs)} {'registrerte arbeidssteder' if len(locs) != 1 else 'registrert arbeidssted'}" + (f" i {where}" if munis else "") + ".")
    parent = _first(by("group"), "parent_company")
    subs = [c for c in by("group") if c["field"] == "subsidiary"]
    if parent:
        say(f"It is part of a group with parent {parent['value'].get('name')} (org. {parent['value'].get('organisation_number')}).", parent,
            no=f"Selskapet inngår i et konsern med morselskap {parent['value'].get('name')} (org.nr. {parent['value'].get('organisation_number')}).")
    if subs:
        say(f"It has {len(subs)} registered subsidiar{'ies' if len(subs) != 1 else 'y'}.", *subs[:5],
            no=f"Selskapet har {len(subs)} registrerte datterselskap{'er' if len(subs) != 1 else ''}.")

    site = _first(by("website"), "official_website")
    socials = by("social_profiles")
    jobs = by("jobs")
    if site:
        profile_kinds = ", ".join(c['field'].replace('_', '/') for c in socials)
        say(f"Its verified official website is {site['value']}" + (f", which links to {len(socials)} company-owned profile{'s' if len(socials) != 1 else ''} ({profile_kinds})" if socials else "") + ".", site, *socials,
            no=f"Bekreftet offisielt nettsted er {site['value']}" + (f", som lenker til {len(socials)} {'egne profiler' if len(socials) != 1 else 'egen profil'} ({profile_kinds})" if socials else "") + ".")
    if jobs:
        titles = [str(c["value"]["title"]) for c in jobs if isinstance(c["value"], dict) and c["value"].get("title")][:3]  # an ad without a title must not break the brief
        say(f"It currently advertises {len(jobs)} active job posting{'s' if len(jobs) != 1 else ''} on NAV" + (f", e.g. {', '.join(titles)}" if titles else "") + ".", *jobs,
            no=f"Selskapet har nå {len(jobs)} aktive stillingsannonse{'r' if len(jobs) != 1 else ''} hos NAV" + (f", for eksempel {', '.join(titles)}" if titles else "") + ".")
    acts = sorted(by("activity"), key=lambda c: c.get("effective_date") or "", reverse=True)
    if acts:
        a = acts[0]
        label = a["value"]["title"] if isinstance(a["value"], dict) else a["value"]
        say(f"Most recent dated activity: {label} ({a.get('effective_date')}).", a, no=f"Siste daterte aktivitet: {label} ({a.get('effective_date')}).")

    changes = envelope.get("changes") or []
    if changes:
        kinds: dict[str, int] = {}
        for ch in changes:
            kinds[ch["type"]] = kinds.get(ch["type"], 0) + 1
        text = "Since the previous run: " + ", ".join(f"{n} {k.replace('_', ' ')}" for k, n in sorted(kinds.items())) + "."
        text_no = "Siden forrige kjøring: " + ", ".join(f"{n} {CHANGE_NO.get(k, k.replace('_', ' '))}" for k, n in sorted(kinds.items())) + "."
        ids = [cid for ch in changes for cid in ch.get("evidence_ids", [])][:8]
        sentences.append({"text": text, "text_no": text_no, "claim_ids": [c["id"] for c in claims if any(e in c["evidence_ids"] for e in ids)][:8], "change_ids": [c["id"] for c in changes][:20]})

    signals = build_signals(claims)
    checks = build_checks(claims)
    unknowns = []
    for fam, meta in FAMILIES.items():
        st = (envelope.get("availability") or {}).get(fam) or {}
        if st.get("state") and st["state"] != "available":
            unknowns.append({"family": fam, "label": meta["label"], "state": st["state"], "reason": st.get("reason")})
    return {"sentences": sentences, "signals": signals, "checks": checks, "unknowns": unknowns,
            "method": "deterministic_template_v2 (English `text` + Norwegian `text_no` from the same claims; every sentence and signal cites claim IDs; derived values are labelled)"}


def build_signals(claims: list[dict]) -> list[dict]:
    """Decision-useful flags derived only from published claims. Each lists the claims it is computed from."""
    out: list[dict] = []
    latest = latest_accounts(claims)

    def num(c):
        try:
            return float(c["value"])
        except (TypeError, ValueError, KeyError):
            return None

    eq, assets, rev, op, res = (latest.get(k) for k in ("equity", "total_assets", "revenue", "operating_result", "net_result"))
    if eq and num(eq) is not None and num(eq) < 0:
        out.append({"kind": "risk", "label": "Negative equity", "text": f"Equity is negative ({money(eq['value'], eq.get('unit'))}).", "claim_ids": [eq["id"]]})
    if eq and assets and num(eq) is not None and num(assets):
        ratio = num(eq) / num(assets) * 100
        out.append({"kind": "risk" if ratio < 10 else "info", "label": "Equity ratio", "text": f"Equity ratio {ratio:.0f}% (derived: equity / total assets).",
                    "claim_ids": [eq["id"], assets["id"]], "derived": True})
    if op and rev and num(op) is not None and num(rev):
        margin = num(op) / num(rev) * 100
        out.append({"kind": "info", "label": "Operating margin", "text": f"Operating margin {margin:.0f}% (derived: operating result / revenue).",
                    "claim_ids": [op["id"], rev["id"]], "derived": True})
    if res:
        scope = "KONSERN" if "KONSERN" in (res.get("note") or "") else "SELSKAP"
        prev = previous_accounts(claims, res["period"]["to"], scope).get("net_result")
        if prev and num(res) is not None and num(prev) is not None and num(res) < 0 and num(prev) < 0:
            out.append({"kind": "risk", "label": "Consecutive losses", "text": "Net loss in the two latest filed years.", "claim_ids": [res["id"], prev["id"]]})
    status = [c for c in claims if c["family"] == "status" and c["field"] in ("konkurs", "underAvvikling", "underTvangsavviklingEllerTvangsopplosning")]
    for c in status:
        out.append({"kind": "risk", "label": c["label"], "text": f"Registry flag: {c['label'].lower()}.", "claim_ids": [c["id"]]})
    jobs = [c for c in claims if c["family"] == "jobs"]
    if jobs:
        out.append({"kind": "growth", "label": "Hiring", "text": f"{len(jobs)} active job posting(s) verified on NAV.", "claim_ids": [c["id"] for c in jobs][:6]})
    recent = sorted((c for c in claims if c["family"] == "activity" and c.get("effective_date")), key=lambda c: c["effective_date"], reverse=True)
    moves = [c for c in recent if "address" in str(c["value"]).lower()][:1]
    board = [c for c in recent if "Roles" in str(c["value"])][:1]
    for c, label in ((moves[0] if moves else None, "Recent address change"), (board[0] if board else None, "Recent board/management update")):
        if c:
            out.append({"kind": "info", "label": label, "text": f"{label} recorded {c['effective_date']}.", "claim_ids": [c["id"]]})
    return out


def build_checks(claims: list[dict]) -> list[dict]:
    """Cross-source consistency checks. They describe the data; they never change a published value."""
    out: list[dict] = []
    fin = [c for c in claims if c["family"] == "financials" and c.get("period") and isinstance(c.get("value"), (int, float))]
    groups: dict[tuple, dict] = {}
    for c in fin:
        groups.setdefault(((c.get("note") or ""), c["period"].get("to")), {})[c["field"]] = c
    for (note, to), g in sorted(groups.items(), key=lambda kv: kv[0][1] or "", reverse=True)[:2]:
        a, e, d = g.get("total_assets"), g.get("equity"), g.get("total_debt")
        if a and e and d:
            gap = abs(a["value"] - (e["value"] + d["value"]))
            ok = gap <= max(1000, abs(a["value"]) * 0.01)
            out.append({"check": "balance_sheet_identity", "result": "pass" if ok else "warn",
                        "text": f"{to[:4]} {note.split('=')[-1].lower() or 'company'} accounts: total assets {'=' if ok else '≠'} equity + debt"
                                + ("" if ok else f" (difference {gap:,.0f})"), "claim_ids": [a["id"], e["id"], d["id"]]})
    emp = next((c for c in claims if c["field"] == "employees"), None)
    units = [c for c in claims if c["family"] == "locations" and isinstance(c["value"], dict) and isinstance(c["value"].get("employees"), int)]
    if emp and units and isinstance(emp["value"], int):
        total = sum(c["value"]["employees"] for c in units)
        ok = total == emp["value"]
        out.append({"check": "employees_vs_workplaces", "result": "pass" if ok else "info",
                    "text": f"Registry employees {emp['value']} vs sum over registered workplaces {total}" + ("" if ok else " (registers update at different times)"),
                    "claim_ids": [emp["id"], *[c["id"] for c in units[:5]]]})
    return out
