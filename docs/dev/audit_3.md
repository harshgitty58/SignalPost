# Audit 3: full re-check (17 Oct 2026)

> Scope: git and remote state, clean-machine install, tests, agent output (input handling, identity gate, budget, synthesis), evidence and refresh gates, docs vs reports, source declarations, the showcase, the live console and its server.
> Method: commands run on this machine and a fresh clone, and grep and reading of the code. No numbers below are estimated.
> Branch checked: `ui-upgrade` @ `c86f4af` (= `main` @ `15378ec` + 4 UI commits).

---

## 1. Verified OK

| Check | Result |
|---|---|
| Clean machine: fresh `git clone` (branch `ui-upgrade`) → `uv sync --frozen` → `pytest` → `signalpost run` on `eval/smoke-100.jsonl` | 10 passed · **100/100 valid · 899 requests · 4.0 min · $0**, coverage identical to `reports/smoke-100-run-report.json`, so the published numbers reproduce exactly |
| `uv lock --check` | lockfile in sync |
| Docs vs reports (`eval/write_docs.py`) | README and SUBMISSION metric blocks already match `reports/` |
| Messy input (`organisation_number` header, blank line, `abc`, duplicates incl. `923 609 016`, 8 and 10 digits, bad checksum) | header, blank and `abc` skipped; duplicates collapsed; malformed numbers each get a `not_applicable` envelope with the mod-11 reason; `valid=True` |
| Evidence re-verification (`verify_evidence.py --sample 30`, fresh known-15 run) | **30/30 re-found (100%)**, 0 drift, 0 fetch errors |
| Refresh replay (`refresh_replay.py`) | **PASS**: idempotent rerun, typed changes, carry-forward |
| Showcase headless check (`ui_check.cjs`) | `errors: []` on out-ui, out-dev, out-1000, the clean-machine site, a 21-change fixture, a site without a run report, and a site of invalid-number envelopes |
| Console headless check (`console_check.cjs`) + live 2-company run via `/api/run` + `/api/stream` | `errors: []`; 2/2 valid, 36 requests; invalid org numbers, cross-origin POST and path traversal in `/api/diff` refused |
| CI workflow (`.github/workflows/ci.yml`) | sync → pytest → 5-company live smoke with an envelope-count assertion; looks correct for Linux (never run on GitHub, see A1) |
| Contrast (both themes) | all text pairs ≥ 4.5:1 (computed) |

---

## 2. Findings

Severity: **A** = can cost qualification · **B** = costs points or evidence accuracy · **C** = should fix · **D** = minor or a question.

### A. Critical

| ID | Finding | Evidence | Action |
|---|---|---|---|
| **A1** | **GitHub `main` is at `e1456ae`.** `0a787f5`, `252a312` (v4: auto-refresh, 1,000-profile artifact, LICENSE, generated metrics), `f8b4804`, `15378ec` and the UI branch exist **only on this machine**. If the submitted hash is any of these, the evaluator cannot clone it. | `git fetch` → `main [origin/main: ahead 4]`; `git log origin/main -1` = `e1456ae` | **You:** push, open the commit URL on GitHub to confirm, then send the hash. Do this before any other revision. |

### B. High (agent output; scored)

| ID | Finding | Evidence | Fix |
|---|---|---|---|
| **B1** | The summary **changes sourced names**: `"; ".join(bits).capitalize()` lowercases everything after the first letter, e.g. "Petter-børre furberg is ceo (daglig leder); pål wibe chairs the board." | `synthesis.py:132`; seen in the Posten brief | Uppercase only the first character; add a test |
| **B2** | **Wrong identity reason on evidence.** The "registry declares this website" rule also runs for `wikidata_p856` and `subunit_declared` sources, so 2 published websites say "registry declares" when Wikidata (matched by org number, P2333) supplied them. The decision is sound; the stated reason is false. | `web.py` gate, `source in ("registry_declared","subunit_declared","wikidata_p856")`; out-ui + out-dev: 2 × `wikidata_p856` labelled "registry declares" | Reason text per source ("Wikidata item with this organisation number (P2333) lists this website…") |
| **B3** | **Group cap too small for small or group-heavy batches.** The cap is `int(n*0.35)+2`, which is 6 for 12 companies. In known-15, 11 of 12 are in groups, so DNB, TINE, Posten, Norwegian and Bouvet ended `group: failed`. | `pipeline.py:123`; out-ui availability | In the unscaled plan use `n + n//20 + 2` (only group members spend a request; large-batch scaling is unchanged) |
| **B4** | **Large batches leave budget unused while websites fail.** At 1,000 companies: 1,795 of 2,000 requests and 2.1 of 45 min used. Fixed lane caps strand about 205 requests (accounts 998/1,052, jobs_verify 3/34, activity 20/42, registry 20/32). Meanwhile 962 companies ended `website: failed` ("website phase exhausted"), so website coverage is 0.3%. | `reports/run-1000-run-report.json` | After the per-company pass, give leftover requests to a **tail pass** (roles/workplaces first, then websites) for companies that hit a budget cap. Needs its own benchmark run, so this is a separate, gated change (§3, step 6). |
| **B5** | **Wikidata is not declared as a source.** It is used for website candidates (CC0) but missing from SOURCES.md and README "What it collects". The source policy requires every source and its licence to be declared. | `wikidata.py`; `grep -i wikidata SOURCES.md README.md` → nothing | Add a row to SOURCES.md, README and the showcase Method page |

