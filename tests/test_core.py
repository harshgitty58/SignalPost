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
