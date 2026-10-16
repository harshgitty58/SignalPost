"""Official-website discovery behind a strict exact-entity identity gate, plus company-owned extraction.

Publication rule: a domain is the company's official website only with one of these proofs
  1. orgnr_on_site      — the company's exact organisation number (mod-11 valid) is printed on the site
                          and the site does not present a *different* organisation number as its owner;
  2. contact_match      — every distinctive legal-name token is on the site AND the registry phone number
                          or the registry street address + postcode is on the site (no conflicting orgnr);
  3. registry_declared  — the registry itself lists this website for the entity AND all distinctive
                          legal-name tokens appear in the site's identity fields (title / site name / JSON-LD),
                          with no conflicting organisation number.
Everything else is `ambiguous` (kept as an audit candidate, never published). Parent / brand / sister
sites (a different orgnr) are rejected as `related_site`. Social links, e-mail, description and news
are only taken from a site that passed the gate.
"""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from lxml import etree, html as lhtml

from .budget import BudgetExhausted
from .http import Fetcher, Snapshot, host_is_public
from .model import Claim, Evidence, ProfileBuilder

FREE_MAIL = {
    "gmail.com", "hotmail.com", "hotmail.no", "outlook.com", "outlook.no", "live.com", "live.no", "yahoo.com", "yahoo.no",
    "online.no", "icloud.com", "me.com", "msn.com", "start.no", "frisurf.no", "broadpark.no", "getmail.no", "c2i.net",
    "lyse.net", "altibox.no", "telia.no", "netcom.no", "hotmail.co.uk", "aol.com", "mail.com", "protonmail.com", "proton.me",
    "gmx.com", "gmx.net", "ebnett.no", "tele2.no", "chello.no", "bluezone.no", "tdcadsl.no", "loqal.no", "monet.no",
    "sensewave.com", "haugnett.no", "enivest.net", "nktv.no", "vikenfiber.no", "tussa.com", "vtel.no", "neasonline.no",
}
# Host families that are never "the company's website"
NON_COMPANY_HOSTS = (
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com", "youtube.com", "tiktok.com", "google.com",
    "proff.no", "gulesider.no", "1881.no", "purehelp.no", "brreg.no", "finn.no", "mittanbud.no", "bedriftsdatabasen.no",
    "firmasok.no", "regnskapstall.no", "kompass.com", "enirodigital", "wix.com", "wixsite.com", "squarespace.com",
    "weebly.com", "blogspot.com", "wordpress.com", "123hjemmeside.no", "jimdo.com", "jimdofree.com", "business.site",
    "nav.no", "altinn.no", "vipps.no", "linktr.ee", "godaddysites.com", "one.com", "domeneshop.no", "uniweb.no",
)
PARKED_MARKERS = (
    "domain is for sale", "domain for sale", "domenet er til salgs", "dette domenet er til salgs", "kjøp dette domenet",
    "hugedomains", "parked at", "parked domain", "this domain is parked", "domeneshop.no/parkert", "parkert hos",
    "her flytter snart en ny gjest", "under construction", "under konstruksjon", "kommer snart", "coming soon",
    "website is under construction", "nettsiden er under utvikling", "default web site page", "welcome to nginx",
    "apache2 default page", "it works!", "index of /", "account suspended", "this account has been suspended",
    "just another wordpress site", "bare nok en wordpress-side", "en ny wordpress-side", "web hosting by", "sedo",
    "this site can’t be reached", "future home of", "registered at one.com", "domenet er registrert",
)
GENERIC_TOKENS = {
    "norge", "norway", "norsk", "norske", "nordic", "scandinavia", "group", "gruppen", "holding", "holdings", "invest",
    "investering", "eiendom", "eiendommer", "property", "properties", "service", "services", "consult", "consulting",
    "konsult", "bygg", "byggservice", "entreprenor", "transport", "regnskap", "regnskapskontor", "handel", "drift",
    "utvikling", "management", "partner", "partners", "solutions", "systems", "teknikk", "tjenester", "kompani", "co",
    "company", "the", "og", "and", "i", "pa", "av", "for", "til", "med", "nye", "ny", "maler", "elektro", "ror",
    "vvs", "auto", "bil", "data", "it", "media", "design", "studio", "sport", "helse", "klinikk", "tannlege", "frisor",
    "eiendomsselskap", "capital", "ventures", "international", "int", "nord", "sor", "vest", "ost", "midt",
}
HOLDING_WORDS = {"holding", "holdings", "invest", "investering", "investment", "investments", "capital", "eiendom", "eiendommer",
                 "property", "properties", "forvaltning", "ventures", "finans", "kapital", "eie", "beholdning"}