### C. Should fix

| ID | Finding | Fix |
|---|---|---|
| **C1** | `signalpost run` calls `build_site()` without protection. A UI bug would fail the scored command after the envelopes are written. | `try/except` → `[showcase] skipped: …` |
| **C2** | `agent_version` = `git rev-parse HEAD` with no dirty flag. Both committed reports say `0a787f5` but were produced before 6 source files changed in `252a312`, so provenance is ambiguous. (The clean re-run shows the numbers do reproduce at the current code.) | Append `-dirty` when the tree has uncommitted changes to `src/`; regenerate reports from the clean candidate commit |
| **C3** | Console: `/api/stop` has no Origin check (a cross-site page could stop a job); no `Host` header check (DNS rebinding could read `/api/state` and `/files`). | Same-origin check on every POST; accept only `127.0.0.1` / `localhost` hosts |
| **C4** | Showcase: count facts ("133 registered workplaces", "N active jobs") open the evidence of **one** claim. Lists are cut off (workplaces 30, activity 15, group 12, former names 5) with no way to reach the rest, so some published facts aren't one tap from their evidence. | Count facts open all their claims; "Show all" on every truncated list |
| **C5** | `eval/*.py` crash on Windows consoles (cp1252, `≥` character). | `sys.stdout.reconfigure(encoding="utf-8")` |
| **C6** | Summary grammar: "is a aksjeselskap". | "an" before a vowel |

### D. Minor or questions

| ID | Finding | Action |
|---|---|---|
| D1 | Duplicate lines and non-numeric lines produce fewer envelopes than input lines (one per distinct org number). Fine if the evaluator keys by org number; a risk if it counts rows. | **Ask Builderr**; no code change until answered |
| D2 | `pyproject.toml` declares `llm = ["anthropic"]`, but nothing imports it. | Leave for U9, or remove for clarity |
| D3 | README "Identity gate" lists 3 rules; the code has 4 (e-mail-domain rule) plus Wikidata as a declared source. | Update README |
| D4 | SECURITY.md doesn't describe the live console (localhost bind, whitelist, Origin/Host checks). | Add a section |
| D5 | Overview copy says every fact carries a "reporting period". It does only where one applies. | "and, where relevant, its reporting period" |
| D6 | Not testable here: Kartverket map online, CSV/clipboard in real browsers, real phones. | Manual checks (upgrade_3 I4–I6) |

---

## 3. Execution plan

**Branches:** `ui-upgrade` takes the UI-only fixes. A new branch **`rev-18oct`** (from `ui-upgrade`) takes the agent fixes and the regenerated reports, so it is one complete candidate. Nothing is pushed or merged by Claude.

| Step | Branch | Items | Gate |
|---|---|---|---|
| 1 | `ui-upgrade` | C1, C3, C4, D5 | ui_check + console_check `errors: []`, pytest |
| 2 | `rev-18oct` | B1, B2, B3, C6 + tests | pytest |
| 3 | `rev-18oct` | B5, D3, D4 (docs), C5 (eval encoding), C2 (dirty flag) | — |
| 4 | `rev-18oct` | Clean-machine re-run of smoke-100 + 1,000 → regenerate `reports/` + `write_docs.py` | 100/100 and 1,000/1,000 valid within limits; replay PASS; re-verification ≥ 98%; hand-check any newly accepted website |
| 5 | **you** | A1 push · open the commit on GitHub · send hash | — |
| 6 | separate branch, only if time | B4 tail pass | full benchmark + hand audit before it may enter a revision |
| — | **you** | D1 question to Builderr · D6 manual checks | — |

