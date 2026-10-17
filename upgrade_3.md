# Upgrade 3: what is left

> State on 17 Oct 2026, after the upgrade_2 P0 pass (`252a312` on `main`) and the dashboard upgrade (branch `ui-upgrade`, `80411b9` → `c86f4af`).
> **Deadlines:** revised commit hashes until **18 Oct**, round closes **21 Oct**.
> Statuses here come from the code (grep), not from earlier plans. ✅ done · 🟡 partly done · ⬜ not started.

---

## 0. Status at a glance

| Area | Status | Where |
|---|---|---|
| Contract, envelopes, 1,000-profile artifact, hygiene B1–B5, generated metrics (U12) | ✅ | `main` |
| U1 auto-refresh + history archive + `first_seen` | ✅ (`last_seen` / `times_seen` ⬜) | `main` |
| U3 priority lanes for large batches | ✅ (HTTP Range resume for bulk files ⬜) | `main` |
| U4 JSON-LD `identifier`/`taxID` proof | ✅ (other U4 items ⬜) | `main` |
| N1 consistency checks | ✅ | `main` |
| U10 showcase + console upgrade, `DESIGN.md`, jsdom checks | ✅ | **`ui-upgrade` only (not merged)** |
| U9 batch "what changed" digest | ✅ | `ui-upgrade` |
| Everything else in upgrade_2 §4–§5 | ⬜ (details in §3) | |

---

## 1. Decision for today: merge `ui-upgrade` before the 18 Oct cutoff?

UX is worth 5–8 points ("find, compare and verify on desktop and mobile"). The branch doesn't change agent behaviour or `reports/`. However, `signalpost run` calls `build_site()` at the end, so the new `build.py` code now runs inside the one scored command.

**Pre-merge checklist (about 30 min):**
1. Make the site build unable to fail the run: in `cli.py`, wrap `build_site()` in `try/except` and log `[showcase] skipped: <error>`. Envelopes and the run report are already written by then.
2. Clean-machine check at the branch head: fresh `git clone` → `uv sync --frozen` → `uv run --group dev pytest -q` → `uv run signalpost run --organisations eval/smoke-100.jsonl --out out-clean`. Expect 100/100 valid.
3. `node eval/ui_check.cjs "<abs>/out-clean/site"` → `errors: []`.
4. Open the site once in a real desktop browser and once on a phone (or DevTools at 375 px). Check that light and dark both work, that a citation opens the drawer, and the Company/Group chart toggle.
5. Merge, push, and send the new commit hash (you do this).

If any step fails and can't be fixed quickly, don't merge. `main` stays the scored commit.

---

## 2. Open issues found during the UI work

| ID | Issue | Type | Suggested fix |
|---|---|---|---|
| I1 | Brief lowercases names: "Petter-børre furberg is ceo (daglig leder); pål wibe chairs the board" | synthesis (agent) | Keep the registry casing, or title-case each name part including after hyphens. Add a test. |
| I2 | Posten Bring: `group` ended `failed` with "phase budget exhausted: group" in the known-15 run | budget (agent) | Check the group lane's per-phase budget for large groups. A failed family costs coverage. |
| I3 | `eval/benchmark.py` crashes on Windows consoles (cp1252, `≥` character) | eval | `sys.stdout.reconfigure(encoding="utf-8")` at the top of the eval scripts |
| I4 | Kartverket workplace map never tested live (only the offline fallback) | UI | Open a profile with workplaces online, press "Show on map", and check that the CORS response draws points |
| I5 | CSV export and clipboard copy only tested in jsdom | UI | One manual click test in Chrome/Edge/Firefox from `file://` |
| I6 | No check on a real phone (only Chrome at 375 px in an iframe) | UI | Test on one iOS and one Android device: bottom sheet, tap targets, sticky header |
| I7 | `/design-taste-frontend` not applied to the overview hero (its loop needs a real browser inspector) | UI polish | Optional, only if time allows |
| I8 | Re-run one company writes to `out-rerun-<org>/`, which keeps growing | console | Fine locally. Add a "clean up re-runs" action later if needed. |

---

## 3. Remaining backlog (from upgrade_2, re-checked against the code)