LEGAL = {"as", "asa", "ans", "da", "sa", "ba", "nuf", "enk", "iks", "kf", "stiftelsen", "sf", "ks", "bbl", "brl", "ltd", "ab", "inc", "llc", "gmbh"}
SOCIAL_PATTERNS = {
    "linkedin": re.compile(r"^https?://([a-z]{2,3}\.)?linkedin\.com/(company|school|showcase)/[^/?#]+", re.I),
    "facebook": re.compile(r"^https?://(www\.|m\.|nb-no\.)?facebook\.com/(?!sharer|share|dialog|plugins|tr\b|groups/|events/|hashtag/|login|policy|privacy)[^/?#]+", re.I),
    "instagram": re.compile(r"^https?://(www\.)?instagram\.com/(?!p/|explore|accounts|reel/)[^/?#]+", re.I),
    "youtube": re.compile(r"^https?://(www\.)?youtube\.com/(channel/|c/|user/|@)[^/?#]+", re.I),
    "x_twitter": re.compile(r"^https?://(www\.)?(twitter|x)\.com/(?!intent|share|home|search|hashtag)[^/?#]+", re.I),
    "tiktok": re.compile(r"^https?://(www\.)?tiktok\.com/@[^/?#]+", re.I),
}
ROLE_MAILBOXES = {
    "post", "postmottak", "info", "kontakt", "contact", "firmapost", "mail", "salg", "sales", "office", "kontor", "kundeservice",
    "support", "service", "hei", "hello", "hallo", "booking", "bestilling", "ordre", "order", "faktura", "invoice", "regnskap",
    "admin", "resepsjon", "reception", "jobb", "karriere", "career", "careers", "jobs", "press", "presse", "media", "marketing",
    "marked", "butikk", "shop", "nettbutikk", "web", "verksted", "drift", "bedrift", "kunde", "kunder", "enquiries", "inquiries",
}
SUBPAGE_HINTS = re.compile(r"(kontakt|contact|om-oss|om_oss|omoss|about|personvern|privacy|vilkar|vilkår|terms|impressum|kjopsbetingelser|salgsbetingelser|firma|selskapet|company)", re.I)
NEWS_HINTS = re.compile(r"(nyheter|aktuelt|news|blogg|blog|presse|press|artikler|articles|siste-nytt)", re.I)
ORG_RE = re.compile(r"(?<![\d])(\d{3})[\s .\-]?(\d{3})[\s .\-]?(\d{3})(?![\d])")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def fold(text: str | None) -> str:
    text = (text or "").casefold().translate(str.maketrans({"ø": "o", "å": "a", "æ": "ae", "ö": "o", "ä": "a", "ü": "u"}))
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def name_tokens(name: str | None) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", fold(name)) if t not in LEGAL]


def distinctive_tokens(name: str | None) -> list[str]:
    return [t for t in name_tokens(name) if t not in GENERIC_TOKENS and len(t) >= 3 and not t.isdigit()]


def valid_orgnr(org: str) -> bool:
    if len(org) != 9 or not org.isdigit() or org[0] not in "89":
        return False
    weights = [3, 2, 7, 6, 5, 4, 3, 2]
    remainder = sum(int(d) * w for d, w in zip(org[:8], weights)) % 11
    check = 0 if remainder == 0 else 11 - remainder
    return check != 10 and check == int(org[8])


def find_orgnrs(text: str) -> set[str]:
    found = set()
    for match in ORG_RE.finditer(text):
        candidate = "".join(match.groups())
        if valid_orgnr(candidate):
            # require an org-number context nearby to avoid matching random 9-digit numbers (phones are 8 digits)
            window = fold(text[max(0, match.start() - 40): match.end() + 10])
            if re.search(r"org|foretaks|mva|vat|reg\.?\s?nr|bedrifts|company", window):
                found.add(candidate)
    return found


