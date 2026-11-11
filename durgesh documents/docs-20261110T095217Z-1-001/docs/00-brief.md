# 00 — Product Brief: Bug-Fix Agent

## The idea
An AI agent that turns a GitHub issue into a reviewed, tested pull request. A developer adds the `agent-fix` label to an issue; the agent reads it, reproduces the bug inside an isolated Docker sandbox, writes a failing test that proves the bug, finds the root cause, patches it, confirms the test now passes (with the existing suite still green), and opens a **draft PR** with a plain-English explanation. A human always makes the final merge decision.

**Problem:** Developers spend hours triaging issues.  
**Solution:** Build an agent that reads a GitHub issue, reproduces the bug in a sandbox, identifies the cause, writes and tests a fix, then opens a pull request with an explanation.

## Who it's for
Dev teams at companies working in **private repos** with internal review workflows. They want triage time back but will not trust an agent that can push code unsupervised.

## The one action
**Add the `agent-fix` label to an issue.** Everything else is automatic until a human reviews the PR.

## Must-have features
1. **Sandboxed code execution:** every clone, install, and test run happens in a throwaway Docker container (no network after dependency install, CPU/memory/time limits, no host mounts).
2. **Tests that pass after the fix:** the agent writes a reproduction test; the PR is opened only if that test fails before the patch and passes after it, and the existing suite stays green.
3. **Human review before merge:** PRs are opened as drafts; branch protection requires an approving review; the agent has no merge permission.
4. **Red→green proof:** failing-before / passing-after test output embedded in the PR and dashboard.
5. **Root-cause write-up + confidence score:** in the PR body, covering what broke, why, what changed, and how sure the agent is (High / Medium / Low with reasons).
6. **Issue progress comments:** the agent posts status on the issue at each step (picked up → reproduced → fixed → PR opened, or "couldn't reproduce").

## The feeling
Calm and trustworthy, like a senior engineer you'd hand the keys to. Quiet UI, clear status, nothing flashy. The reasoning is transparent and the agent's own uncertainty is stated openly.

## References
- **Linear:** restraint, typography, calm density.
- **Vercel:** deployment-style status timeline and logs.
- **GitHub Actions:** step-by-step run view with collapsible logs.

## Constraints
- **Deadline:** 24–48 hour hackathon sprint.
- **Budget:** ₹0 — free tiers and hackathon credits only.
- **Team (4):** Agent (LangGraph pipeline + prompts) · Sandbox/Infra (Docker runner, GitHub App, webhooks) · Frontend (Next.js dashboard) · Pitch/QA (demo repo, seeded bugs, deck, rehearsals).
- **Stack:** Python · FastAPI (webhooks + API, SSE for live events) · LangGraph (Read → Reproduce → Diagnose → Fix → Verify → PR) · Docker sandbox · Next.js dashboard · GitHub App (label webhook, comments, draft PRs).

## Demo definition of done
On a prepared Python demo repo, label 3 seeded issues live → at least 2 produce draft PRs with red→green proof and root-cause notes, the third ends with an honest "couldn't reproduce" comment. The dashboard shows each run end to end.

## ASSUMPTIONS
- MVP supports **Python repos with pytest only**; other languages are a roadmap slide.
- The demo runs on **our own seeded repo** with small, deterministic bugs (off-by-one, wrong condition, missing null check), not arbitrary real-world repos.
- A free-tier LLM API (e.g. Gemini or Groq free tier, or hackathon credits) is enough for ~20–30 full runs during build and demo.
- The GitHub App runs locally with webhooks forwarded via smee.io or ngrok; no paid hosting needed.
- Issues contain enough detail (steps, expected vs actual) to reproduce; poorly written issues get a "need more info" comment instead of a guess.
- "Human review" is enforced by draft PRs + branch protection, not by custom approval UI.

## RISKS
- **Free-tier rate limits** stall the agent mid-demo. *Mitigation:* cache LLM responses for the rehearsed issues; keep a recorded backup run.
- **Reproduction fails** on the live issue (env drift, flaky install). *Mitigation:* prebuilt Docker image with dependencies baked in; pin versions.
- **Wrong or overfitted fix:** the patch passes the new test but breaks intent. *Mitigation:* require the full existing suite to pass; lower confidence when the diff touches many files; human review is the final gate.
- **Sandbox escape / secret leakage** from running untrusted code. *Mitigation:* no network during test runs, no tokens inside the container, non-root user, resource and time limits.
- **Scope creep** across 6 features in 48 hours. *Mitigation:* build order is pipeline → sandbox → PR → issue comments → dashboard; the dashboard can fall back to a simple log view.
- **Judges ask "how is this different from Copilot/Devin?"** *Mitigation:* lead the pitch with red→green proof + mandatory human gate + cost (₹0, self-hostable for private repos).