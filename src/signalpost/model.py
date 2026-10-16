"""Claims, evidence and per-company profile assembly.

IDs are content-derived so that re-running on an identical source snapshot yields identical
claim and evidence IDs (idempotent refresh, no duplicate records).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

STATES = ("available", "not_available", "blocked", "not_applicable", "ambiguous", "failed")

# Field families, in profile-section order. `section` maps them to the seven required sections.
FAMILIES: dict[str, dict[str, str]] = {
    "identity": {"section": "Legal identity and public brand", "label": "Legal identity"},
    "status": {"section": "Legal identity and public brand", "label": "Registry status"},
    "industry": {"section": "Legal identity and public brand", "label": "Industry"},
    "financials": {"section": "Latest annual accounts and history", "label": "Annual accounts"},
    "leadership": {"section": "Leadership and registered workplaces", "label": "Leadership & roles"},
    "locations": {"section": "Leadership and registered workplaces", "label": "Registered workplaces"},
    "group": {"section": "Legal identity and public brand", "label": "Group structure"},
    "website": {"section": "Verified website and company-owned profiles", "label": "Official website"},
    "social_profiles": {"section": "Verified website and company-owned profiles", "label": "Company-owned profiles"},
    "contact": {"section": "Verified website and company-owned profiles", "label": "Contact"},
    "description": {"section": "Verified website and company-owned profiles", "label": "Self-description"},
    "jobs": {"section": "Hiring and dated public activity", "label": "Job postings"},
    "activity": {"section": "Hiring and dated public activity", "label": "Dated activity"},
}


def stable_id(prefix: str, *parts: Any) -> str:
    raw = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.split())
    return value


@dataclass
class Evidence:
    source_url: str
    source_class: str  # official_registry | official_registry_bulk | company_owned | public_api | open_data
    retrieved_at: str
    content_sha256: str
    claim_span: str
    extraction_method: str
    license: str | None = None
    identity_reason: str | None = None
    reporting_period: dict[str, str] | None = None
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = stable_id("ev", self.source_url, self.content_sha256, self.claim_span[:300])

    def to_dict(self) -> dict[str, Any]:
        out = {
            "id": self.id,
            "source_url": self.source_url,
            "source_class": self.source_class,
            "retrieved_at": self.retrieved_at,
            "content_sha256": self.content_sha256,
            "claim_span": self.claim_span[:600],
            "extraction_method": self.extraction_method,
        }
        if self.license:
            out["license"] = self.license
        if self.identity_reason:
            out["identity_reason"] = self.identity_reason
        if self.reporting_period:
            out["reporting_period"] = self.reporting_period
        return out


@dataclass
class Claim:
    family: str
    field: str
    value: Any
    evidence_ids: list[str]
    label: str = ""
    confidence: float = 1.0
    period: dict[str, str] | None = None
    effective_date: str | None = None
    unit: str | None = None
    derived: bool = False
    note: str | None = None
    key: str | None = None  # stable identity of the fact (for multi-valued fields: e.g. role+person)
    id: str = ""

    def __post_init__(self) -> None:
        self.value = normalize_value(self.value)
        if self.key is None:
            self.key = self.field
        if not self.id:
            self.id = stable_id("c", self.family, self.key, self.value, self.period)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "family": self.family,
            "field": self.field,
            "key": self.key,
            "label": self.label or self.field.replace("_", " "),
            "value": self.value,
            "availability": "available",
            "confidence": self.confidence,
            "evidence_ids": self.evidence_ids,
        }
        for name in ("period", "effective_date", "unit", "note"):
            if getattr(self, name) is not None:
                out[name] = getattr(self, name)
        if self.derived:
            out["derived"] = True
        return out


@dataclass
class FamilyState:
    state: str
    reason: str
    checked_sources: list[str] = field(default_factory=list)


class ProfileBuilder:
    def __init__(self, org: str):
        self.org = org
        self.claims: dict[str, Claim] = {}
        self.evidence: dict[str, Evidence] = {}
        self.families: dict[str, FamilyState] = {}
        self.errors: list[dict[str, Any]] = []
        self.candidates: list[dict[str, Any]] = []  # rejected / ambiguous candidates (kept for audit, never published)
        self.extra: dict[str, Any] = {}
        self.requests = 0

    def add_evidence(self, ev: Evidence) -> str:
        self.evidence.setdefault(ev.id, ev)
        return ev.id

    def add(self, claim: Claim) -> Claim:
        if not claim.evidence_ids:
            raise ValueError(f"claim without evidence: {claim.field}")
        missing = [eid for eid in claim.evidence_ids if eid not in self.evidence]
        if missing:
            raise ValueError(f"claim references unknown evidence: {missing}")
        if claim.value is None or claim.value == "" or claim.value == []:
            raise ValueError(f"empty claim value for {claim.field}")
        existing = self.claims.get(claim.id)
        if existing:
            for eid in claim.evidence_ids:
                if eid not in existing.evidence_ids:
                    existing.evidence_ids.append(eid)
            return existing
        self.claims[claim.id] = claim
        return claim

    def set_state(self, family: str, state: str, reason: str, *sources: str) -> None:
        assert state in STATES, state
        current = self.families.get(family)
        # never downgrade an available family because of a later secondary failure
        if current and current.state == "available" and state != "available":
            current.checked_sources.extend(s for s in sources if s not in current.checked_sources)
            return
        self.families[family] = FamilyState(state, reason, list(sources))

    def family_claims(self, family: str) -> list[Claim]:
        return [c for c in self.claims.values() if c.family == family]

    def finalize_states(self) -> None:
        for family in FAMILIES:
            has = bool(self.family_claims(family))
            st = self.families.get(family)
            if has:
                if not st or st.state != "available":
                    self.families[family] = FamilyState("available", st.reason if st and st.state == "available" else "found", st.checked_sources if st else [])
            elif not st:
                self.families[family] = FamilyState("failed", "family not processed in this run")
            elif st.state == "available":
                st.state = "not_available"
                st.reason = "no publishable claims"

    def error(self, family: str, message: str, url: str | None = None) -> None:
        self.errors.append({"family": family, "message": message, **({"url": url} if url else {})})
