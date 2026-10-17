# Benchmark report

### out-dev — dev-v4b @ 0a787f5fd3f0

100 companies · valid=True · requests=899 · time=234.0s · cost=$0.0 · p50/p95 per company=47875/65859 ms

| Family | Available | 95% CI | Ambiguous (abstained) | Not available | Failed/blocked | Claims |
|---|---|---|---|---|---|---|
| identity | 100% | 96%–100% | 0% | 0% | 0% | 1375 |
| status | 100% | 96%–100% | 0% | 0% | 0% | 100 |
| industry | 100% | 96%–100% | 0% | 0% | 0% | 104 |
| financials | 100% | 96%–100% | 0% | 0% | 0% | 5510 |
| leadership | 100% | 96%–100% | 0% | 0% | 0% | 402 |
| locations | 78% | 69%–85% | 0% | 22% | 0% | 89 |
| group | 5% | 2%–11% | 0% | 0% | 0% | 6 |
| website | 17% | 11%–26% | 33% | 46% | 4% | 17 |
| social_profiles | 8% | 4%–15% | 0% | 92% | 0% | 17 |
| contact | 31% | 23%–41% | 0% | 69% | 0% | 35 |
| description | 9% | 5%–16% | 0% | 91% | 0% | 9 |
| jobs | 0% | 0%–4% | 1% | 99% | 0% | 0 |
| activity | 100% | 96%–100% | 0% | 0% | 0% | 390 |

| Derived coverage | Companies | 95% CI |
|---|---|---|
| financial history (≥1 filed year) | 100% | 96%–100% |
| material activity (excl. employee-count updates) | 100% | 96%–100% |
| real group relations (parent/subsidiary) | 4% | 2%–10% |
| company-owned news items | 1% | 0%–5% |

Published claims: 8054 (80.5/company) · evidence-incomplete references: 0 · identity gate: {'rejected': 14, 'blocked': 6, 'accepted': 17, 'ambiguous': 22, 'unreachable': 8, 'related_site': 1}

### out-1000 — run-1000-v4 @ 0a787f5fd3f0

1000 companies · valid=True · requests=1795 · time=125.2s · cost=$0.0 · p50/p95 per company=218/1391 ms

| Family | Available | 95% CI | Ambiguous (abstained) | Not available | Failed/blocked | Claims |
|---|---|---|---|---|---|---|
| identity | 100% | 99%–100% | 0% | 0% | 0% | 13568 |
| status | 100% | 99%–100% | 0% | 0% | 0% | 1003 |
| industry | 100% | 99%–100% | 0% | 0% | 0% | 1015 |
| financials | 100% | 99%–100% | 0% | 0% | 0% | 43953 |
| leadership | 32% | 29%–35% | 0% | 0% | 68% | 1253 |
| locations | 22% | 20%–25% | 0% | 7% | 71% | 254 |
| group | 5% | 4%–6% | 0% | 0% | 2% | 60 |
| website | 0% | 0%–1% | 0% | 3% | 96% | 3 |
| social_profiles | 0% | 0%–1% | 0% | 5% | 95% | 2 |
| contact | 17% | 15%–19% | 0% | 4% | 79% | 171 |
| description | 0% | 0%–1% | 0% | 4% | 95% | 3 |
| jobs | 0% | 0%–0% | 0% | 100% | 0% | 0 |
| activity | 100% | 99%–100% | 0% | 0% | 0% | 3610 |

| Derived coverage | Companies | 95% CI |
|---|---|---|
| financial history (≥1 filed year) | 0% | 0%–0% |
| material activity (excl. employee-count updates) | 100% | 99%–100% |
| real group relations (parent/subsidiary) | 5% | 4%–6% |
| company-owned news items | 0% | 0%–1% |

Published claims: 64895 (64.9/company) · evidence-incomplete references: 0 · identity gate: {'accepted': 3, 'ambiguous': 4, 'rejected': 1}

