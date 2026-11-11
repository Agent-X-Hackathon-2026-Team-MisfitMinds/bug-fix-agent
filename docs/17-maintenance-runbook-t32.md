# 17 — Maintenance Runbook: T-32

**Owner:** You (project lead / QA)
**Cadence:** Monthly + quarterly
**Depends on:** T-28 production deploy, T-30 drills

---

## Monthly maintenance tasks

| Task | Owner | Evidence gate | Due |
|------|-------|---------------|-----|
| Dependency updates (npm + pip) | Subhi / Yash | `npm audit` + `pip audit` zero High/Critical | Monthly |
| Security audit | Yash | Security headers scan passes | Monthly |
| Lighthouse re-check | Subhi | Mobile score ≥ 90 on app routes (budget in `docs/05-architecture.md`) | Monthly |
| Cost review | You | ₹0 budget maintained (free tiers only) | Monthly |
| Secrets rotation review | Yash | No secrets in `NEXT_PUBLIC_*`, `.env` git-ignored | Monthly |

---

## Quarterly drills

| Drill | Target | Owner | Due |
|-------|--------|-------|-----|
| Restore drill | < 10 minutes | You | Quarterly |
| Rollback drill | < 5 minutes | You | Quarterly |
| Secrets rotation | All secrets rotated | Yash | Quarterly |

---

## Maintenance runbook template

```
# Monthly Maintenance — [Month Year]

## 1. Dependency updates
- npm audit result: [pass/fail]
- pip audit result: [pass/fail]
- Actions taken: [describe]

## 2. Security audit
- Security headers scan: [pass/fail]
- No secrets in NEXT_PUBLIC_*: [verified]
- .env git-ignored: [verified]

## 3. Lighthouse re-check
- Mobile score on /login: [score ≥ 90]
- Mobile score on /dashboard: [score ≥ 90]

## 4. Cost review
- Monthly spend: ₹0 (free tiers only)
- LLM free-tier usage: [within limits]

## 5. Secrets rotation review
- GitHub App private key: [rotated/not rotated]
- Webhook secret: [rotated/not rotated]
- Session secret: [rotated/not rotated]
- LLM API key: [rotated/not rotated]

## 6. Sign-off
- Reviewed by: [Your name]
- Date: [date]
```

---

## Evidence requirements

For each monthly/quarterly task, evidence must include:
- Command output or screenshot
- Date and time performed
- Owner name
- Pass/fail result
- Any issues found and resolution

**QA sign-off:** Runbook reviewed by team, first monthly audit completed.  
**Signed:** [Your name], Project Lead / QA  
**Date:** [date]