def registrable_domain(url_or_host: str) -> str:
    host = urllib.parse.urlsplit(url_or_host if "://" in url_or_host else "http://" + url_or_host).hostname or ""
    host = host.lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def normalize_site(value: str | None) -> str | None:
    value = (value or "").strip().strip("/")
    if not value or " " in value or "@" in value:
        return None
    if "://" not in value:
        value = "https://" + value
    parts = urllib.parse.urlsplit(value)
    if not parts.hostname or "." not in parts.hostname:
        return None
    host = parts.hostname.lower()
    if any(host == h or host.endswith("." + h) for h in NON_COMPANY_HOSTS):
        return None
    return f"https://{host}/"


# ------------------------------------------------------------------------------------------ parsing

class Page:
    def __init__(self, snap: Snapshot):
        self.snap = snap
        self.url = snap.final_url
        raw = snap.text()
        self.raw = raw
        try:
            self.doc = lhtml.fromstring(raw) if raw.strip() else None
        except (etree.ParserError, ValueError):
            self.doc = None
        self.title = ""
        self.meta: dict[str, str] = {}
        self.text = ""
        self.links: list[tuple[str, str]] = []
        self.jsonld: list[dict] = []
        self.feeds: list[str] = []
        if self.doc is None:
            return
        doc = self.doc
        t = doc.find(".//title")
        self.title = " ".join((t.text_content() if t is not None else "").split())
        for m in doc.iter("meta"):
            key = (m.get("property") or m.get("name") or "").lower()
            if key and m.get("content"):
                self.meta.setdefault(key, " ".join(m.get("content").split()))
        for s in doc.xpath("//script[@type='application/ld+json']"):
            try:
                data = json.loads(s.text_content().strip() or "null")
            except (json.JSONDecodeError, ValueError):
                continue
            stack = [data]
            while stack:
                node = stack.pop()
                if isinstance(node, list):
                    stack.extend(node)
                elif isinstance(node, dict):
                    self.jsonld.append(node)
                    if "@graph" in node:
                        stack.append(node["@graph"])
        for link in doc.xpath("//link[@rel='alternate'][@href]"):
            if "rss" in (link.get("type") or "") or "atom" in (link.get("type") or ""):
                self.feeds.append(urllib.parse.urljoin(self.url, link.get("href")))
        for a in doc.xpath("//a[@href]"):
            href = a.get("href", "").strip()
            if href.startswith(("javascript:", "#")):
                continue
            self.links.append((urllib.parse.urljoin(self.url, href), " ".join(a.text_content().split())[:80]))
        for bad in doc.xpath("//script|//style|//noscript|//template"):
            bad.drop_tree() if bad.getparent() is not None else None
        try:
            self.text = " ".join(doc.text_content().split())
        except ValueError:
            self.text = ""

    def identity_fields(self, strict: bool = False) -> str:
        parts = [self.title, self.meta.get("og:site_name", ""), self.meta.get("og:title", ""), self.meta.get("application-name", "")]
        for node in self.jsonld:
            if str(node.get("@type", "")).lower() in {"organization", "localbusiness", "corporation", "website", "store", "restaurant", "professionalservice"} or "Organization" in str(node.get("@type", "")):
                for key in ("name", "legalName", "alternateName"):
                    if isinstance(node.get(key), str):
                        parts.append(node[key])
        if self.doc is not None and not strict:
            for el in self.doc.xpath("//h1|//header//img[@alt]|//footer"):
                parts.append(el.get("alt") if el.tag == "img" else el.text_content()[:400])
        return " ".join(p for p in parts if p)


# ------------------------------------------------------------------------------------------ gate

def _tokens_present(tokens: list[str], text: str) -> bool:
    words = set(re.findall(r"[a-z0-9]+", fold(text)))
    compact = re.sub(r"[^a-z0-9]", "", fold(text))
    return all(t in words or (len(t) >= 5 and t in compact) for t in tokens)


def _phone_present(phone: str | None, text: str) -> bool:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("47") and len(digits) == 10:
        digits = digits[2:]
    if len(digits) != 8:
        return False
    flat = re.sub(r"[\s \-.()]", "", text)
    return digits in flat


def _address_present(entity: dict, text: str) -> bool:
    addr = entity.get("forretningsadresse") or entity.get("postadresse") or {}
    lines = addr.get("adresse") or []
    street = fold(lines[0]) if lines else ""
    postcode = addr.get("postnummer") or ""
    if not street or not postcode or len(street) < 5:
        return False
    ftext = fold(text)
    street_norm = re.sub(r"\s+", " ", street).strip()
    return street_norm in re.sub(r"\s+", " ", ftext) and re.search(rf"(?<!\d){postcode}(?!\d)", text) is not None


