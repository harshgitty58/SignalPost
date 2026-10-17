# Benchmark plan: raise the scores honestly

**Goal:** raise real, verifiable coverage and quality without inflating the numbers. Every number we
publish (README, email, showcase) must be reproducible from the committed code with one command, on
companies the code was not tuned on.

---

## 1. Ground rules

1. **No tuning on official batches.** Hidden daily batches are never used to change code or thresholds.
2. **No precomputed answers.** No cached profiles, hand-entered values or company lists inside the agent. Every run fetches live.
3. **Frozen, disjoint test sets.** Thresholds are tuned on *dev* only, checked on *val*, and *test* runs once per version. No overlapping organisation numbers.
4. **Precision is measured, not assumed.** Every newly published website/social/job is hand-audited before a version ships. Wrong-company publications must be **0**.
5. **Abstentions are reported, never hidden.** `ambiguous`/`not_available` rates are published next to coverage.
6. **A family is "available" only with a positive fact.** "Not in a group", or a filing-year flag without the accounts, doesn't count as coverage (fixed in v3, see §4).
7. **No cosmetic padding.** No splitting one fact into many claims, no counting search results or registry-declared URLs as verified, no derived numbers without a "derived" label.
8. **Report failures.** Crashes, budget refusals, slow sources and regressions go into the run report and this file.

## 2. Test sets (frozen)

| Set | Size | Seed / source | Use |
|---|---|---|---|
| dev | 100 | `select --seed 20261016` (`eval/smoke-100.jsonl`) | iterate, tune thresholds |
| val | 100 | `select --seed 777 --exclude dev` | confirm a change generalises |
| test | 1,000 | `select --seed 1000 --exclude dev` (`eval/batch-1000.jsonl`) | once per version, official limits |
| known | 12 | large employers (`eval/known-15.jsonl`) | sanity only, never reported as a benchmark |

## 3. Metrics (`eval/benchmark.py` computes all of them from a run directory)

| Metric | Definition |
|---|---|
| Company coverage per family | share of companies whose family state is `available` with ≥1 positive claim |
| Material activity coverage | share with ≥1 activity item that isn't an employee-count update |
| Claims per company | published claims (absent-family entries excluded) |
| Abstention rate | share `ambiguous` per family (identity could not be proven) |
| Website precision | from the hand audit: correct / published (target 100%) |
| Evidence completeness | every published claim has URL, retrieval time, SHA-256, span, method (automated, target 100%) |
| Evidence re-verification | sample N claims, re-fetch the source, check the span still appears (`eval/verify_evidence.py`) |
| Refresh correctness | `eval/refresh_replay.py`: idempotent, typed changes, carry-forward (all must pass) |
| Cost / speed | requests, p50/p95 per company, wall time, $ |
| 95% interval | Wilson interval on every coverage %, so 100-company numbers aren't over-read |

## 4. Where we stand and the honest ceiling

Universe facts (411,160 companies): **85% have 0/unreported employees, and only 10.9% list a website in the registry.**
Real estate (22%) and holding companies dominate. Expect a low ceiling on web/jobs coverage for *every* entrant.
Pooled coverage rewards whoever finds the *existing* facts, and precision decides qualification.

| Family | v2 dev coverage | Honest ceiling estimate | Lever |
|---|---|---|---|
| identity / status / industry | 100% | 100% | — |
| financials (latest) | 100% | ~99% | already |
| **financial history (filing years + official PDFs)** | 0% | **~99%** | **v3: `aarsregnskap/kopi/{org}/aar`** |
| leadership | 100% | ~100% | already (per-company) |
| workplaces | 78% | ~80% | real absence for the rest |
| group relations | ~4% real (was shown as 100%) | ~5% | v3 honesty fix |
| website | 17% | ~20–22% | careful candidate work; precision first |
| social / contact / description | 8% / 31% / 9% | bounded by website | extraction depth on verified sites |
| jobs | 0–1% | ~3–4% | NAV window 60d, careers/ATS links on verified sites |
| activity (material) | measured in v3 | ~60%+ | official change log + filings + news |

## 5. Improvement queue (ordered by honest coverage gain per request)

1. **Filing history** (v3, now): official list of filed years + links to official filing copies. ~1 request per company, paced to the endpoint's ~30/min limit; skipped automatically for large batches.
2. **Honesty fixes** (v3, now): `part_of_group` → identity family; `latest_filed_year` → identity. Group/financials are "available" only with real relations/accounts.
3. **Benchmark tooling** (v3, now): `eval/benchmark.py` (metrics + Wilson CIs) and `eval/verify_evidence.py` (span re-verification).
4. **Filing events in activity:** new filing years appear as dated official activity ("annual accounts for 2025 filed").
5. **Jobs:** 60-day NAV window; JSON-LD `JobPosting` and ATS links (Teamtailor, Jobylon, Webcruiter, ReachMee, Recman) found on verified sites only.
6. **Website extraction depth:** read JSON-LD `sameAs` on sub-pages, footer social icons without text, role mailboxes on contact pages. This raises social/contact *within* verified sites, at no precision cost.
7. **Sector registers by org number** (each ~1–2% of companies, exact key): DiBK central approval (construction), Mattilsynet inspections (food service). Verify licence and terms before use.
8. **Large-batch mode:** resumable (HTTP Range) bulk downloads, so 1,000-company batches keep roles/workplaces.

## 6. Release gate (every version)

```
pytest                                  -> all pass
run dev-100 and val-100                 -> 100% envelopes valid, 0 crashes
eval/benchmark.py dev, val              -> coverage up or equal on BOTH sets (no dev-only gains)
hand audit of NEW websites/socials/jobs -> 0 wrong-company
eval/refresh_replay.py                  -> PASS
eval/verify_evidence.py (sample 50)     -> ≥ 98% spans re-found (drift explained)
run test-1000 under official limits     -> valid, within 45 min / 2,000 requests / $10
```
Publish the benchmark report (`reports/benchmark.md`) with the commit hash, sets, intervals and abstentions.
