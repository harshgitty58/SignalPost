# Upgrade 2: requirements audit, gaps and next-iteration upgrades

> Audit of the repo at `2dcf705` (17 Oct) against the official requirements: the pasted brief, the challenge page, the evaluation contract, the source policy, the playbook and the starter `OUTPUT_CONTRACT.md`.
> Method: full file inventory, doc-vs-measurement check, a **fresh `git clone` → `uv sync --frozen` → tests → run** (passed), and the dev/val benchmark outputs.
> **Deadline:** revisions close **18 Oct**. Section 3 (P0) is what must ship in the next commit.

---

## 0. Status (17 Oct, after the upgrade_2 P0 pass)
| Item | Status |
|---|---|
| Push + submit | ✅ pushed (form + email by you) |
| R11 1,000 profiles | ✅ `reports/run-1000-envelopes.jsonl.gz` (1,000/1,000 valid, 1,795 requests, 2.1 min) |
| B1 stray files, B3 CSV header, B4 LICENSE, B5 README, B2/U12 metrics generated from reports | ✅ |
| U1 auto-refresh + history archive + `first_seen` | ✅ second run into the same `--out` → refresh mode, 0 false changes |
| U3 large-batch priorities | ✅ leadership 17% → 32%, workplaces 13% → 22% at 1,000 companies (request cap is the binding limit) |
| U4 JSON-LD `identifier`/`taxID` as org-number context | ✅ |
| N1 consistency checks (balance sheet identity, employees vs workplaces) | ✅ in brief + showcase |
| Next | U5 evidence vault, U6 ATS jobs, U7 sector registers, U9 NO/EN, U10 hosting, U11 gold-set CI |

## 1. Requirements compliance matrix

| # | Requirement (source) | Status | Evidence / gap |
|---|---|---|---|
| R1 | Input: Norwegian org numbers, batch read at run time (brief, playbook) | ✅ | `--organisations` JSONL/JSON/TXT; never builds its own list |
| R2 | **Exactly one terminal envelope per input** (contract) | ✅ / ⚠️ | Guaranteed incl. crashes (fallback envelope + hard watchdog). ⚠️ A CSV **header line** becomes a bogus input (see B3). Duplicates are de-duplicated (one envelope per distinct org number). |
| R3 | Six availability states, missing ≠ zero (contract) | ✅ | Per family + explicit absent-family claims; empty values never published |
| R4 | Claim = source URL, retrieval time, reporting period, content hash, extraction method (source policy) | ✅ | Validator: 0 incomplete references (`reports/benchmark.md`) |
| R5 | Precise location in a preserved, immutable snapshot (playbook §6) | ⚠️ | Hash + span text kept, but **raw snapshot bodies aren't stored** and there are no character offsets (→ U5 Evidence vault) |
| R6 | Exact-entity identity, parent/brand/franchise labelled not merged (source policy) | ✅ | Identity gate + `related_website`; 0 wrong in hand audit (17 + 13 sites) |
| R7 | Idempotent refresh, prior evidence preserved, material changes exposed (contract) | ✅ / ⚠️ | `--previous`, typed + material changes, carry-forward, replay PASS. ⚠️ Refresh needs an explicit flag; history covers only one previous run (→ U1, U2) |
| R8 | One command, pinned deps, clean-machine install (contract) | ✅ | Verified via fresh clone + `uv sync --frozen`. CI workflow exists but **has never run** (no remote yet) |
| R9 | Budget: 45 min / 2,000 requests / $10 (form) | ✅ / ⚠️ | 100 cos: 899 req, 4.2 min. 1,000 cos: valid, but roles/workplaces only ~17% (→ U3) |
| R10 | 100-company smoke-test result in repo (brief) | ✅ | `reports/smoke-100-*` |
| R11 | **At least 1,000 company profiles** (form) | ❌ | Only an older 1,000-company run, uncommitted (50 MB, v1 code). Need a v3 run committed compressed (→ P0-2) |
| R12 | Repo link + **exact commit hash** (form) | ❌ | **Not pushed yet**, no remote |
| R13 | Model/API details, licences, expected cost (form) | ✅ / ⚠️ | README/SOURCES/SUBMISSION. ⚠️ Numbers in SUBMISSION/README are outdated (~750 req/1.5 min → now ~900 req/4.2 min). **No LICENSE file** |
| R14 | Source rights, server-side secrets, safe URL handling, declared caches (contract) | ✅ | SOURCES.md, SECURITY.md, URL policy in `http.py`, no caches |
| R15 | Required profile sections 1–7 (brief) | ✅ | All seven sections exist in the envelope + showcase |
| R16 | Synthesis: what it does, what changed, unknowns, with sources (scoring) | ✅ | Cited brief + signals + ranked unknowns. NO/EN not yet (→ U9) |
| R17 | UX: find, compare, verify on desktop + mobile (scoring) | ✅ / ⚠️ | Showcase (overview/explorer/profile/evidence/compare/changes/method) + live console. Not hosted; no charts/map (→ U10) |
| R18 | Coverage vs pooled set (35/50 points; ≥21/35 to qualify) | ⚠️ | Registry families ~100%, website 13–17%, social 5–8%, jobs 0–1%. **This is where we risk the 21/35 coverage gate** (→ U4, U6, U7) |
| R19 | Freeze before daily evaluation; no tuning on hidden batches (harness) | ✅ | Policy in `benchmark_plan.md`; no in-run learning |
| R20 | Ratings/reviews, buzz/sentiment (starter proxy scorer weights them) | ❌ (by choice) | No permitted keyless source identified yet (→ U8 decision) |

