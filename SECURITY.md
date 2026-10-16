# Security and outbound URL policy

* **Secrets:** none required. Optional `NAV_FEED_TOKEN` env var only. Nothing secret is written to outputs or logs.
* **Outbound URLs** (`src/signalpost/http.py`): `http`/`https` only; no credentials in URLs; no raw-IP hosts;
  ports 80/443 only; every hop (including redirects) must resolve to public (global) IP addresses —
  loopback, private, link-local and reserved ranges are refused; ≤5 redirects; 3 MB body cap; timeouts.
* **Parsing:** HTML via lxml; RSS/Atom with `resolve_entities=False, no_network=True` (no XXE).
* **Showcase:** scraped text is rendered with `textContent` only; links are restricted to http(s)/mailto.
* **Budget:** a single counter charges every request (robots.txt and redirects included) against the
  2,000-request / 45-minute / $10 limits; a watchdog emits all envelopes before the deadline.
