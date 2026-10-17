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
* **Refresh is automatic:** re-running into the same `--out` archives the last run to `out/history/` and diffs against it
  (typed, material/minor changes; unreadable sources carried forward; `first_seen` per fact). `--previous` overrides, `--fresh` forces a baseline.
* `--bulk`: optional frozen Brreg snapshot (CSV/JSON, gz ok) used as identity fallback.
* Defaults enforce the official limits: `--max-requests 2000 --max-minutes 45 --max-cost 10`.

Outputs in `out/`: `envelopes.jsonl` (one per input, input order), `run-report.json`
(validation, coverage, requests by host/phase, p50/p95, cost), `site/index.html` (showcase; open directly).

Local test batch: `uv run signalpost select --universe signalpost-universe.jsonl.gz --count 100 --output batch.jsonl`.
Tests: `uv run --group dev pytest -q`.

## Live console (local)

```bash
uv run --group dev signalpost serve      # open http://127.0.0.1:8765
```
Run the agent, unit tests, benchmark, evidence re-verification or refresh replay from the browser. Terminal
output from this machine streams live; each company appears as it finishes, and clicking it explains *why*
every field family ended in its state (including identity-gate decisions). Bound to 127.0.0.1, whitelisted
actions only (no arbitrary shell).

## What it collects

| Family | Source | Identity |
|---|---|---|
| identity, status, industry, group membership | Enhetsregisteret (live, 100 orgs/request) | org.nr key |
| annual accounts (company + group, latest years returned by the API, currency, period, audit) + full filing history with links to official copies | Regnskapsregisteret | org.nr key |
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

## Measured results (generated from `reports/` by `eval/write_docs.py`)
<!-- metrics:start -->
- **100 random companies (smoke test)** (dev-v4b @ `0a787f5fd3f0`): 100/100 valid envelopes (validation passed), 899 requests, 3.9 min, $0.00. Coverage: identity 100%, status 100%, industry 100%, financials 100%, leadership 100%, locations 78%, group 5%, website 17%, social_profiles 8%, contact 31%, description 9%, jobs 0%, activity 100%.
- **1,000 random companies (official limits)** (run-1000-v4 @ `0a787f5fd3f0`): 1000/1000 valid envelopes (validation passed), 1795 requests, 2.1 min, $0.00. Coverage: identity 100%, status 100%, industry 100%, financials 100%, leadership 32%, locations 22%, group 5%, website 0%, social_profiles 0%, contact 17%, description 0%, jobs 0%, activity 100%.
<!-- metrics:end -->

See [SOURCES.md](SOURCES.md) for source rights and [SECURITY.md](SECURITY.md) for the outbound URL policy.
