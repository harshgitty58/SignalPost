# Benchmark report

### out-dev — dev-v3b @ ad57ced8bba8

100 companies · valid=True · requests=899 · time=252.6s · cost=$0.0 · p50/p95 per company=47578/63641 ms

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

### out-val — val-v3 @ 5e1d83d8bf4f

100 companies · valid=True · requests=802 · time=250.0s · cost=$0.0 · p50/p95 per company=45468/66546 ms

| Family | Available | 95% CI | Ambiguous (abstained) | Not available | Failed/blocked | Claims |
|---|---|---|---|---|---|---|
| identity | 99% | 95%–100% | 0% | 1% | 0% | 1357 |
| status | 99% | 95%–100% | 0% | 1% | 0% | 99 |
| industry | 99% | 95%–100% | 0% | 1% | 0% | 99 |
| financials | 99% | 95%–100% | 0% | 1% | 0% | 5373 |
| leadership | 99% | 95%–100% | 0% | 1% | 0% | 395 |
| locations | 73% | 64%–81% | 0% | 27% | 0% | 73 |
| group | 11% | 6%–19% | 0% | 1% | 0% | 27 |
| website | 13% | 8%–21% | 19% | 67% | 1% | 13 |
| social_profiles | 5% | 2%–11% | 0% | 95% | 0% | 7 |
| contact | 26% | 18%–35% | 0% | 1% | 73% | 27 |
| description | 9% | 5%–16% | 0% | 91% | 0% | 9 |
| jobs | 1% | 0%–5% | 0% | 99% | 0% | 1 |
| activity | 99% | 95%–100% | 0% | 1% | 0% | 368 |

| Derived coverage | Companies | 95% CI |
|---|---|---|
| financial history (≥1 filed year) | 99% | 95%–100% |
| material activity (excl. employee-count updates) | 99% | 95%–100% |
| real group relations (parent/subsidiary) | 10% | 6%–17% |
| company-owned news items | 4% | 2%–10% |

Published claims: 7848 (78.5/company) · evidence-incomplete references: 0 · identity gate: {'unreachable': 11, 'rejected': 9, 'ambiguous': 13, 'accepted': 13, 'blocked': 2, 'related_site': 1}

