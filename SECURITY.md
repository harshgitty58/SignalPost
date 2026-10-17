# Security and outbound URL policy

* **Secrets:** none required. Optional `NAV_FEED_TOKEN` env var only. Nothing secret is written to outputs or logs.
* **Outbound URLs** (`src/signalpost/http.py`): `http`/`https` only; no credentials in URLs; no raw-IP hosts;
  ports 80/443 only; every hop (including redirects) must resolve to public (global) IP addresses —
  loopback, private, link-local and reserved ranges are refused; ≤5 redirects; 3 MB body cap; timeouts.
* **Parsing:** HTML via lxml; RSS/Atom with `resolve_entities=False, no_network=True` (no XXE).
* **Showcase:** scraped text is rendered with `textContent` only; links are restricted to http(s)/mailto.
* **Budget:** a single counter charges every request (robots.txt and redirects included) against the
  2,000-request / 45-minute / $10 limits; a watchdog emits all envelopes before the deadline.

## Live console (`signalpost serve`)

- Binds to `127.0.0.1` only and answers only requests whose `Host` is `127.0.0.1`, `localhost` or `::1`
  (protects against DNS rebinding).
- Every POST must be same-origin (`http://127.0.0.1:<port>` / `http://localhost:<port>`) or carry no Origin.
- Runs a fixed whitelist of project commands (run, re-run one company, tests, benchmark, evidence check,
  refresh replay, site build). No shell, no user-supplied command text. Organisation numbers must be 9 digits;
  output folders must match `out-[A-Za-z0-9_.-]+`.
- Static files are served only from `out-*/` and `reports/`. `/api/diff` reads only `out-*/envelopes.jsonl` or
  `out-*/history/*.jsonl(.gz)` and never writes.
