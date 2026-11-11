# 15 — Backup / Restore / Rollback Drills: T-30

**Owner:** You (project lead / QA)
**Depends on:** T-28 production deploy
**Targets:** Restore < 10 minutes, Rollback < 5 minutes

---

## Data backup (transient JSON files, no database per ADR-006)

Backup target: `apps/api/data/` directory (JSON run files, sessions, LLM cache, webhook events)

```powershell
# Create backup tarball (tar ships with Windows 10+; Compress-Archive would write a zip)
tar -czf "backup-$(Get-Date -Format 'yyyyMMdd-HHmmss').tar.gz" -C apps/api data

# Verify the newest backup (tar.exe does not expand wildcards in PowerShell).
# File names carry the timestamp, so sorting by name gives the newest last.
$backup = Get-ChildItem backup-*.tar.gz | Sort-Object Name | Select-Object -Last 1
if ($backup) { tar -tzf $backup.FullName } else { Write-Host "No backup files found" }
```

## Restore drill (< 10 minutes)

| Step | Action | Target time | Actual | Pass/Fail |
|------|--------|-------------|--------|-----------|
| 1 | Wipe `apps/api/data/` (simulate data loss) | 1 min | | |
| 2 | Restore tarball from backup | 3 min | | |
| 3 | Verify 3 seeded runs visible on `/dashboard` | 3 min | | |
| 4 | Confirm run data matches (run IDs, statuses, confidence) | 2 min | | |
| **Total** | | **< 10 min** | | |

## Rollback drill (< 5 minutes)

| Step | Action | Target time | Actual | Pass/Fail |
|------|--------|-------------|--------|-----------|
| 1 | `vercel rollback` to previous production deploy | 2 min | | |
| 2 | `docker compose` redeploy backend (if needed) | 2 min | | |
| 3 | Smoke test: `curl -sf https://<domain>/` → 200 | 1 min | | |
| **Total** | | **< 5 min** | | |

---

## Drill record

| Drill | Date | Start time | End time | Duration | Pass/Fail | Issues |
|-------|------|------------|----------|----------|-----------|--------|
| Restore | | | | | | |
| Rollback | | | | | | |

**QA sign-off:** Restore drill < 10 min, rollback drill < 5 min, both documented.  
**Signed:** [Your name], Project Lead / QA  
**Date:** [date]