---

## 2. Bugs and hygiene found in the scan

| ID | Finding | Fix |
|---|---|---|
| B1 | `my-test.jsonl` and `out-console-server.log` were **committed by accident** | `git rm`, add `*.log` and `my-*.jsonl` to `.gitignore` |
| B2 | SUBMISSION.md / README quote stale numbers (~650–750 requests, ~1.5 min) | Regenerate from `reports/` (single source of truth: write numbers from `run-report.json` automatically, see U12) |
| B3 | Input reader turns a non-numeric line (CSV header `organisation_number`) into an empty-org envelope | Skip lines with no digits; still emit envelopes for malformed *numbers* (as `not_applicable`) |
| B4 | No `LICENSE` | Add MIT (or chosen licence), mention in README |
| B5 | `README` table says accounts "up to 3 years". Filing history now lists every filed year | Update the table row |
| B6 | Filing-history pacing (2.1 s/company, global) dominates runtime (p50 per company 47 s) | Start history requests first, in their own lane, so web work overlaps (U3) |
| B7 | `out-1000` run predates v2/v3 (stale) | Re-run with v3, commit gzipped |
| B8 | The 1,000-company bulk path fails from this network (Brreg drops at ~12 MB) | Range-resume download (U3) or keep it opt-in |

---

## 3. P0: must ship before the 18 Oct revision cutoff

1. **Push + submit** (R12): create the repo, push, form + email with the full commit hash (`SUBMISSION.md`).
2. **1,000-profile artifact** (R11): `signalpost run` on `eval/batch-1000.jsonl` under the official limits → commit `reports/run-1000-envelopes.jsonl.gz` + `reports/run-1000-run-report.json` + the showcase as a release asset / Pages site.
3. **Hygiene** B1–B5 (≈15 min).
4. **U1 Auto-refresh inside the one command** (below): the evaluator may never pass `--previous`, so the update score (20 points) should work with the default command.
5. **U3 Large-batch priorities**, so a 1,000-company official batch still gets roles/workplaces for as many companies as possible.

---

## 4. Upgrades for the next iteration

### U1. Auto-refresh with run history (update score)
- If `--out` already contains `envelopes.jsonl`, treat it as the previous run automatically. Archive it to `out/history/<run_id>.jsonl.gz` before writing the new one.
- `--previous` still overrides; `--fresh` forces a baseline.
- Changes chain across *all* archived runs: `first_seen`, `last_seen`, `times_seen` per claim; a stable `history` block per envelope.

