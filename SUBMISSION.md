# Submission pack

## 1. Push (one time)
Create an **empty public** GitHub repo (e.g. `signalpost`), then:
```bash
git remote add origin https://github.com/<you>/signalpost.git
git push -u origin master
git rev-parse HEAD        # full 40-char commit hash for the form + email
```
Form field: `https://github.com/<you>/signalpost/commit/<40-char-sha>`

## 2. Email to submit@builderr.ai
```
Subject: Signalpost entry — Signalpost Agent — v1 — <short sha>

Agent name: Signalpost Agent
Builder & contact: <name>, harshvdn.2@gmail.com
Repository: https://github.com/<you>/signalpost
Exact commit: <40-char sha>   (https://github.com/<you>/signalpost/commit/<sha>)

Install:  uv sync --frozen
Run:      uv run signalpost run --organisations <batch.jsonl> --out out/ [--previous <previous_out>/]
          (one envelope per input in out/envelopes.jsonl; run report out/run-report.json; showcase out/site/index.html)

Models / APIs / licences:
- Brønnøysundregistrene open APIs: Enhetsregisteret, Regnskapsregisteret, roles, sub-units, konsernstruktur,
  change log (NLOD 2.0)
- NAV pam-stilling-feed (free public API; NAV's published public token, override via NAV_FEED_TOKEN)
- Wikidata SPARQL (CC0) — website candidates only
- Company-owned websites (robots.txt honoured), published only after an exact-entity identity gate
- No LLM, no paid API, no API keys
Expected third-party cost per official run: $0.00

Measured (from the committed reports):
<!-- metrics:start -->
- **100 random companies (smoke test)** (dev-rev18d @ `7be8eaa46f8e`): 100/100 valid envelopes (validation passed), 899 requests, 4.0 min, $0.00. Coverage: identity 100%, status 100%, industry 100%, financials 100%, leadership 100%, locations 78%, group 5%, website 17%, social_profiles 8%, contact 31%, description 9%, jobs 0%, activity 100%.
- **1,000 random companies (official limits)** (run-1000-rev18 @ `7be8eaa46f8e`): 1000/1000 valid envelopes (validation passed), 1920 requests, 2.9 min, $0.00. Coverage: identity 100%, status 100%, industry 100%, financials 100%, leadership 37%, locations 28%, group 5%, website 0%, social_profiles 0%, contact 17%, description 0%, jobs 0%, activity 100%.
<!-- metrics:end -->
1,000 profiles: reports/run-1000-envelopes.jsonl.gz (+ run report)
Smoke test: reports/smoke-100-run-report.json + reports/smoke-100-envelopes.jsonl.gz
Identity audit: reports/identity-audit.md   Refresh proof: reports/refresh-replay.json
Source rights: SOURCES.md   Security / URL policy: SECURITY.md
```

## 3. Before every revision
```bash
uv run --group dev pytest -q
uv run signalpost run --organisations eval/smoke-100.jsonl --out out-check
uv run python eval/refresh_replay.py out-check/envelopes.jsonl reports/refresh-replay.json
# review out-check/identity-audit.md: every published website must be the exact company
```
Revisions close **18 Oct**. Send the new commit hash by email each time (max 4 revisions).
