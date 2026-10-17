# Email draft — submission to Builderr

**To:** submit@builderr.ai
**Subject:** Signalpost entry — Signalpost Agent — <short sha>
**Attachment:** `signalpost-code.zip` (the code at the submitted commit: `git archive --format=zip -o signalpost-code.zip HEAD`)

Before sending, replace `<40-char sha>` / `<short sha>` with the output of `git rev-parse HEAD` (after
`git push origin main`) and `<your name>` with your name.

---

Hello Builderr team,

Please find my entry for the Signalpost challenge ("Build an agent that finds company information").

**Agent:** Signalpost Agent
**Builder and contact:** <your name>, harshvdn.2@gmail.com
**Repository:** https://github.com/harshgitty58/SignalPost
**Exact commit:** <40-char sha> — https://github.com/harshgitty58/SignalPost/commit/<40-char sha>
**Code:** attached as `signalpost-code.zip` (identical to that commit)

**One command to run it**
```
uv sync --frozen
uv run signalpost run --organisations <batch.jsonl> --out out/
```
Output: one terminal envelope per input in `out/envelopes.jsonl`, the run report in `out/run-report.json`, a static
showcase in `out/site/index.html`. Running the same command again into the same `out/` is a refresh: it archives the
previous run and reports typed changes.

**At least 1,000 company profiles:** `reports/run-1000-envelopes.jsonl.gz` in the repository (1,000/1,000 valid
envelopes, run under the official limits), with its run report `reports/run-1000-run-report.json`.

**Model / API details**
- No LLM is used.
- Brønnøysundregistrene open APIs: Enhetsregisteret, Regnskapsregisteret, roles, sub-units, group structure, change log (NLOD 2.0).
- NAV pam-stilling-feed (free public API; NAV's published public token).
- Wikidata SPARQL (CC0), used only to find website candidates; every site must pass an exact-entity identity gate.
- Company-owned websites, robots.txt honoured, published only after the identity gate.
- No paid API and no API keys.

**Expected run cost:** $0.00 in third-party / external API costs per run (limits enforced by default: 45 minutes,
2,000 outbound requests, $10).

**Measured results** (from the committed `reports/`):
<!-- metrics:start -->
- **100 random companies (smoke test)** (dev-rev18f @ `318dd62b4ff9`): 100/100 valid envelopes (validation passed), 899 requests, 4.1 min, $0.00. Coverage: identity 100%, status 100%, industry 100%, financials 100%, leadership 100%, locations 78%, group 5%, website 17%, social_profiles 8%, contact 31%, description 9%, jobs 0%, activity 100%.
- **1,000 random companies (official limits)** (run-1000-rev18b @ `318dd62b4ff9`): 1000/1000 valid envelopes (validation passed), 1920 requests, 2.9 min, $0.00. Coverage: identity 100%, status 100%, industry 100%, financials 100%, leadership 37%, locations 28%, group 5%, website 0%, social_profiles 0%, contact 17%, description 0%, jobs 0%, activity 100%.
<!-- metrics:end -->

Every published fact carries its source URL, retrieval time, reporting period (where relevant), content SHA-256,
claim span and extraction method. Anything that cannot be tied to the exact legal entity is returned as `ambiguous`
or `not_available` instead of being published. Source rights are in `SOURCES.md`, the outbound URL policy in
`SECURITY.md`, and a requirement-by-requirement checklist in `SUBMISSION.md`.

Thank you,
<your name>