### U2. Freshness model per source (TTL)
- `stale_after` per family: jobs 1 day, activity 1 day, website 30 days, roles 7 days, accounts until the registry's `sisteInnsendteAarsregnskap` changes.
- On refresh, skip still-fresh sources (keeping the evidence) and spend the saved requests on website/jobs discovery. Report `refetched` vs `reused_fresh` per family (still honest: reused facts keep their original retrieval time).

### U3. Large-batch scheduler
- Priority lanes: accounts → roles → workplaces → group → website → news. Each lane takes requests from the budget in order, round-robin across companies. Under 2,000 requests for 1,000 companies, every company gets accounts, then as many roles/workplaces as possible.
- Filing history: its own paced lane started at t=0 (overlaps everything else); disabled for batches over 200 companies.
- Bulk files with **HTTP Range resume** (retry from the last byte), so `--bulk-files` becomes reliable.

### U4. Website recall (largest coverage gap, precision first)
- **More proof types without lowering the bar:**
  - org number inside PDFs/terms pages linked from the site (`/personvern`, `/salgsbetingelser`);
  - `vatID` / `taxID` / `identifier` in JSON-LD;
  - org number in the `<meta name="description">` or footer image `alt`.
- **More candidates:** domains in the registry's `hjemmeside` of *sub-units* (done), parent-owned domains labelled as related (done), domains from **NAV ads** (`employer.homepage`) once an ad is verified by org number.
- **JS-shell fallback:** detect Wix/Squarespace/React shells (empty body, big script). Read their server-side JSON (`window.__INITIAL_STATE__`, `wix-warmup-data`) for the org number before marking "parked".
- Track **per-source yield** (accept rate per candidate source on dev) and order candidates by it. The order is frozen per version.

### U5. Evidence vault (snapshots + offsets): novelty, playbook §6
- Store every company-owned page used as evidence as `out/snapshots/<sha256>.html.gz` (registry JSON is reproducible from the API; optionally store it too).
- Evidence gets a `snapshot_path` and **character offsets** (`span_start`, `span_end`) into the stored body.
- The showcase evidence drawer shows the highlighted excerpt from the stored snapshot. Proof survives even if the site changes.
- Enables **offline replay** (U11).

### U6. Jobs coverage
- Verified-site career pages: JSON-LD `JobPosting` (done), plus links to ATS boards (Teamtailor, Jobylon, Webcruiter, ReachMee, Recman, Easycruit). Fetch only the board page linked from the verified site, robots-respecting.
- A NAV ad's employer org number can be a **sub-unit**. Already handled; extend candidate names with the sub-unit names from bulk/API (done) and **brand names from the verified site** (`og:site_name`).
- Publish `hiring_signal` (count, newest date) as a derived claim.

### U7. More official, exact-key sources (coverage with zero identity risk)
| Source | Families | Notes |
|---|---|---|
| Brreg change log → **filing events** ("2025 accounts filed") | activity | 0 extra requests (diff of `sisteInnsendteAarsregnskap`) |
| **Mattilsynet** smilefjes inspections | activity, licences | food service (2.1% of universe); bulk open data, verify licence |
| **DiBK** sentral godkjenning | licences | construction (7.8%); per-org API, verify terms |
| **Arbeidstilsynet** cleaning/staffing approvals | licences | open register |
| **Finanstilsynet** licence register | licences | finance (3.9%) |
| **Doffin** awards | activity | verify API terms first |
Each new family is added to `FAMILIES`, the showcase and the benchmark, with `not_applicable` for out-of-sector companies (honest denominator).

### U8. Ratings, reviews, buzz and sentiment (decision)
- No keyless, permitted source found yet (Google Places needs a key; Trustpilot/Glassdoor terms forbid scraping). **Ask Builderr** whether they will supply a key for a licensed API (allowed by the rules: "Builderr will supply a model key for scoring if needed").
- Until then these families are explicit `not_applicable`/`not_available` with the reason "no permitted source". Never inferred.
- Company-owned copy is never used as sentiment (source policy).