### Coverage and precision (agent; scored)
| Item | Left to do | Value |
|---|---|---|
| **U4 website recall** 🟡 | Org number in linked PDFs/terms pages (`/personvern`, `/salgsbetingelser`), `<meta description>`, footer `alt`; NAV `employer.homepage` as a candidate once the ad is verified; JS-shell fallback (Wix/Squarespace `__INITIAL_STATE__`, `wix-warmup-data`); per-source yield ordering | Website is the biggest gap (13–17%). Precision first: every new proof type needs a hand audit. |
| **U6 jobs** ⬜ | ATS boards linked from the verified site (Teamtailor, Jobylon, Webcruiter, ReachMee, Recman, Easycruit), robots-respecting; `og:site_name` brand as a NAV name variant; derived `hiring_signal` claim | Jobs is 0–1% |
| **U7 exact-key sources** ⬜ | Filing events as dated `activity` (diff of `sisteInnsendteAarsregnskap`, 0 extra requests); Mattilsynet smilefjes; DiBK sentral godkjenning; Arbeidstilsynet approvals; Finanstilsynet licences; Doffin (check terms first). Each is a new family with an honest `not_applicable` denominator. | Coverage with zero identity risk |
| **U2 freshness / TTL** ⬜ | `stale_after` per family; reuse fresh facts on refresh (keeping their original retrieval time); report `refetched` vs `reused_fresh` | Update score + budget |
| **U1 history depth** 🟡 | `last_seen`, `times_seen` per claim across all archived runs | Update score |
| **U3 bulk resume** 🟡 | HTTP Range resume so `--bulk-files` survives the ~12 MB drop | Large batches |

### Evidence and reproducibility
| Item | Left to do |
|---|---|
| **U5 evidence vault** ⬜ | Store each company-owned evidence page as `out/snapshots/<sha256>.html.gz`, with `snapshot_path` + `span_start/span_end` on evidence. The drawer highlights from the snapshot. |
| **U11 offline replay** ⬜ | `--replay out/snapshots`: a zero-network re-run that proves determinism |
| **U11 gold-set CI** ⬜ | `eval/gold_websites.jsonl` (~150 hand-labelled decisions from the audits) + `eval/score_gate.py` in CI; any wrong-company decision fails the build |
| **U11 CI on Linux** 🟡 | `.github/workflows/ci.yml` exists (sync + pytest + a run step). Confirm it is green on GitHub after push. |
| **U11 property tests** ⬜ | Malformed inputs (headers, blanks, 8/10 digits, duplicates) still give N envelopes |

### Synthesis
| Item | Left to do |
|---|---|
| **U9 NO/EN brief** ⬜ | Norwegian sentences from the same templates. Today only the UI *labels* switch; the brief stays English. |
| **U9 optional LLM polish** ⬜ | `--llm` (Claude Haiku, key supplied by Builderr), off by default; validator rejects any sentence whose numbers, dates or names aren't in the cited claims; hard cost cap |
| **N2 corroboration badge** ⬜ | Count of independent sources agreeing per fact |
| **N8 peer context** ⬜ | NACE 2-digit medians within the batch (revenue, margin, equity ratio), labelled derived |
| **N9 per-source yield telemetry** ⬜ | Accept/reject rate per candidate source and gate rule in the run report |

### Presentation and outreach
| Item | Left to do |
|---|---|
| **U10 hosting** ⬜ | Publish `out-1000/site` (from `reports/run-1000-envelopes.jsonl.gz`) on GitHub Pages and link it in the README and the email. The site is static and needs no server. |
| **U10 demo video** ⬜ | 2–3 min: run → console → profile → evidence drawer → compare → changes |
| **U8 reviews/sentiment** ⬜ | Ask Builderr whether they will supply a key for a licensed reviews API. Until then the family stays "no permitted source". |

---

## 4. Order of work

| Slot | Work |
|---|---|
| **Today (17 Oct)** | §1 pre-merge checklist → merge `ui-upgrade` if green · I1 name casing + I3 encoding (small, safe) · re-run dev + val, refresh replay, evidence re-verification · regenerate docs (`eval/write_docs.py`) · send the revision |
| **18 Oct (last revision)** | U7 filing events (0 requests) · I2 group budget · one U4 proof type with a hand audit · final revision only if every gate passes |
| **After 18 Oct (outside the scored commit)** | U10 Pages hosting + video · U5/U11 vault, replay, gold-set CI · U6 ATS jobs · U7 sector registers · U9 NO/EN brief · U2 TTL · U8 question to Builderr |

**Release gate for every revision (unchanged):** tests green · dev + val 100/100 valid · 0 wrong-company in a hand audit of new acceptances · refresh replay PASS · evidence re-verification ≥ 98% · 1,000-company run within the limits · plus, if the UI is merged, `ui_check.cjs` → `errors: []`.