---

## 4. Execution log (17 Oct)

| Step | Commit | Result |
|---|---|---|
| 1 · UI hardening (C1, C3, C4, D5) | `050afd9` on `ui-upgrade` | Site build can't fail a run; console refuses foreign `Host` (403) and cross-origin POSTs incl. `/api/stop`; count facts open all their claims (Posten: 133 workplaces); "Show all" on every truncated list (68 → 171 rows). ui_check + console_check `errors: []` |
| 2–3 · Agent fixes + docs (B1, B2, B3, B5, C2, C5, C6, D3, D4) | `7389f13` on `rev-18oct` | Names keep their casing ("Petter-Børre Furberg is CEO"); Wikidata-sourced sites say so; known-15 group 50% → 92% (all 11 members); Wikidata + Kartverket declared; `-dirty` version flag; eval scripts work on cp1252 consoles; 3 new tests |
| New finding · empty evidence excerpt | `5dd7bbe` | The name+contact proof quoted nothing when the token was folded ("rorservice" vs "Rørservice"); 1 of 4 sites in the 1,000 run. Now quotes the identity fields. 0 empty excerpts after the fix |
| 6 · Tail pass (B4) | `7fc1331` (branch `tail-pass`), merged `7be8eaa`, test `0fdf60a` | Benchmarked on the 1,000 batch before merging: 124 stranded requests → leadership 320 → 368, workplaces 223 → 275, group +1; all exact-key, no new website acceptances; 1,000/1,000 valid. Smoke-100: idle (no lane runs out) |
| 4 · Reports regenerated | `b9a1779` | Fresh clone of `7be8eaa` → smoke-100 baseline + refresh (100/100, 899 req, 4.0 min, coverage unchanged) and 1,000 (1,000/1,000, 1,920 req = usable cap, 2.9 min, leadership 37%, workplaces 28%). Refresh replay PASS · evidence re-verification 30/30 · 0 empty website excerpts · README/SUBMISSION regenerated · ui_check `errors: []` on both sites |
| Hand audit of new acceptances | — | `norskrorservice.no` (913529979): exact legal name in `<title>`/`og:site_name`, registry phone 22 12 00 01 and address on the site → correct. `dbbil.no` (997783999): JSON-LD name "DB Bil AS", registry phone 38 13 97 00, postcode 4715 → correct. Smoke-100 website set unchanged (17) |

**Candidate for the revision:** branch `rev-18oct` (contains `ui-upgrade`). Tests: 14 passed.

**Still open (yours):** A1 push + confirm the commit on GitHub + send the hash · D1 ask Builderr rows vs distinct org numbers · D6 manual checks (Kartverket map online, CSV/copy in a browser, a real phone).

### 4b. Finishing pass (17 Oct, later)

| Item | Commit | Result |
|---|---|---|
| UI polish: light glass theme, portfolio / profile / compare charts, console sparkline; mixed currencies never drawn on one scale | `0b82c74` | ui_check + console_check `errors: []`; contrast re-checked on the effective glass colour (worst 4.61:1) |
| GitHub Pages workflow for the 1,000-profile showcase; identity audit shipped inside the site | `0b82c74` | local simulation: 1,000 profiles, 62 MB, `errors: []`. **You:** Settings → Pages → Source: GitHub Actions |
| Kartverket map verified live | — | HTTP 200 with `access-control-allow-origin: *`; fields match |
| Norwegian brief (`text_no`), `last_seen` / `times_seen`, gate yield per source, 3 tests | `318dd62` | 17 tests; duplicate-key claims now carry seen-fields (was 2/2,283 missing) |
| Reports regenerated from a clean clone of `318dd62` | this commit | smoke-100 100/100 · 899 req; 1,000: 1,000/1,000 · 1,920 req; replay PASS; re-verification 30/30; 0 claims without seen-fields; 0 sentences without `text_no`; no new website acceptances |
| U7 filing events | not done | registry gives filing years only, no filing date; nothing honest to date an activity item with |
