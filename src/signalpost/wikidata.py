"""Wikidata (CC0): official website (P856) for entities whose Norwegian org. number (P2333) is in the batch.

One SPARQL request per 100 organisation numbers. Used only as a website *candidate*; the site must still
pass the identity gate before anything is published.
"""
from __future__ import annotations

import json
import urllib.parse

from .budget import BudgetExhausted
from .http import Fetcher

ENDPOINT = "https://query.wikidata.org/sparql"


def websites(fetcher: Fetcher, orgs: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for i in range(0, len(orgs), 100):
        values = " ".join(json.dumps(o) for o in orgs[i:i + 100])
        query = f"SELECT ?org ?site WHERE {{ VALUES ?org {{ {values} }} ?item wdt:P2333 ?org . ?item wdt:P856 ?site . }}"
        url = ENDPOINT + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
        try:
            snap = fetcher.get_json(url, phase="registry", headers={"Accept": "application/sparql-results+json"}, timeout=30)
        except BudgetExhausted:
            break
        if not snap.ok:
            continue
        for row in snap.json().get("results", {}).get("bindings", []):
            out.setdefault(row["org"]["value"], []).append(row["site"]["value"])
    return out
