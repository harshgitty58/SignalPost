# Signalpost — evidence-backed Norwegian company profiles

Give it Norwegian organisation numbers; it returns one terminal JSON envelope per company with
facts from permitted public sources. Every fact carries its **source URL, retrieval time, reporting
period, content SHA-256, claim span and extraction method**. It re-runs as a **refresh** that emits
typed changes, and it generates a static **showcase site** where every fact is one tap from its proof.

**Precision first:** anything that cannot be tied to the exact legal entity is returned as
`ambiguous` / `not_available`, never published. Missing values are never converted to zero.

## Run it (one command)

```bash
uv sync --frozen
uv run signalpost run --organisations <batch.jsonl> --out out/ [--previous <previous_out>/]
```

* `--organisations`: JSONL (`{"organisation_number": "..."}` per line), JSON list, or plain text.
* `--previous`: previous output directory → refresh mode (typed changes, carried-forward evidence).
* `--bulk`: optional frozen Brreg snapshot (CSV/JSON, gz ok) used as identity fallback.
* Defaults enforce the official limits: `--max-requests 2000 --max-minutes 45 --max-cost 10`.

Outputs in `out/`: `envelopes.jsonl` (one per input, input order), `run-report.json`
(validation, coverage, requests by host/phase, p50/p95, cost), `site/index.html` (showcase; open directly).

Local test batch: `uv run signalpost select --universe signalpost-universe.jsonl.gz --count 100 --output batch.jsonl`.
Tests: `uv run --group dev pytest -q`.

## What it collects

| Family | Source | Identity |
|---|---|---|
| identity, status, industry, group membership | Enhetsregisteret (live, 100 orgs/request) | org.nr key |
| annual accounts (company + group, up to 3 years, currency, period, audit) | Regnskapsregisteret | org.nr key |
| leadership & roles (no birth dates) | Brreg roles API | org.nr key |
| registered workplaces | Brreg sub-units (`overordnetEnhet`) | org.nr key |
| group structure (labelled, never merged) | Brreg konsernstruktur | org.nr key |
| dated activity | Brreg change log (`oppdateringer`, field-level, dated) + verified-site news/RSS | org.nr key / verified site |
| official website | registry site, registry e-mail domain, `<name>.no` → **identity gate** | see below |
| social profiles, role e-mail, self-description | outbound links / text on the verified site only | verified site |
| active job postings | NAV pam-stilling-feed | ad `employer.orgnr` ∈ {company, its sub-units} |

### Identity gate (website)
Published only with: (1) the exact org.nr printed on the site (not merely among several companies'
numbers), or (2) legal name in the site's identity fields **and** registry phone/street address on the
site (.no), or (3) the registry declares the site **and** its title/site-name carries the full legal name.
Held back: parked pages, cross-domain redirects without org.nr, address-like names, holding/investment
company names without org.nr, names that are only a role holder's surname, and sites showing another
org.nr (labelled as `related_website` when it is a group entity).

## Models, APIs, cost
* No LLM, no paid API, no API keys. **Third-party cost per official run: $0.00.**
* NAV feed uses NAV's published public token (override with `NAV_FEED_TOKEN`).
* Typical 100-company run: ~1.5–3 min, ~650 requests (see `reports/`).

See [SOURCES.md](SOURCES.md) for source rights and [SECURITY.md](SECURITY.md) for the outbound URL policy.
