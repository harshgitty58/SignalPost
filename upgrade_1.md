# Upgrade 1: improvement plan for the next prototype

> Based on v1 (commit `684d1b9`) test runs: 100-company smoke test, 100-company refresh, 12 known large employers, and 1,000 companies under the official limits.
> **Deadline:** revisions close **Sun 18 Oct**. Tier A is for v2 (Sat), Tier B for the final revision (Sun). Tier C is presentation work that can continue after the 18th, because it doesn't touch the scored commit.

---

## 1. Where v1 stands (measured)

| Area | v1 result | Gap |
|---|---|---|
| Execution | 100/100 and 1,000/1,000 valid envelopes. 640 requests / 75 s for 100 companies; 1,721 requests / 3.8 min for 1,000. $0. | 1,000-company run crashed once on a blank field (fixed). Bulk mode is still being verified. |
| Registry families (identity, status, industry, financials, activity) | 100% | Only up to 3 account years; no derived ratios. |
| Leadership / workplaces | 100% / 78% at 100 companies. At 1,000 companies: 17% / 11% (request budget). | Bulk mode (`bulk.py`) should fix this; still being verified. |
| Official website | **17%** (17 accepted, 17 ambiguous, 13 rejected, 11 unreachable/blocked) | Biggest coverage gap. Too few candidates, and some true matches held back as ambiguous. |
| Social / contact / description | 8% / 31% / 9% | All depend on finding the website first. |
| Jobs | 0% on random companies, works on large employers (TINE: 6) | Most small companies don't advertise on NAV; other permitted job sources are unused. |
| Refresh | 0 false changes on an immediate rerun | No proof yet with *real* changes. History stops at one previous run. |
| Precision | 0 wrong in the 17-site audit, after 2 gate fixes found by audit | No frozen gold set, so gate changes aren't regression-tested. |
| Synthesis | Deterministic, every sentence cited | Describes, but doesn't interpret (risk/growth/hiring signals). |
| UX | Overview, explorer, profile, evidence drawer, compare, changes, method; works offline | No charts, no map, no NO/EN toggle, not hosted. |

**Score levers (official weights):** coverage 35–50 points (70% company recall + 30% fact recall per family), precision/evidence 30, refresh 12–20, synthesis 10–12, UX 5–8. Website-dependent families are where pooled coverage is decided, so **website recall is the #1 lever**, as long as precision holds.

---

## 2. Tier A: v2 (Sat 17 Oct), highest score per hour

### A1. Website recall: more candidates (expected website coverage 17% → ~30%)
| # | Change | Why | Request cost |
|---|---|---|---|
| A1.1 | **Sub-unit websites and e-mails** from the sub-unit records (`hjemmeside`, `epostadresse` per workplace) | Many companies register the website on the workplace, not the parent | 0 (already fetched) |
| A1.2 | **Wikidata batch lookup** (P2333 org number → P856 website, plus social IDs P2013/P2003/P4264) | Exact org-number key and CC0. Strong for mid/large companies. | 1 request per 100 companies |
| A1.3 | **More name-based domain guesses**, checked by DNS before any HTTP: `{name}as.no`, without generic words (`bygg`, `service`…), `og`→`-og-`, `.com` for `.no`-less brands | v1 already found `wulffbergas.no` via registry; guesses miss these patterns | DNS only; HTTP only for domains that resolve |
| A1.4 | **Employer website from verified NAV ads** (`employer.homepage` / links in employer description), only when the ad's org number matches | Candidate tied to the exact org number | 0 (ad already fetched) |
| A1.5 | **Probe standard legal pages** (`/kontakt`, `/kontakt-oss`, `/om-oss`, `/personvern`) when the homepage doesn't link them (JS menus) | Many "ambiguous" sites have the org number on an unlinked contact page | +1–2 per ambiguous site |
| A1.6 | **Re-check "parked/empty" verdicts on JS-rendered sites** (Wix/Squarespace/Webflow markers). Read server-rendered JSON blobs before giving up. | Several "parked" rejections may be real sites that render client-side | 0 |

