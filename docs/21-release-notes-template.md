# 21 — Release Notes Template

**Owner:** You (project lead / QA)
**Use:** copy the block below for each release. A release is not complete until every field is
filled from real output (guide §7F.7). A gate that was not run is recorded as NOT RUN, never as
passed (guide §8).

---

```markdown
# Release <version> — <YYYY-MM-DD>

Commit of `main`: <sha>
Released by: <name>

## What shipped

| Ticket | Title | Owner | PR |
|--------|-------|-------|----|
| T-xx | | | |

## Gate results

Result is one of: PASS / FAIL / NOT RUN. Evidence is a CI run link or pasted output.

| Gate | Command | Fix owner | Result | Evidence |
|------|---------|-----------|--------|----------|
| TypeScript | `npx tsc --noEmit` | Subhi | | |
| Frontend lint | `npx eslint . --max-warnings=0` | Subhi | | |
| Python lint | `ruff check apps/api/` | Yash / Durgesh | | |
| Python types | `mypy --strict apps/api/` | Yash / Durgesh | | |
| Frontend unit | `npx vitest run --reporter=verbose` | Subhi | | |
| Backend unit | `pytest tests/unit/ -v` | Yash / Durgesh | | |
| Backend integration | `pytest tests/integration/ -v` | Yash | | |
| E2E (Chromium + WebKit) | `npx playwright test --reporter=html` | Subhi; lead verifies | | |
| Accessibility | `npx playwright test e2e/a11y/` | Subhi | | |
| Lighthouse | `npx lhci autorun` | Subhi; lead verifies | | |
| Bundle size | `bash scripts/check-bundle-size.sh` | Subhi | | |
| Node audit | `npm audit --audit-level=high` | Subhi | | |
| Python audit | `pip-audit` | Yash | | |
| Visual regression | `npx playwright test e2e/visual/` | Subhi; lead approves baselines | | |

## Demo definition of done

| Check | Result | Evidence |
|-------|--------|----------|
| Issue #1 → draft PR with failing-before / passing-after proof | | |
| Issue #4 → draft PR with failing-before / passing-after proof | | |
| Issue #5 → "couldn't reproduce" comment, no PR | | |
| Dashboard shows all three runs | | |
| Sandbox isolation active (no network, non-root, no mounts, limits) | | |
| Agent has no merge permission; PRs are drafts | | |

## Smoke test

| Check | Result |
|-------|--------|
| Home returns 200 | |
| `/auth/session` returns 200 or 401, not 5xx | |
| `/health` returns `{"status":"ok"}` | |

## Known limits

- Python + pytest only, seeded demo repository only.
- <anything not built, not run, or failing in this release>

## Rollback

Procedure: `docs/15-backup-rollback-drill-t30.md`. Previous good commit: <sha>.

## Sign-offs

| Area | Owner | Signed | Date |
|------|-------|--------|------|
| Frontend | Subhi | | |
| Agent pipeline | Durgesh | | |
| Backend, sandbox, GitHub App | Yash | | |
| QA, demo, release | Project lead | | |
```
