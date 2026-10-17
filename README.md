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
Run the agent, re-run one company, unit tests, benchmark, evidence re-verification, refresh replay or a site
rebuild from the browser. The terminal streams live with phase tags, level filters (warnings/errors), search and
copy; per-family coverage bars and budget meters (requests / time / cost, warning at 70%, "near limit" at 90%)
update as companies finish. Clicking a company explains *why* every field family ended in its state, including
identity-gate decisions, and offers "Re-run this company". Benchmark output renders as tables; evidence
re-verification results are saved next to the run and appear in its showcase. "Diff two runs" compares any two
runs or archived `history/` snapshots with the agent's own change detection, in memory. Bound to 127.0.0.1,
whitelisted actions only (no arbitrary shell), validated inputs.

## Showcase site (what to look at)

`out-*/site/index.html` opens straight from disk: no server, no CDN, no web fonts. Light glass theme by default (dark on the toggle),
NO/EN interface labels (data stays as sourced), 375 px mobile layout, keyboard shortcuts (`/` search, `Esc`
close, `g o/c/h/x/m` to switch view, `?` for the list).

* **Overview**: search with suggestions, a real published fact with its proof, a trust panel (evidence
  completeness, abstention rate, re-verification result when available, identity-gate decisions, how each
  website was proven, examples of correct rejections), coverage per family with 95% Wilson intervals, a
  "what changed" digest and run budget meters.
* **Companies**: sortable table (cards on mobile), filters for family state, legal form, county, website,
  jobs and changes since a date, all kept in the URL; paginated for 1,000+ companies; CSV export.
* **Profile**: header with org.nr copy, cited summary, signals and data checks, sections 1–7, annual-account
  charts (revenue, result, equity; company vs group) with the exact values in a table, filing history with
  official PDF links, roles, workplaces (optional Kartverket map, off until asked), jobs, activity timeline,
  changes and `first_seen`, unknowns and the identity audit. Print-friendly.
* **Evidence drawer** (bottom sheet on mobile): source class, URL, retrieval time, period, method, identity
  reason, licence, highlighted span and the full SHA-256 with copy.
* **Compare** (up to four, shareable URL, differing rows tinted), **Changes** (typed, material/minor
  filter) and **Method** (pipeline, identity gate, states, sources and licences, budget plan).

**Hosting:** `.github/workflows/pages.yml` builds the showcase for the committed 1,000-profile run on every push to
`main` and publishes it to GitHub Pages (one-time: Settings → Pages → Source: GitHub Actions).

Design tokens and rules for both UIs live in [`DESIGN.md`](DESIGN.md). Headless checks (no browser needed):
`npm install --no-save jsdom@24.1.3`, then `node eval/ui_check.cjs "<abs path to out-x/site>"` and, with the
console running, `node eval/console_check.cjs http://127.0.0.1:8765`. Both must end with `errors: []`.

## What it collects

| Family | Source | Identity |
|---|---|---|
| identity, status, industry, group membership | Enhetsregisteret (live, 100 orgs/request) | org.nr key |
| annual accounts (company + group, latest years returned by the API, currency, period, audit) + full filing history with links to official copies | Regnskapsregisteret | org.nr key |
| leadership & roles (no birth dates) | Brreg roles API | org.nr key |
| registered workplaces | Brreg sub-units (`overordnetEnhet`) | org.nr key |
| group structure (labelled, never merged) | Brreg konsernstruktur | org.nr key |
| dated activity | Brreg change log (`oppdateringer`, field-level, dated) + verified-site news/RSS | org.nr key / verified site |
| official website | registry site (company or workplace), registry e-mail domain, Wikidata P856 matched by org.nr (P2333), `<name>.no` → **identity gate** | see below |
| social profiles, role e-mail, self-description | outbound links / text on the verified site only | verified site |
| active job postings | NAV pam-stilling-feed | ad `employer.orgnr` ∈ {company, its sub-units} |

### Identity gate (website)
Published only with: (1) the exact org.nr printed on the site (not merely among several companies'
numbers), or (2) the company's registered e-mail domain is the site's domain **and** the legal name is in
its identity fields, or (3) legal name in the site's identity fields **and** registry phone/street address on
the site (.no), or (4) the registry (or the Wikidata item carrying the org.nr) declares the site **and** its
title/site-name carries the full legal name. The evidence names which rule and which source proved it.
Held back: parked pages, cross-domain redirects without org.nr, address-like names, holding/investment
company names without org.nr, names that are only a role holder's surname, and sites showing another
org.nr (labelled as `related_website` when it is a group entity).

## Models, APIs, cost
* No LLM, no paid API, no API keys. **Third-party cost per official run: $0.00.**
* NAV feed uses NAV's published public token (override with `NAV_FEED_TOKEN`).

## Measured results (generated from `reports/` by `eval/write_docs.py`)
<!-- metrics:start -->
- **100 random companies (smoke test)** (dev-rev18f @ `318dd62b4ff9`): 100/100 valid envelopes (validation passed), 899 requests, 4.1 min, $0.00. Coverage: identity 100%, status 100%, industry 100%, financials 100%, leadership 100%, locations 78%, group 5%, website 17%, social_profiles 8%, contact 31%, description 9%, jobs 0%, activity 100%.
- **1,000 random companies (official limits)** (run-1000-rev18b @ `318dd62b4ff9`): 1000/1000 valid envelopes (validation passed), 1920 requests, 2.9 min, $0.00. Coverage: identity 100%, status 100%, industry 100%, financials 100%, leadership 37%, locations 28%, group 5%, website 0%, social_profiles 0%, contact 17%, description 0%, jobs 0%, activity 100%.
<!-- metrics:end -->

See [SOURCES.md](SOURCES.md) for source rights and [SECURITY.md](SECURITY.md) for the outbound URL policy.