### A2. Website precision: new proof types and stronger guards
- **New proof: e-mail domain + name.** The registry e-mail domain equals the site's domain **and** the legal name is in the site's identity fields. The company's own registered e-mail on that domain is strong evidence.
- **Franchise/chain guard.** If the site is a chain/franchise (many workplaces, "finn butikk", or the site's org number belongs to a different entity), label it `related_website`.
- **Parent-site check.** When the site shows a different org number, look it up in the group structure and label it as the parent/sister site, not a rejection.
- **Gold set + regression test.** Freeze ~150 hand-labelled orgs (website / no website / tricky negatives: holding, franchise, address-named, same-name), store them in `eval/gold_websites.jsonl`, and add `eval/score_gate.py` (precision, recall). Rule: **no gate change merges if wrong-company > 0.**
- Write `reports/identity-audit.md` automatically on every run (accepted sites with proof spans, rejections with reasons). It's also showcase material.

### A3. Output-contract alignment (low effort, protects the evaluator's parser)
- Also emit **absent families as claims** with `availability` ∈ {not_available, ambiguous, blocked, failed, not_applicable}, `value: null`, `evidence_ids: []`, as in the starter's `OUTPUT_CONTRACT.md`. Our current shape keeps availability per family only, and the evaluator may read per-claim availability.
- Add the starter-style `run.terminal_status` per envelope (done) and `operations` per envelope (done). Also copy the run report's `validation.passed` and `emitted_envelopes` names (done). Double-check field names against `OUTPUT_CONTRACT.md` once more.

### A4. Execution hardening
- Confirm the **bulk-mode** 1,000-company run (roles/workplaces from `roller/totalbestand` and the sub-units CSV). If it fails or is slow, fall back to per-company calls with priority ordering.
- **Hard watchdog thread** that writes all envelopes at T−90s even if the main thread is blocked (covers hung sockets and DNS stalls).
- `.python-version` = 3.12 and `uv sync --frozen` in CI on Linux (the clean-machine check).
- `--resume`: reuse the partial checkpoint file after a crash.

---

## 3. Tier B: final revision (Sun 18 Oct)

### B1. Jobs coverage beyond NAV
- **Careers pages on the verified site:** JSON-LD `JobPosting`, plus links to ATS boards found on the site (Teamtailor, Jobylon, Webcruiter, ReachMee, Recman, Easycruit). Only when linked from the verified site, and robots-respecting.
- **NAV window 35 → 60 days** (≈+50 pages) so long-running ads aren't missed. Index ad status changes, not just new ads.
- Publish `hiring_signal` (number of active postings, newest date) as a derived, labelled claim.

### B2. Dated activity / more official registers (by org number, mostly bulk/open data)
| Source | What it adds | Notes |
|---|---|---|
| **Mattilsynet smilefjes** (food inspections, open CSV, org number) | Dated inspections + results for food businesses | 1 bulk request; NLOD |
| **DiBK sentral godkjenning** (construction approvals by org number) | Approval areas, validity dates | Large share of the universe is construction (NACE 41–43) |
| **Arbeidstilsynet** registers (cleaning / staffing approval) | Approval status + date | Open data |
| **Doffin** (public procurement) | Contract awards to the org number | Verify API terms first |
| **Sitemaps** of the verified site (`lastmod` on /nyheter/ URLs) | Dated company news when there is no RSS | +1 request |
| Registry change log | Already in v1; add **filing events** (new `sisteInnsendteAarsregnskap`) and auditor changes as typed events | 0 |

Each one is a new field family or new activity items, so it's coverage in the pooled reference set, with exact org-number identity (no precision risk).

### B3. Refresh (worth up to 20)
- **Real-change proof:** `reports/refresh-replay.json` from a fixture with mutated snapshots (new filing, CEO change, address change, closed job), showing the expected typed changes, 0 false changes, and idempotent reruns. Add it to the pytest suite.
- **History store:** append-only `out/history/` (or SQLite) so changes chain across many runs, not just the last one. Carried-forward claims keep `stale_since`, and evidence from every past run stays resolvable.
- **Change significance:** `material` (CEO/board change, new filing, status flag, address, website) vs `minor` (employee-count drift). The brief highlights only material changes.
- **Cheaper refreshes:** skip re-fetching the accounts when the registry's `sisteInnsendteAarsregnskap` hasn't changed; use conditional requests (ETag/If-Modified-Since). The saved requests go to website discovery.

### B4. Synthesis (10–12)
- **Signals section** (derived, labelled, each cited): revenue growth, operating margin, equity ratio, **negative equity**, consecutive losses, auditor change, late or missing filing, new board, hiring activity, recent address move.
- **Unknowns ranked by importance** (no website / no accounts first).
- **Optional LLM polish** (`--llm`, Claude Haiku via `ANTHROPIC_API_KEY`, off by default). A validator rejects any sentence whose numbers, dates or names aren't in the cited claims. Hard cost cap in code. Declare the model and expected cost in the submission.
- Norwegian + English brief (template-based, no LLM needed).

---

## 4. Tier C: showcase and UX (can continue after 18 Oct, outside the scored commit)

| # | Upgrade | Value |
|---|---|---|
| C1 | **Host the 1,000-profile site** on GitHub Pages; link it in the README and the email | Judges can click through |
| C2 | Financial **mini-charts** (revenue / result / equity by year) and an equity-ratio gauge | Quick to read |
| C3 | **Map of registered workplaces** (Kartverket address API, open) | Visual |
| C4 | Overview **"trust panel"**: wrong-company audit result, rejected-candidate examples (parent site, address-named, holding company) | Tells the precision story |
| C5 | NO/EN language toggle, print-friendly profile, CSV export from the explorer, keyboard shortcuts (`/` search, `e` evidence) | UX points |
| C6 | **Live lookup mode** (`signalpost serve`): enter an org number and watch each source and gate decision stream in | Demo video centrepiece |
| C7 | Accessibility pass (WCAG AA contrast, focus order, screen-reader labels on state chips) | UX points, mobile |
| C8 | 2–3 minute **demo video** + README hero GIF + metrics table | Gallery + community vote |

---

## 5. Measurement loop (do this before every revision)

1. `signalpost run` on a frozen **dev 100** (fixed seed) and a non-overlapping **validation 100**.
2. `eval/score_local.py` → per-family coverage, gate precision on the gold set, requests, p95, false-change rate.
3. Hand-audit every *newly* accepted website/social/job (diff against the previous version's output).
4. Promote only if: wrong-company = 0, every claim has evidence, coverage ↑, budget OK.
5. Commit, push, then email + form with the new commit hash.

---

## 6. Open questions to resolve (Discord / inquiries@builderr.ai)
1. Official batch size and scoring weights for daily runs (100 vs 1,000; 35/30/20/10/5 vs 50/30/12/8).
2. Does the evaluator pass a frozen registry snapshot path, and under what flag name?
3. Is NAV's published public token acceptable, given it isn't a personal credential?
4. Does a bulk download count as one outbound request?
5. Exact revision cutoff time on 18 Oct.

---

## 7. Suggested order of work

| When | Do |
|---|---|
| Sat morning | A4 (bulk verify, watchdog), A3 (absent-family claims), A1.1–A1.3 |
| Sat afternoon | A1.4–A1.6, A2 (new proof + gold set + audit report), then measure → **submit v2** |
| Sun morning | B3 refresh-replay proof + history, B4 signals, B1 careers/ATS, B2 smilefjes + DiBK, then measure → **final revision before cutoff** |
| Sun pm → Wed | Tier C (host the site, video, README, LinkedIn post for the community vote) |
