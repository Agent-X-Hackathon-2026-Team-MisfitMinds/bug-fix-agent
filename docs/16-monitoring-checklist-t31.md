# 16 — Monitoring + Alerts Checklist: T-31

**Owner:** You (project lead / QA)
**Depends on:** T-28 production deploy
**Constraint:** No third-party scripts (self-hosted only, per ADR-011 / demo scope)

---

## Monitoring setup

| Monitor | Tool | Threshold | Alert action | Owner |
|---------|------|-----------|--------------|-------|
| Uptime | UptimeRobot (free) or cron + curl | Down > 2 min | Notify project lead | You |
| 5xx error spike | Server error logs | > 5/min | Investigate | Yash |
| Web Vitals | Self-hosted (no third-party scripts) | p75 LCP > 2.5s, INP > 200ms, CLS > 0.1 | Investigate | Subhi |
| LLM rate limit | LLM cache hit/miss logs | Free-tier limit approached | Switch to cached/demo responses | Durgesh |
| Docker sandbox failure | Docker container logs | Container timeout/crash | Investigate sandbox | Yash |

---

## No-PII rule

- [ ] No PII in any log or alert payload
- [ ] No issue body, PR diff, email, or personal data in logs
- [ ] Errors shown to users are generic (no stack traces)
- [ ] No tokens, webhook secrets, or GitHub keys in logs

---

## Alert configuration template

```powershell
# Uptime check (cron example, runs every 2 minutes)
*/2 * * * * curl -sf https://<domain>/ > $null || Send-Alert "Site down"

# 5xx error check (parse server logs)
Get-Content "apps/api/logs/*.log" -Tail 100 \| Select-String "5xx" \| Measure-Object
```

---

## Acceptance checklist

- [ ] Uptime alert triggers if site down > 2 minutes
- [ ] 5xx spike > 5/min triggers investigation
- [ ] Web Vitals alerts configured (p75 LCP > 2.5s, INP > 200ms, CLS > 0.1)
- [ ] LLM rate-limit alerts configured
- [ ] Docker sandbox failure alerts configured
- [ ] No PII in any log or alert payload (verified)
- [ ] Deliberate test error appears in logs (verified)
- [ ] Uptime monitor configured and active

**QA sign-off:** Monitoring + alerts live, no PII in logs, test error verified in logs.  
**Signed:** [Your name], Project Lead / QA  
**Date:** [date]