def is_parked(page: Page) -> bool:
    sample = fold(page.title + " " + page.text[:3000])
    if len(page.text) < 120 and not page.jsonld:
        return True
    return any(marker in sample for marker in (fold(m) for m in PARKED_MARKERS))


class SiteVisit:
    def __init__(self, candidate: str, source: str):
        self.candidate = candidate
        self.source = source
        self.pages: list[Page] = []
        self.decision = "unchecked"
        self.reason = ""
        self.proof_page: Page | None = None
        self.proof_span = ""
        self.foreign_orgs: set[str] = set()

    @property
    def origin(self) -> str:
        page = self.pages[0] if self.pages else None
        url = page.url if page else self.candidate
        parts = urllib.parse.urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}/"


def _span_around(text: str, needle_re: str, width: int = 90) -> str:
    m = re.search(needle_re, text)
    if not m:
        return ""
    return text[max(0, m.start() - width): m.end() + width].strip()


def org_pattern(org: str) -> str:
    return rf"{org[:3]}[\s .\-]?{org[3:6]}[\s .\-]?{org[6:]}"


def address_tokens(entity: dict) -> set[str]:
    out: set[str] = set()
    for key in ("forretningsadresse", "postadresse"):
        addr = entity.get(key) or {}
        for line in (addr.get("adresse") or []) + [addr.get("poststed") or "", addr.get("kommune") or ""]:
            out |= set(re.findall(r"[a-z0-9]+", fold(line)))
    return out


def identity_tokens(entity: dict, legal_name: str) -> list[str]:
    """Distinctive legal-name tokens that are *not* simply the company's own address (e.g. 'Hinderveien 2 AS')."""
    addr = address_tokens(entity)
    return [t for t in distinctive_tokens(legal_name) if t not in addr]


def _footer_text(page: Page) -> str:
    if page.doc is None:
        return page.text[-1500:]
    feet = page.doc.xpath("//footer")
    return " ".join(f.text_content() for f in feet)[:4000] if feet else page.text[-1500:]


