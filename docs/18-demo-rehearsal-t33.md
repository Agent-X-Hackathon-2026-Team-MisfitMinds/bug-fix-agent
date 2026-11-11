# 18 — Demo Rehearsal Script: T-33

**Owner:** You (project lead / QA)
**Depends on:** T-17 merged, T-28 production deploy, T-13/T-14/T-16 working
**Demo Definition of Done (from docs/00-brief.md § 38):**
- Label 3 seeded issues live → ≥2 produce draft PRs with red→green proof and root-cause notes
- 3rd issue ends with honest "couldn't reproduce" comment
- Dashboard shows all 3 runs end-to-end

---

## Seeded demo issues

| Issue | Bug type | Expected outcome | Confidence |
|-------|----------|-----------------|------------|
| Issue #1 | Off-by-one in `calculate_discount` | Draft PR with red→green proof | High |
| Issue #4 | Wrong boundary in `validate_age` | Draft PR with red→green proof | Medium |
| Issue #5 | Missing null check in `get_user_profile` | Honest "couldn't reproduce" comment | Low / null |

Exact issue titles and bodies, known fixes and reference tests: `docs/19-seeded-demo-reference.md`.
Issue #5 is filed with deliberately thin text; that is why it ends in "couldn't reproduce".

---

## Demo rehearsal script (step-by-step)

### Pre-demo (30 minutes before)
- [ ] Production URL live: `curl -sf https://<domain>/` → 200
- [ ] `/auth/session` → 200 or 401 (not 5xx)
- [ ] LLM free-tier cache warmed for rehearsed issues (Durgesh)
- [ ] Seeded repo verified: `python scripts/demo/verify_seeded_repo.py` → all checks passed
- [ ] Docker sandbox prebuilt with dependencies (Yash)
- [ ] Recorded backup run ready (in case of LLM rate limits)
- [ ] Dashboard accessible: `https://<domain>/dashboard`

### Live demo (15 minutes)

| Step | Action | Expected result | Pass/Fail |
|------|--------|-----------------|-----------|
| 1 | Open production URL | Home page loads | |
| 2 | Sign in with GitHub OAuth | Dashboard renders, signed in | |
| 3 | Navigate to seeded demo repo | 3 issues open, none carrying `agent-fix` yet | |
| 4 | Label issue #1 (`calculate_discount`) | Run appears on dashboard, SSE timeline starts | |
| 5 | Watch all 6 SSE steps | read → reproduce → diagnose → fix → verify → pr | |
| 6 | Verify red→green proof | Test output shows FAILED → PASSED | |
| 7 | Verify root-cause notes | Plain-English explanation visible | |
| 8 | Open draft PR | PR link visible, draft status | |
| 9 | Label issue #4 (`validate_age`) | Run appears, all 6 steps stream | |
| 10 | Verify red→green proof | Test output shows FAILED → PASSED | |
| 11 | Label issue #5 (`get_user_profile`) | Run appears | |
| 12 | Verify "couldn't reproduce" | Honest comment posted, confidence null | |
| 13 | Verify dashboard shows all 3 runs | All 3 runs visible end-to-end | |

### Post-demo
- [ ] Recorded backup run available if LLM rate limits stalled
- [ ] Demo deck updated with live results
- [ ] Judge-facing explanation emphasizes: red→green proof, Docker isolation, mandatory human review, ₹0 scope

---

## Recorded backup run

If LLM free-tier rate limits interrupt the live demo:
- [ ] Pre-recorded video of all 3 seeded issues → draft PRs
- [ ] Video shows red→green proof for issues #1 and #4
- [ ] Video shows "couldn't reproduce" for issue #5
- [ ] Video shows dashboard with all 3 runs
- [ ] Backup video cued and ready to play

---

## QA sign-off

Demo DoD met: ≥2 of 3 seeded issues → draft PR with red→green proof  
3rd issue posts honest "couldn't reproduce" comment  
Dashboard shows all 3 runs with SSE timeline  
Recorded backup run available  

**Signed:** [Your name], Project Lead / QA  
**Date:** [date]
