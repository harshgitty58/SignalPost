# Submission pack — Builderr "Signalpost" challenge

Repository: https://github.com/harshgitty58/SignalPost (branch `main`) · The email to send: [SUBMISSION_EMAIL.md](SUBMISSION_EMAIL.md)

## 1. Requirements checklist

Status as of the commit that contains this file. Numbers come from the committed `reports/` (see §3), not from
estimates.

### What to build
| Requirement | Status | Where it is shown |
|---|---|---|
| Take a Norwegian organisation number, search permitted public sources | ✅ | `uv run signalpost run --organisations <batch> --out out/`; sources and licences in [SOURCES.md](SOURCES.md) |
| Return company facts, source links and dates | ✅ | every claim has source URL, retrieval time, reporting period (where relevant), content SHA-256, claim span, extraction method; `reports/*-envelopes.jsonl.gz` |
| Each fact belongs to the right company | ✅ | exact org.nr keys for registry data; website identity gate with stated proof per site; no wrong-company publication in the hand audits ([reports/identity-audit.md](reports/identity-audit.md), [docs/dev/audit_3.md](docs/dev/audit_3.md)) |
| Keep profiles current | ✅ | re-running into the same output folder is a refresh: typed, material/minor changes, `first_seen` / `last_seen` / `times_seen`, unreadable sources carried forward; [reports/refresh-replay.json](reports/refresh-replay.json) = PASS |

### What to submit
| Requirement | Status | Where it is shown |
|---|---|---|
| At least 1,000 company profiles | ✅ | `reports/run-1000-envelopes.jsonl.gz` (1,000/1,000 valid) + `reports/run-1000-run-report.json`; browsable at https://harshgitty58.github.io/SignalPost/ |
| Repository link | ✅ | https://github.com/harshgitty58/SignalPost |
| Exact commit hash | ✅ at send time | `git rev-parse HEAD` after `git push origin main` (§2) |
| One command to run it | ✅ | `uv sync --frozen` then `uv run signalpost run --organisations <batch.jsonl> --out out/` |
| Model / API details | ✅ | no LLM; Brønnøysundregistrene open APIs (NLOD 2.0), NAV pam-stilling-feed (public token), Wikidata SPARQL (CC0, website candidates only), company-owned websites (robots.txt honoured) |
| Expected run costs | ✅ | **$0.00** third-party cost per run (no paid API, no API keys) |

### How it is tested and scored
| Item | Status | Evidence |
|---|---|---|
| Daily limits: 45 min, 2,000 requests, $10 | ✅ | defaults enforce them (`--max-minutes 45 --max-requests 2000 --max-cost 10`); 100 companies use about 900 requests and about 4 min, 1,000 companies about 1,920 requests and about 3 min, $0 |
| Exactly one terminal envelope per input, every run completes | ✅ | contract validation in every run report; watchdog + fallback envelope; malformed inputs tested |
| Clean-machine install | ✅ | `uv sync --frozen` from a fresh clone; GitHub Actions `clean-machine` workflow runs tests + a live smoke on every push |
| Find useful information (35) | ⚠️ partly | registry families about 100%, filing history, leadership and workplaces strong; websites 17% at 100 companies (only about 11% of companies list one), jobs about 0–1%. The pooled reference set is not visible to us, so the coverage score cannot be predicted |
| Match it correctly with evidence (30) | ✅ | 100% evidence completeness; 30/30 sampled sources re-found at the source; abstentions (`ambiguous`) reported, never published |
| Update correctly (20) | ✅ | refresh replay PASS: idempotent rerun with zero false changes, typed changes, carry-forward |
| Useful explanations (10) | ✅ | deterministic summary in English and Norwegian where every sentence cites its claims; signals, data checks, unknowns with reasons |
| Easy to use (5) | ✅ | static showcase (find, compare, verify; desktop + mobile; NO/EN) and a local live console; see the README |
| Qualify: ≥ 65/100 overall, ≥ 21/35 coverage | ⚠️ unknown until scored | precision, evidence and update are strong; coverage is the risk |
| No material wrong-company publication, no fabricated financial value | ✅ | identity gate + hand audits; financial values copied verbatim from Regnskapsregisteret with unit and period, missing values stay missing |
| JBOX bonus | — | not claimed (the agent was not built with JBOX) |

## 2. Send it
```powershell
git checkout main
git push origin main
git rev-parse HEAD                                   # the exact commit hash
git archive --format=zip -o signalpost-code.zip HEAD # the code at that commit (about 9 MB), to attach
```
Check that `https://github.com/harshgitty58/SignalPost/commit/<sha>` opens and the `clean-machine` workflow is green,
then send [SUBMISSION_EMAIL.md](SUBMISSION_EMAIL.md) to **submit@builderr.ai** with the hash filled in and the zip
attached. Form field: `https://github.com/harshgitty58/SignalPost/commit/<40-char-sha>`.

## 3. Measured (generated from `reports/` by `eval/write_docs.py`)
<!-- metrics:start -->
- **100 random companies (smoke test)** (dev-rev18f @ `318dd62b4ff9`): 100/100 valid envelopes (validation passed), 899 requests, 4.1 min, $0.00. Coverage: identity 100%, status 100%, industry 100%, financials 100%, leadership 100%, locations 78%, group 5%, website 17%, social_profiles 8%, contact 31%, description 9%, jobs 0%, activity 100%.
- **1,000 random companies (official limits)** (run-1000-rev18b @ `318dd62b4ff9`): 1000/1000 valid envelopes (validation passed), 1920 requests, 2.9 min, $0.00. Coverage: identity 100%, status 100%, industry 100%, financials 100%, leadership 37%, locations 28%, group 5%, website 0%, social_profiles 0%, contact 17%, description 0%, jobs 0%, activity 100%.
<!-- metrics:end -->
1,000 profiles: `reports/run-1000-envelopes.jsonl.gz` (+ run report) · Smoke test: `reports/smoke-100-run-report.json` +
`reports/smoke-100-envelopes.jsonl.gz` · Benchmark with 95% intervals: `reports/benchmark.md` · Identity audit:
`reports/identity-audit.md` · Refresh proof: `reports/refresh-replay.json` · Source rights: [SOURCES.md](SOURCES.md) ·
Security / URL policy: [SECURITY.md](SECURITY.md)

## 4. Before every revision
```bash
uv run --group dev pytest -q
uv run signalpost run --organisations eval/smoke-100.jsonl --out out-check
uv run python eval/refresh_replay.py out-check/envelopes.jsonl reports/refresh-replay.json
uv run python eval/verify_evidence.py out-check/envelopes.jsonl --sample 30
# review out-check/identity-audit.md: every published website must be the exact company
```
Revisions close **18 Oct**; send the new commit hash by email each time (max 4 revisions).