def visit_site(fetcher: Fetcher, candidate: str, source: str, org: str, entity: dict, legal_name: str,
               related_orgs: set[str], max_subpages: int = 3, person_tokens: set[str] | None = None) -> SiteVisit:
    visit = SiteVisit(candidate, source)
    host = urllib.parse.urlsplit(candidate).hostname or ""
    if not host_is_public(host):
        alt = host[4:] if host.startswith("www.") else "www." + host
        if host_is_public(alt):
            candidate = candidate.replace(host, alt, 1)
            visit.candidate = candidate
    snap = fetcher.get(candidate, phase="web")
    if not snap.ok and snap.error != "blocked_robots" and candidate.startswith("https://"):
        snap = fetcher.get("http://" + candidate[len("https://"):], phase="web")
    if snap.error == "blocked_robots":
        visit.decision, visit.reason = "blocked", "robots.txt disallows the homepage"
        return visit
    if not snap.ok or "html" not in (snap.content_type or "html"):
        visit.decision, visit.reason = "unreachable", f"homepage not reachable ({snap.status or snap.error})"
        return visit
    home = Page(snap)
    visit.pages.append(home)
    final_host = urllib.parse.urlsplit(home.url).hostname or ""
    if any(final_host == h or final_host.endswith("." + h) for h in NON_COMPANY_HOSTS):
        visit.decision, visit.reason = "rejected", f"redirects to a non-company platform ({final_host})"
        return visit
    redirected = registrable_domain(home.url) != registrable_domain(candidate)
    if redirected:
        # cross-domain redirect: only an exact organisation number on the destination can prove identity
        visit.reason = f"redirected to {registrable_domain(home.url)}; "
    if is_parked(home):
        visit.decision, visit.reason = "rejected", "parked / placeholder / empty site"
        return visit
    multi_entity = False

    def scan(page: Page) -> bool:
        nonlocal multi_entity
        orgs = find_orgnrs(page.text + " " + " ".join(json.dumps(n, ensure_ascii=False) for n in page.jsonld))
        others = {o for o in orgs if o != org}
        if org in orgs:
            if others and org not in find_orgnrs(_footer_text(page)):
                # several organisation numbers on one page (group/portfolio/client list): not proof of ownership
                multi_entity = True
                visit.foreign_orgs |= others
                return False
            visit.proof_page = page
            visit.proof_span = _span_around(page.text, org_pattern(org)) or f"organisation number {org}"
            return True
        visit.foreign_orgs |= others
        return False

    if not scan(home):
        # follow likely legal/contact pages on the same site
        seen = {home.url.rstrip("/")}
        targets = []
        for url, text in home.links:
            if registrable_domain(url) != registrable_domain(home.url):
                continue
            if url.rstrip("/") in seen or re.search(r"\.(pdf|jpg|png|zip|docx?)$", url, re.I):
                continue
            if SUBPAGE_HINTS.search(urllib.parse.urlsplit(url).path) or SUBPAGE_HINTS.search(fold(text)):
                seen.add(url.rstrip("/"))
                targets.append(url)
        targets.sort(key=lambda u: (0 if re.search(r"kontakt|contact", u, re.I) else 1 if re.search(r"om-oss|about", u, re.I) else 2))
        for url in targets[:max_subpages]:
            try:
                sub = fetcher.get(url, phase="web")
            except BudgetExhausted:
                break
            if not sub.ok:
                continue
            page = Page(sub)
            visit.pages.append(page)
            if scan(page):
                break

    if visit.proof_page is not None:
        visit.decision = "accepted"
        visit.reason += "exact organisation number printed on the site"
        return visit
    # conflicting org number: this is somebody else's site (parent, brand, sister, accountant, web agency…)
    owner_conflict = visit.foreign_orgs - related_orgs
    if visit.foreign_orgs:
        rel = visit.foreign_orgs & related_orgs
        if rel:
            visit.decision = "related_site"
            visit.reason += f"site belongs to related entity {sorted(rel)[0]} (group relation) — labelled, not merged"
        else:
            visit.decision = "rejected"
            visit.reason += f"site presents a different organisation number ({sorted(owner_conflict)[0]})"
        return visit

    if multi_entity:
        visit.decision = "ambiguous"
        visit.reason += "organisation number appears only among several companies' numbers (group/portfolio page)"
        return visit
    if redirected:
        visit.decision = "ambiguous"
        visit.reason += "cross-domain redirect without the exact organisation number on the destination"
        return visit
    all_text = " ".join(p.title + " " + p.text for p in visit.pages)
    tokens = identity_tokens(entity, legal_name)
    if set(name_tokens(legal_name)) & HOLDING_WORDS:
        visit.decision, visit.reason = "ambiguous", visit.reason + "holding/investment company: only the exact organisation number can prove the site is its own"
        return visit
    if tokens and person_tokens and set(tokens) <= person_tokens:
        visit.decision, visit.reason = "ambiguous", visit.reason + "legal name consists of a role holder's personal name; needs the organisation number"
        return visit
    if not tokens:
        visit.decision, visit.reason = "ambiguous", visit.reason + "legal name is too generic (or is just the address) to verify without an organisation number"
        return visit
    identity_text = " ".join(p.identity_fields() for p in visit.pages)
    name_in_identity = _tokens_present(tokens, identity_text)
    contact = _phone_present(entity.get("telefon"), all_text) or _phone_present(entity.get("mobil"), all_text) or _address_present(entity, all_text)
    if name_in_identity and contact and registrable_domain(home.url).endswith(".no"):
        visit.decision = "accepted"
        visit.proof_page = visit.pages[0]
        visit.proof_span = "legal name in site identity + registry contact details: " + (_span_around(identity_text, r"(?i)" + re.escape(tokens[0]))[:200])
        visit.reason += "legal name in the site's identity fields and registry phone/address on the site"
        return visit
    identity_text = visit.pages[0].identity_fields(strict=True)
    if source == "registry_declared" and _tokens_present(name_tokens(legal_name), identity_text):
        visit.decision = "accepted"
        visit.proof_page = home
        visit.proof_span = "registry declares this website; site identity fields: " + identity_text[:200]
        visit.reason += "registry declares this website and the site's identity fields carry the legal name"
        return visit
    visit.decision = "ambiguous"
    visit.reason += "no organisation number and insufficient name/contact evidence"
    return visit


