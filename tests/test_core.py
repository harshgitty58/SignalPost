import copy

from signalpost.http import Snapshot
from signalpost.model import Claim, Evidence, ProfileBuilder
from signalpost.pipeline import validate
from signalpost.refresh import diff
from signalpost.web import Page, find_orgnrs, identity_tokens, is_parked, valid_orgnr


def page(html: str, url: str = "https://example.no/") -> Page:
    return Page(Snapshot(url, url, 200, "2026-10-16T00:00:00Z", body=html.encode(), content_type="text/html; charset=utf-8"))


def test_orgnr_checksum_and_context():
    assert valid_orgnr("923609016")
    assert not valid_orgnr("923609017")
    assert find_orgnrs("Equinor ASA · Org.nr: 923 609 016 MVA") == {"923609016"}
    assert find_orgnrs("Ring oss på 923 609 016") == set()  # no org-number context => not proof


def test_address_like_names_are_not_identity_evidence():
    entity = {"forretningsadresse": {"adresse": ["Hinderveien 2"], "poststed": "SANDEFJORD"}}
    assert identity_tokens(entity, "HINDERVEIEN 2 AS") == []


def test_parked_page_detected():
    assert is_parked(page("<html><title>Domenet er til salgs</title><body>Dette domenet er til salgs. " + "x " * 100 + "</body></html>"))


def _env(claims, evidence, states=None, run_id="r1"):
    return {"organisation_number": "923609016", "run": {"run_id": run_id, "completed_at": "2026-10-16T00:00:00Z"},
            "claims": claims, "evidence": evidence, "availability": states or {"financials": {"state": "available"}, "jobs": {"state": "available"}}}


def _claim(family, key, value):
    pb = ProfileBuilder("923609016")
    ev = pb.add_evidence(Evidence("https://x", "official_registry", "t", "h" * 64, "span", "m"))
    c = pb.add(Claim(family, key, value, [ev], key=key))
    return c.to_dict(), pb.evidence[ev].to_dict()


def test_refresh_idempotent_and_typed():
    c1, e1 = _claim("jobs", "job:1", {"title": "Elektriker"})
    prev = _env([c1], [e1])
    same = copy.deepcopy(prev)
    assert diff(prev, same, detected_at="t")[0] == []
    c2, e2 = _claim("jobs", "job:2", {"title": "Lærling"})
    changes, meta = diff(prev, _env([c2], [e2]), detected_at="t")
    assert sorted(ch["type"] for ch in changes) == ["closed_job", "new_job"]


def test_unreadable_family_is_carried_forward_not_removed():
    c1, e1 = _claim("jobs", "job:1", {"title": "Elektriker"})
    cur = _env([], [], states={"jobs": {"state": "failed", "reason": "source error"}})
    changes, meta = diff(_env([c1], [e1]), cur, detected_at="t")
    assert changes == [] and meta["not_compared"] == ["jobs"]
    assert cur["claims"][0]["stale_since"] and cur["evidence"][0]["id"] == e1["id"]


def test_contract_validation():
    c1, e1 = _claim("financials", "revenue", 10)
    env = _env([c1], [e1], states={f: {"state": "not_available"} for f in
                                   ["identity", "status", "industry", "financials", "leadership", "locations", "group", "website",
                                    "social_profiles", "contact", "description", "jobs", "activity"]})
    assert validate([env], ["923609016"])["passed"]
    assert not validate([env], ["923609016", "914778271"])["passed"]


def test_blank_registry_fields_are_skipped_not_fatal():
    from signalpost.registry import entity_claims
    pb = ProfileBuilder("923609016")
    entity_claims(pb, {"navn": "TEST AS", "vedtektsfestetFormaal": [" "], "hjemmeside": "", "kapital": {}},
                  retrieved_at="t", source_class="official_registry", method="m")
    assert [c.field for c in pb.claims.values()] == ["legal_name"]


def test_input_header_and_duplicates(tmp_path):
    from signalpost.pipeline import read_inputs
    p = tmp_path / "batch.csv"
    p.write_text("organisation_number\n923609016\n923609016\n12345\n", encoding="utf-8")
    assert read_inputs(p) == ["923609016", "12345"]  # header skipped, duplicate folded, malformed kept (gets an envelope)


def test_first_seen_is_carried_across_runs():
    c1, e1 = _claim("jobs", "job:1", {"title": "Elektriker"})
    prev = _env([dict(c1, first_seen="2026-10-01T00:00:00Z")], [e1])
    cur = _env([dict(c1)], [e1])
    diff(prev, cur, detected_at="2026-10-17T00:00:00Z")
    assert cur["claims"][0]["first_seen"] == "2026-10-01T00:00:00Z"


def test_balance_sheet_check():
    from signalpost.synthesis import build_checks
    p = {"from": "2025-01-01", "to": "2025-12-31"}
    mk = lambda f, v: {"id": f, "family": "financials", "field": f, "value": v, "period": p, "note": "account_type=SELSKAP"}  # noqa: E731
    assert build_checks([mk("total_assets", 100_000), mk("equity", 40_000), mk("total_debt", 60_000)])[0]["result"] == "pass"
    assert build_checks([mk("total_assets", 100_000), mk("equity", 10_000), mk("total_debt", 60_000)])[0]["result"] == "warn"


def test_brief_keeps_sourced_name_casing():
    from signalpost.synthesis import build_brief
    mk = lambda fam, f, v: {"id": f, "family": fam, "field": f, "value": v, "availability": "available", "evidence_ids": ["e"]}  # noqa: E731
    env = {"organisation_number": "984661185", "availability": {}, "claims": [
        mk("identity", "legal_name", "POSTEN BRING AS"), mk("identity", "legal_form", "Aksjeselskap (AS)"),
        mk("leadership", "ceo", "Petter-Børre Furberg"), mk("leadership", "board_chair", "Pål Wibe")]}
    text = " ".join(s["text"] for s in build_brief(env)["sentences"])
    assert "Petter-Børre Furberg is CEO" in text and "Pål Wibe chairs the board" in text
    assert "is an aksjeselskap" in text


def test_declared_website_reason_names_the_real_source():
    from signalpost.web import DECLARED_BY
    assert "Wikidata" in DECLARED_BY["wikidata_p856"] and "P2333" in DECLARED_BY["wikidata_p856"]
    assert "registry" in DECLARED_BY["registry_declared"] and "Wikidata" not in DECLARED_BY["registry_declared"]


def test_small_batch_budgets_group_for_every_company(tmp_path):
    from signalpost.pipeline import Runner
    orgs = ["923609016", "984661185", "947942638", "984851006", "982463718", "910747711",
            "911382296", "975959171", "984024290", "965920358", "996756246", "881932792"]
    r = Runner(orgs, out_dir=tmp_path, run_id="t", bulk=None, previous=None, max_requests=2000, max_minutes=45.0,
               max_cost=10.0, workers=4, job_days=7)
    assert r.plan["group"] >= len(orgs)