### U9. Synthesis upgrades
- Norwegian + English brief (template-based, no LLM).
- **Optional LLM polish** (`--llm`, Claude Haiku via `ANTHROPIC_API_KEY` supplied by Builderr): a validator rejects any sentence whose numbers, dates or names aren't in the cited claims. Hard cost cap. Off by default.
- "What changed" digest across the batch (top material changes) at the top of the showcase overview.

### U10. Showcase / UX
- Host the 1,000-profile site (GitHub Pages) and link it in the README + email.
- Financial charts (revenue/result/equity by year), workplace map (Kartverket address API), NO/EN toggle, CSV export, print view, keyboard shortcuts, WCAG AA pass.
- **Trust panel** on the overview: audit result, examples of correct rejections (parent site, address-named, holding company), evidence re-verification rate.
- Live console: "re-run this company" button and a diff view between two runs.

### U11. Reproducibility and testing
- **Offline replay mode** (`--replay out/snapshots`): re-run from stored snapshots with zero network. This proves determinism and idempotency, and makes judge audits possible.
- Gold set: freeze ~150 hand-labelled website decisions (from the audits) → `eval/gold_websites.jsonl` + `eval/score_gate.py` in CI. Any wrong-company decision fails the build.
- Push CI and confirm it runs green on Linux (clean-machine check).
- Property tests: random malformed inputs (headers, blanks, 8/10-digit numbers, duplicates) → still N envelopes.

### U12. Single source of truth for published numbers
- `eval/benchmark.py --write-docs` updates the numbers block in README/SUBMISSION from the latest `reports/*.json`. No hand-typed metrics can drift (fixes B2 permanently).

---

## 5. Logical novelties (differentiators)

| Novelty | What it is | Why it scores |
|---|---|---|
| **N1 Cross-source consistency checks** | Accounting identity (assets = equity + debt, within rounding), employees (registry vs sum of workplace employees), registry phone/address vs site. Results are published as `data_quality` claims (pass/warn), never used to alter values. | Precision + synthesis ("what is unknown/inconsistent"); shows rigour |
| **N2 Corroboration score per fact** | Count of independent sources agreeing (registry + site + NAV), shown as a badge; identity reason chains | Explainability, evidence quality |
| **N3 Evidence vault + offline replay** (U5/U11) | Every proof replayable without network; character offsets into snapshots | Reproducibility, evidence validity, judge trust |
| **N4 Freshness-aware refresh** (U2) | TTL per source, reuse fresh facts, spend requests where change is likely | Update score + coverage within the same budget |
| **N5 Change significance + batch digest** | Material vs minor changes; overview "what changed today" | Update + synthesis + UX |
| **N6 Abstention transparency** | Every held-back candidate published in the audit with reason; ambiguity rate reported next to coverage | Precision story; matches "abstentions reported separately" |
| **N7 Live explainable console** (done) | Watch the agent decide, company by company | UX / demo value |
| **N8 Peer context (derived)** | Industry (NACE 2-digit) medians within the batch: revenue, margin, equity ratio. Labelled derived. | Synthesis usefulness |
| **N9 Per-source yield telemetry** | Accept/reject rates per candidate source and per gate rule in the run report | Honest benchmarking; drives frozen candidate ordering |

---

## 6. Order of work

| Slot | Work |
|---|---|
| **Now → 18 Oct (P0)** | Push + submit v3 · hygiene B1–B5 · U1 auto-refresh · U3 priority lanes · fresh 1,000-profile run committed (gz) · update docs from reports · **send revision** |
| 18 Oct (if time before cutoff) | N1 consistency checks · U4 JSON-LD `vatID`/`identifier` proof · U7 filing events · re-benchmark dev + val · audit · final revision |
| After 18 Oct (outside the scored commit) | U10 hosting, charts, map, video · U5/U11 vault + replay in a branch · U8 Builderr key question · gold-set CI |

**Release gate for every revision:** tests green · dev + val 100/100 valid · 0 wrong-company in a hand audit of new acceptances · refresh replay PASS · evidence re-verification ≥ 98% · 1,000-company run within the limits.