def domain_candidates(entity: dict, bulk_row: dict | None) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    def push(url: str | None, source: str) -> None:
        site = normalize_site(url)
        if not site:
            return
        dom = registrable_domain(site)
        if dom in seen:
            return
        seen.add(dom)
        out.append((site, source))

    for row in (entity, bulk_row or {}):
        push(row.get("hjemmeside"), "registry_declared")
    email = (bulk_row or {}).get("epostadresse") or entity.get("epostadresse")
    if email and "@" in email:
        dom = email.split("@", 1)[1].strip().lower()
        if dom not in FREE_MAIL and not any(dom.endswith(f) for f in ("online.no",)):
            push(dom, "registry_email_domain")
    tokens = name_tokens(entity.get("navn"))
    distinct = distinctive_tokens(entity.get("navn"))
    if distinct and 1 <= len(tokens) <= 3:
        joined = "".join(tokens)
        if len(joined) >= 5:
            for cand in (joined + ".no", "-".join(tokens) + ".no" if len(tokens) > 1 else None):
                if cand and host_is_public(cand):
                    push(cand, "name_slug_guess")
    return out


# ------------------------------------------------------------------------------------------ extraction

def _social_ok(platform: str, url: str, page: Page, legal_name: str, domain: str, sameas: set[str]) -> bool:
    if url.rstrip("/") in sameas:
        return True
    handle = fold(urllib.parse.unquote(urllib.parse.urlsplit(url).path)).strip("/@ ")
    handle = re.sub(r"^(company|school|showcase|channel|c|user|pages?)/", "", handle)
    compact = re.sub(r"[^a-z0-9]", "", handle)
    label = re.sub(r"[^a-z0-9]", "", domain.split(".")[0])
    distinct = distinctive_tokens(legal_name) or name_tokens(legal_name)
    if label and len(label) >= 4 and label in compact:
        return True
    return bool(distinct) and all(t in compact for t in distinct[:2])


