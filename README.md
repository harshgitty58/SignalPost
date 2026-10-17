# Signalpost — evidence-backed Norwegian company profiles

Give it Norwegian organisation numbers; it returns one terminal JSON envelope per company with facts from
permitted public sources. Every fact carries its **source URL, retrieval time, reporting period (where relevant),
content SHA-256, claim span and extraction method**. Re-running it is a **refresh** that emits typed changes, and
every run produces a static **showcase site** where each fact is one tap from its proof.

**Precision first:** anything that cannot be tied to the exact legal entity is returned as `ambiguous` /
`not_available`, never published. Missing values are never turned into zero.

---

## 1. Quick start

You need **git** and **[uv](https://docs.astral.sh/uv/)**. uv installs the pinned Python (3.12) by itself.

**Windows (PowerShell)**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # once, then reopen PowerShell
git clone https://github.com/harshgitty58/SignalPost.git
cd SignalPost
uv sync --frozen
uv run signalpost run --organisations eval/known-15.jsonl --out out-ui --job-days 7   # ~1 min, 12 well-known companies
start out-ui\site\index.html                                                          # open the showcase
```

**macOS / Linux**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh                                       # once
git clone https://github.com/harshgitty58/SignalPost.git && cd SignalPost
uv sync --frozen
uv run signalpost run --organisations eval/known-15.jsonl --out out-ui --job-days 7
open out-ui/site/index.html        # Linux: xdg-open out-ui/site/index.html
```

Your own batch: any JSONL (`{"organisation_number": "923609016"}` per line), JSON list, or plain text with one
number per line works as `--organisations`.

---

## 2. Launch the dashboard (backend + UI)

The dashboard is two pages served by one small local backend:

| Page | URL | What it is |
|---|---|---|
| **Live console** | http://127.0.0.1:8765 | Run the agent, tests, benchmark, evidence check, refresh replay; live terminal, budget meters, per-company "why" |
| **Showcase** | http://127.0.0.1:8765/files/out-ui/site/index.html | The profiles of a run (replace `out-ui` with any `out-<name>` folder) |

**Start it in your own PowerShell** (this window *is* the backend; keep it open):
```powershell
cd "<path to>\SignalPost"
uv run --group dev signalpost serve              # add --port 8780 if 8765 is taken
```
Then open the URLs above (`start http://127.0.0.1:8765` opens the console). Press **Ctrl+C** in that PowerShell
window to stop the backend.

### Connecting the UI's terminal to your PowerShell
The showcase home page has a **"Run it locally"** panel with the setup steps and an embedded **PowerShell-style
terminal** underneath:

1. Start the backend in your PowerShell as above.
2. Open the showcase **through the backend** (`http://127.0.0.1:8765/files/out-ui/site/index.html`), not from disk.
   The terminal header turns green: *connected to the local backend*.
3. Press **▶ Run** on a step, or type one of the commands at the `PS …\SignalPost>` prompt. The backend that runs
   in your PowerShell window executes it in your checkout and streams the output into the page.
   **Ctrl+C** (or *Stop*) ends a running job, `cls` clears, `help` lists the commands.

Commands the terminal accepts (everything else is refused, by design; a web page must not be able to run
arbitrary commands on your machine):
```text
uv run signalpost run --organisations eval/<batch>.jsonl --out out-<name> [--job-days N]
uv run --group dev pytest -q
uv run python eval/benchmark.py out-<name>
start out-<name>/site/index.html            (opens that run's showcase in a new tab)
```
Opened straight from disk (`file://`), the panel still shows the steps with copy buttons and tells you how to start
the backend.

---

## 3. Command reference

| Task | Command |
|---|---|
| Install (pinned, exact) | `uv sync --frozen` |
| Run a batch | `uv run signalpost run --organisations <batch> --out out-<name>` |
| Refresh (typed changes vs the last run) | run again into the **same** `--out` (the last run is archived to `out-<name>/history/`) |
| Force a baseline / diff against a specific run | `--fresh` / `--previous out-<other>` |
| Registry only (no websites) | `--no-web` |
| NAV job look-back window | `--job-days 7` (default 60) |
| Limits (defaults = official limits) | `--max-requests 2000 --max-minutes 45 --max-cost 10` |
| Rebuild a run's showcase | `uv run signalpost showcase --envelopes out-x/envelopes.jsonl --report out-x/run-report.json --output out-x/site` |
| Draw a random test batch from a universe file | `uv run signalpost select --universe data/signalpost-universe.jsonl.gz --count 100 --output batch.jsonl` |
| Live console | `uv run --group dev signalpost serve [--port 8765]` |
| Unit tests | `uv run --group dev pytest -q` |
| Benchmark (coverage, 95% Wilson intervals, abstentions) | `uv run python eval/benchmark.py out-x [out-y]` |
| Re-verify evidence at the source (30 samples) | `uv run python eval/verify_evidence.py out-x/envelopes.jsonl --sample 30` |
| Refresh replay (idempotency, typed changes, carry-forward) | `uv run python eval/refresh_replay.py out-x/envelopes.jsonl out-x/refresh-replay.json` |
| Write measured numbers into README/SUBMISSION | `uv run python eval/write_docs.py` |
| Headless UI checks (optional, needs Node) | `npm install --no-save jsdom@24.1.3` → `node eval/ui_check.cjs "<abs path>\out-x\site"` · `node eval/console_check.cjs http://127.0.0.1:8765` |

**Outputs** in `out-<name>/`: `envelopes.jsonl` (one per input, input order), `run-report.json` (validation,
coverage, identity gate per source, requests by host and phase, p50/p95, cost), `identity-audit.md`, `site/`
(showcase), `history/` (archived previous runs).

---

## 4. The two UIs

**Showcase** (`out-*/site/index.html`; works from disk, no CDN, no web fonts). Light glass theme (dark on the
toggle), NO/EN interface and summary, 375 px mobile layout, keyboard shortcuts (`/` search, `Esc` close,
`g o/c/h/x/m` switch view, `?` list).
* **Overview:** search with suggestions, a real published fact with its proof, the *Run it locally* terminal, a
  portfolio (availability donut, revenue histogram, industries, counties), a trust panel (evidence completeness,
  abstentions, re-verification, identity-gate decisions, correct rejections), coverage per family with 95%
  Wilson intervals, what changed, run budget.
* **Companies:** sortable table (cards on mobile), filters (family state, legal form, county, website, jobs,
  changed since) kept in the URL, pagination for 1,000+ companies, CSV export.
* **Profile:** org.nr copy, completeness ring, cited summary (English and Norwegian), signals and data checks,
  sections 1–7, account charts (company / group) with exact values, filing history with official PDFs, roles,
  workplaces (optional Kartverket map), jobs, activity, changes with `first_seen` / `times_seen`, unknowns,
  identity audit. Print-friendly.
* **Evidence drawer:** source class, URL, retrieval time, period, method, identity reason, licence, highlighted
  span, full SHA-256 with copy.
* **Compare** (up to four, shareable URL, side-by-side charts; different currencies are never drawn on one
  scale), **Changes** (typed, material/minor) and **Method** (pipeline, gate, states, sources and licences).

**Live console** (`signalpost serve`). Terminal with phase tags, level filters, search and copy; live per-family
coverage bars; budget meters with a requests-over-time sparkline and warning states; per-company "why" dialog with
identity-gate decisions and *Re-run this company*; benchmark tables; evidence re-verification saved for the
showcase; *Diff two runs* (or archived snapshots) using the agent's own change detection.

**Hosting:** `.github/workflows/pages.yml` publishes the showcase of the committed 1,000-profile run to GitHub
Pages on every push to `main` (one-time: Settings → Pages → Source: *GitHub Actions*).

Design system for both UIs: [`DESIGN.md`](DESIGN.md).

---

## 5. What it collects

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
Published only with: (1) the exact org.nr printed on the site (not merely among several companies' numbers), or
(2) the company's registered e-mail domain is the site's domain **and** the legal name is in its identity fields,
or (3) legal name in the site's identity fields **and** registry phone/street address on the site (.no), or (4) the
registry (or the Wikidata item carrying the org.nr) declares the site **and** its title/site-name carries the full
legal name. The evidence names which rule and which source proved it. Held back: parked pages, cross-domain
redirects without org.nr, address-like names, holding/investment company names without org.nr, names that are only
a role holder's surname, and sites showing another org.nr (labelled as `related_website` when it is a group entity).

### Budget
Requests are planned per phase; in large batches exact-key official lookups come first. Requests a phase leaves
unused are spent in a final *tail pass* on families that failed only for budget (still within the global cap).

## 6. Models, APIs, cost
* No LLM, no paid API, no API keys. **Third-party cost per official run: $0.00.**
* NAV feed uses NAV's published public token (override with `NAV_FEED_TOKEN`).

## 7. Measured results (generated from `reports/` by `eval/write_docs.py`)
<!-- metrics:start -->
- **100 random companies (smoke test)** (dev-rev18f @ `318dd62b4ff9`): 100/100 valid envelopes (validation passed), 899 requests, 4.1 min, $0.00. Coverage: identity 100%, status 100%, industry 100%, financials 100%, leadership 100%, locations 78%, group 5%, website 17%, social_profiles 8%, contact 31%, description 9%, jobs 0%, activity 100%.
- **1,000 random companies (official limits)** (run-1000-rev18b @ `318dd62b4ff9`): 1000/1000 valid envelopes (validation passed), 1920 requests, 2.9 min, $0.00. Coverage: identity 100%, status 100%, industry 100%, financials 100%, leadership 37%, locations 28%, group 5%, website 0%, social_profiles 0%, contact 17%, description 0%, jobs 0%, activity 100%.
<!-- metrics:end -->

Evidence for these numbers is committed in [`reports/`](reports): envelopes (gz), run reports, `benchmark.md`,
`identity-audit.md`, `refresh-replay.json`.

---

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| `uv` is not recognised | Reopen PowerShell after installing uv (or run `$env:Path += ";$HOME\.local\bin"`) |
| Port 8765 already in use | `uv run --group dev signalpost serve --port 8780`, then use that port in the URLs |
| The page's terminal says *backend not running* | The page was opened from disk; open it via `http://127.0.0.1:8765/files/out-<name>/site/index.html` |
| A job is already running (console) | Wait for it, or press *Stop* / Ctrl+C in the page's terminal |
| You want a clean run instead of a refresh | add `--fresh` |

## 9. Repository layout
```text
src/signalpost/      agent: cli, pipeline, registry, web (identity gate), jobs, refresh, synthesis, budget, http
  showcase/          static site builder + template (overview, companies, profile, compare, changes, method)
  console/           local live console (server + page)
eval/                frozen batches (smoke-100 = dev, val-100, batch-1000, known-15), benchmark, evidence check, refresh replay, UI checks
reports/             committed evidence for the published numbers
tests/               unit tests
docs/dev/            planning, audits and benchmark policy (development history)
```
Policies: [SOURCES.md](SOURCES.md) (source rights, licences) · [SECURITY.md](SECURITY.md) (outbound URL policy,
console) · [SUBMISSION.md](SUBMISSION.md) (submission pack) · [docs/dev/benchmark_plan.md](docs/dev/benchmark_plan.md)
(honest-benchmark rules) · [LICENSE](LICENSE) (MIT).
