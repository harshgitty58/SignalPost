# Sources, rights and access policy

| Source | Endpoint(s) | Licence / terms | Access pattern |
|---|---|---|---|
| Enhetsregisteret | `data.brreg.no/enhetsregisteret/api/enheter?organisasjonsnummer=…` (≤100 per call), `/enheter/{org}/roller`, `/underenheter?overordnetEnhet={org}`, `/konsernstruktur/{org}`, `/oppdateringer/enheter`, `/oppdateringer/roller` | NLOD 2.0 open data | documented open API, ≤8 concurrent |
| Regnskapsregisteret | `data.brreg.no/regnskapsregisteret/regnskap/{org}` | NLOD 2.0 | 1 call per company |
| NAV vacancy feed | `pam-stilling-feed.nav.no/api/v1/feed`, `/feedentry/{uuid}` | free public API, arbeidsplassen.nav.no API terms | feed read once per run (look-back window), detail only for name-matched candidates; only ACTIVE ads published; contact persons never stored |
| Wikidata | `query.wikidata.org/sparql`: one query per 100 org. numbers for items whose Norwegian org. number (P2333) is in the batch, returning their official website (P856) | CC0 | website *candidate* only; the site must still pass the identity gate |
| Company websites | registry-declared site (company or registered workplace), registry e-mail domain, Wikidata P856, `<name>.no` | company-owned content | robots.txt honoured (incl. 401/403 = disallow), identifying User-Agent, ≤2 concurrent per host, ≤5 pages per site, 3 MB cap |

**Not used:** search engines, LinkedIn/Meta/Glassdoor/Indeed or any unofficial client, directories
(proff.no, gulesider, purehelp, 1881…), `w2.brreg.no/kunngjoring` (disallowed by its robots.txt).
Social profile URLs are only *links found on the verified official site*; the platforms are never fetched.

**Personal data:** role holders' names only (birth dates dropped, deceased persons skipped); e-mail
limited to role mailboxes (post@, info@…) on the company's own domain; registry phone not shown for
sole proprietorships.

**Showcase (viewer side, optional):** the workplace map sends registered addresses to Kartverket's address API
(`ws.geonorge.no/adresser/v1/sok`, CC BY 4.0) only when the reader presses “Show on map”. It is not part of any run.

**Caches:** none. Every run fetches live; `--previous` reads only this agent's own prior output.