def extract_company_owned(pb: ProfileBuilder, fetcher: Fetcher, visit: SiteVisit, legal_name: str, *, want_news: bool = True) -> None:
    home = visit.pages[0]
    domain = registrable_domain(home.url)
    origin = visit.origin
    proof = visit.proof_page or home
    ev_site = pb.add_evidence(Evidence(proof.url, "company_owned", proof.snap.retrieved_at, proof.snap.sha256, visit.proof_span or home.title,
                                       f"identity_gate:{visit.source}", identity_reason=visit.reason))
    pb.add(Claim("website", "official_website", origin, [ev_site], label="Official website",
                 confidence=1.0 if "organisation number" in visit.reason else 0.9, note=f"discovered via {visit.source}"))
    pb.set_state("website", "available", visit.reason, visit.candidate)

    # public brand (site name differs from legal name)
    brand = home.meta.get("og:site_name") or next((n.get("name") for n in home.jsonld if isinstance(n.get("name"), str) and "Organization" in str(n.get("@type", ""))), None)
    if brand and 2 < len(brand) < 60 and fold(brand) not in fold(legal_name) and fold(legal_name).split(" ")[0] not in fold(brand).split(" ")[:1]:
        ev = pb.add_evidence(Evidence(home.url, "company_owned", home.snap.retrieved_at, home.snap.sha256, f'og:site_name / JSON-LD name: "{brand}"', "html_meta:og:site_name"))
        pb.add(Claim("identity", "public_brand", brand, [ev, ev_site], label="Public brand (from verified site)", confidence=0.9))

    # social profiles: outbound links on the verified site (company-owned declarations)
    sameas: set[str] = set()
    for node in home.jsonld:
        same = node.get("sameAs")
        for s in (same if isinstance(same, list) else [same] if isinstance(same, str) else []):
            sameas.add(str(s).rstrip("/"))
    socials: dict[str, tuple[str, Page]] = {}
    for page in visit.pages:
        for url, _text in page.links + [(s, "") for s in sameas]:
            for platform, pattern in SOCIAL_PATTERNS.items():
                m = pattern.match(url)
                if m and platform not in socials:
                    clean = m.group(0).rstrip("/")
                    if _social_ok(platform, clean, page, legal_name, domain, sameas):
                        socials[platform] = (clean, page)
    for platform, (url, page) in socials.items():
        ev = pb.add_evidence(Evidence(page.url, "company_owned", page.snap.retrieved_at, page.snap.sha256, f'<a href="{url}">', "html_link:outbound_social",
                                      identity_reason="linked from the verified official website; handle matches the company name/domain"))
        pb.add(Claim("social_profiles", platform, url, [ev], label=platform.replace("_", "/").title() + " profile", key=f"social:{platform}"))
    pb.set_state("social_profiles", "available" if socials else "not_available",
                 f"{len(socials)} company-owned profiles linked from the verified site" if socials else "verified site links no company-owned social profiles", origin)

    # contact e-mail: role mailboxes on the company's own domain only (no personal addresses)
    mails: dict[str, Page] = {}
    for page in visit.pages:
        found = set(EMAIL_RE.findall(page.text)) | {u[7:].split("?")[0] for u, _ in page.links if u.lower().startswith("mailto:")}
        for mail in found:
            mail = mail.strip().lower().rstrip(".")
            local, _, dom = mail.partition("@")
            if registrable_domain(dom) == domain and local in ROLE_MAILBOXES:
                mails.setdefault(mail, page)
    for mail, page in list(mails.items())[:3]:
        ev = pb.add_evidence(Evidence(page.url, "company_owned", page.snap.retrieved_at, page.snap.sha256, mail, "html_text:email_regex+role_mailbox_filter"))
        pb.add(Claim("contact", "email", mail, [ev], label="Contact e-mail (company domain)", key=f"email:{mail}"))
    if mails:
        pb.set_state("contact", "available", "company role mailbox on verified site", origin)

    # self-description (company-owned promotional copy, labelled as such)
    desc = home.meta.get("description") or home.meta.get("og:description")
    if not desc:
        desc = next((n.get("description") for n in home.jsonld if isinstance(n.get("description"), str)), None)
    if desc and 40 <= len(desc) <= 600 and not any(fold(m) in fold(desc) for m in PARKED_MARKERS):
        ev = pb.add_evidence(Evidence(home.url, "company_owned", home.snap.retrieved_at, home.snap.sha256, desc[:600], "html_meta:description"))
        pb.add(Claim("description", "self_description", desc, [ev], label="Company's own description (promotional, company-owned)", confidence=0.9))
        pb.set_state("description", "available", "meta description on verified site", origin)
    else:
        pb.set_state("description", "not_available", "verified site has no usable description", origin)

    if want_news:
        _news(pb, fetcher, visit, origin)


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    for parser in (lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")), parsedate_to_datetime):
        try:
            dt = parser(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.date().isoformat()
        except (ValueError, TypeError, IndexError):
            continue
    m = re.match(r"(\d{4}-\d{2}-\d{2})", value)
    return m.group(1) if m else None


def _news(pb: ProfileBuilder, fetcher: Fetcher, visit: SiteVisit, origin: str, max_items: int = 8) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=730)).date().isoformat()
    today = datetime.now(timezone.utc).date().isoformat()
    items: list[tuple[str, str, str, Page]] = []  # date, title, url, page

    def from_page(page: Page) -> None:
        for node in page.jsonld:
            typ = str(node.get("@type", ""))
            if any(t in typ for t in ("NewsArticle", "BlogPosting", "Article", "Event")):
                date = _parse_date(node.get("datePublished") or node.get("startDate"))
                title = node.get("headline") or node.get("name")
                if date and title and cutoff <= date <= today:
                    items.append((date, str(title)[:200], str(node.get("url") or page.url), page))
        if page.doc is None:
            return
        for art in page.doc.xpath("//article[.//time[@datetime]]")[:20]:
            t = art.xpath(".//time[@datetime]")[0]
            date = _parse_date(t.get("datetime"))
            head = art.xpath(".//h1|.//h2|.//h3|.//h4")
            title = " ".join(head[0].text_content().split()) if head else ""
            link = art.xpath(".//a[@href]")
            url = urllib.parse.urljoin(page.url, link[0].get("href")) if link else page.url
            if date and title and cutoff <= date <= today and registrable_domain(url) == registrable_domain(origin):
                items.append((date, title[:200], url, page))

    for page in visit.pages:
        from_page(page)
    home = visit.pages[0]
    feeds = [f for f in home.feeds if registrable_domain(f) == registrable_domain(origin) and "comments" not in f]
    try:
        if feeds:
            snap = fetcher.get(feeds[0], phase="web_news", max_bytes=1_500_000)
            if snap.ok:
                try:
                    root = etree.fromstring(snap.body, parser=etree.XMLParser(resolve_entities=False, no_network=True, recover=True))
                except etree.XMLSyntaxError:
                    root = None
                if root is not None:
                    fake = Page(snap)
                    for it in root.iter("{*}item", "{*}entry", "item", "entry"):
                        title = (it.findtext("title") or it.findtext("{*}title") or "").strip()
                        link_el = it.find("link") if it.find("link") is not None else it.find("{*}link")
                        link = (link_el.text or link_el.get("href") or "").strip() if link_el is not None else ""
                        date = _parse_date(it.findtext("pubDate") or it.findtext("{*}published") or it.findtext("{*}updated") or it.findtext("{http://purl.org/dc/elements/1.1/}date"))
                        if title and date and cutoff <= date <= today and (not link or registrable_domain(link) == registrable_domain(origin)):
                            items.append((date, title[:200], link or snap.final_url, fake))
        elif not items:
            news_links = [u for u, txt in home.links if registrable_domain(u) == registrable_domain(origin)
                          and (NEWS_HINTS.search(urllib.parse.urlsplit(u).path) or NEWS_HINTS.search(fold(txt)))]
            if news_links:
                snap = fetcher.get(news_links[0], phase="web_news")
                if snap.ok:
                    page = Page(snap)
                    from_page(page)
    except BudgetExhausted:
        pass
    seen: set[str] = set()
    items.sort(key=lambda x: x[0], reverse=True)
    added = 0
    for date, title, url, page in items:
        key = fold(title)
        if key in seen:
            continue
        seen.add(key)
        ev = pb.add_evidence(Evidence(page.snap.final_url, "company_owned", page.snap.retrieved_at, page.snap.sha256, f"{date} — {title}",
                                      "jsonld/article-time/rss:dated_item", identity_reason="published on the verified official website"))
        pb.add(Claim("activity", "company_news", {"title": title, "url": url, "date": date}, [ev], label="Company news / post (company-owned)",
                     effective_date=date, key=f"news:{key[:80]}"))
        added += 1
        if added >= max_items:
            break


def research_website(pb: ProfileBuilder, fetcher: Fetcher, entity: dict, bulk_row: dict | None, related_orgs: set[str], *,
                     max_candidates: int = 3, want_news: bool = True) -> None:
    legal_name = entity.get("navn") or (bulk_row or {}).get("navn") or ""
    cands = domain_candidates(entity, bulk_row)
    if not cands:
        pb.set_state("website", "not_available", "registry lists no website or company e-mail domain, and no name-based domain resolves")
        for fam in ("social_profiles", "description"):
            pb.set_state(fam, "not_available", "no verified official website to read from")
        return
    decisions = []
    accepted: SiteVisit | None = None
    for candidate, source in cands[:max_candidates]:
        try:
            people = {t for c in pb.family_claims("leadership") for t in name_tokens(str(c.value))}
            visit = visit_site(fetcher, candidate, source, pb.org, entity, legal_name, related_orgs, person_tokens=people)
        except BudgetExhausted:
            decisions.append("budget")
            break
        decisions.append(visit.decision)
        if visit.decision == "accepted":
            accepted = visit
            break
        pb.candidates.append({"family": "website", "candidate": candidate, "source": source, "decision": visit.decision, "reason": visit.reason})
        if visit.decision == "related_site":
            rel_page = visit.pages[0]
            ev = pb.add_evidence(Evidence(rel_page.url, "company_owned", rel_page.snap.retrieved_at, rel_page.snap.sha256,
                                          _span_around(rel_page.text, r"(?i)org") or rel_page.title, "identity_gate:related_site", identity_reason=visit.reason))
            pb.add(Claim("group", "related_website", visit.origin, [ev], label="Website of a related group entity (labelled, not the company's own)",
                         key=f"related_site:{registrable_domain(visit.origin)}", confidence=0.9))
    if accepted:
        try:
            extract_company_owned(pb, fetcher, accepted, legal_name, want_news=want_news)
        except BudgetExhausted:
            pass
        return
    if "budget" in decisions and not any(d in ("ambiguous", "rejected", "related_site") for d in decisions):
        pb.set_state("website", "failed", "request budget exhausted before the website check completed")
    elif any(d in ("ambiguous", "rejected", "related_site") for d in decisions):
        pb.set_state("website", "ambiguous", "candidate site(s) found but none passed the exact-entity identity gate")
    elif "blocked" in decisions:
        pb.set_state("website", "blocked", "robots.txt disallows access to the candidate site")
    else:
        pb.set_state("website", "not_available", "candidate domains were unreachable")
    for fam in ("social_profiles", "description"):
        pb.set_state(fam, "not_available", "no verified official website to read from")
