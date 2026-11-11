# 01 — Product Requirements Document: Bug-Fix Agent

## Problem statement
Developers at companies with private GitHub repos spend hours triaging, reproducing, and fixing bugs. Existing tooling either only flags issues without fixing them, auto-remediates without proof (and is therefore untrusted), or is language-narrow (Java-only). There is no agent that reads an issue, reproduces the bug in an isolated sandbox, proves the fix with a red→green test, and routes to a human reviewer — all at zero cost for private repos.

## One-line vision
Every GitHub issue becomes a tested, human-reviewed pull request — automatically, safely, at zero cost.

## Personas
| Persona | Goals | Frustrations | Device | Tech comfort |
|---------|-------|--------------|--------|--------------|
| Priya — Staff Engineer / tech lead (ASSUMPTION: role) | Cut triage time while keeping code quality and review gates | AI tools that merge without proof; low-quality issue noise | Laptop, desktop browser | High (ASSUMPTION:) |
| Marcus — Engineering manager (ASSUMPTION: role) | Ship faster while keeping compliance and security | Unreviewed AI code; sandbox/secret leakage risk | Laptop, occasional iPad | Medium-high (ASSUMPTION:) |
| Diego — Mid-level developer (ASSUMPTION: role) | Get hard bugs fixed without waiting on seniors | Stuck on hard-to-reproduce bugs | Laptop | Medium (ASSUMPTION:) |

## Features (MUST / SHOULD / COULD)

**MUST**
- GitHub App + `agent-fix` label webhook — the single user action that starts everything
- Docker sandboxed execution — isolation so untrusted code never touches the host
- Reproduction test (red) + fix verification (green) + existing suite stays green — red→green proof
- Draft PR with root-cause write-up + confidence score — human-review gate; agent never merges
- Issue progress comments at each step — status visibility without leaving GitHub
- Live run timeline via SSE — transparent reasoning for every step

**SHOULD**
- Honest "couldn't reproduce" comment — avoids false fixes on thin issues
- Seeded demo repo with deterministic bugs — supports the hackathon demo DoD
- Cached LLM responses for rehearsed issues — mitigates free-tier rate limits

**COULD (out of v1)**
- Multi-language beyond Python/pytest
- Custom approval UI beyond draft PRs + branch protection
- Slack/Teams notifications

## User stories with acceptance hints
1. As a developer, I label an issue `agent-fix` → ASSUMPTION: the webhook is received, pipeline starts, and a status comment is posted on the issue within ~30 seconds.
2. As a developer, I see red→green test output in the PR → ASSUMPTION: the reproduction test fails before the patch, passes after it, and the existing suite stays green.
3. As a tech lead, I review and approve the draft PR → ASSUMPTION: the PR is opened as draft, branch protection requires an approving review, and the agent has no merge permission.
4. As an engineering manager, no untrusted code runs on my host → ASSUMPTION: all clone/install/test runs happen in a Docker container with no network after dep install, no host mounts, non-root user, and CPU/memory/time limits.
5. As a developer on a thin issue, I get a "need more info" comment → ASSUMPTION: the agent detects missing reproduction steps and declines to guess instead of producing a bad fix.

## MVP scope
Python repos with pytest only; seeded deterministic bugs (off-by-one, wrong condition, missing null check) on our own demo repo; local GitHub App with webhooks forwarded via smee.io or ngrok; free-tier LLM API (~20–30 full runs); draft PRs + branch protection as the human gate; dashboard may fall back to a simple log view; 24–48 hour hackathon sprint; team of 4 (Agent/LangGraph, Sandbox/Infra/Docker/GitHub App, Frontend/Next.js, Pitch/QA); budget ₹0.

## Non-goals for v1
- Non-Python repos or arbitrary real-world repos (seeded demo only)
- Auto-merge or agent-push-to-main
- Custom approval UI
- Multi-language support
- Slack/Teams notifications, scheduled or nightly runs
- Paid hosting or multi-org SaaS

## Single primary conversion goal
A developer adds the `agent-fix` label to an issue and a draft PR with red→green proof is opened, ready for human review.

## Success metrics (all targets ASSUMPTION:)
| Metric | Target | How measured |
|--------|--------|--------------|
| % of labeled issues producing a draft PR | ≥ 66% (2 of 3 seeded) | Label webhook events vs. draft PRs created via GitHub API |
| % of draft PRs with red→green proof | 100% | PR body contains failing-before / passing-after test output |
| Human review rate before merge | 100% | Branch protection approval events on every merged PR |
| Runs shown end-to-end on dashboard | 3 of 3 seeded runs | SSE events received per run |
| Label → draft PR time | < 5 min | Webhook timestamp to PR created timestamp |

## Risks
- **Free-tier rate limits** stall the agent mid-demo. *Mitigation:* cache LLM responses for rehearsed issues; keep a recorded backup run.
- **Reproduction fails** on the live issue (env drift, flaky install). *Mitigation:* prebuilt Docker image with dependencies baked in; pin versions.
- **Wrong or overfitted fix:** patch passes the new test but breaks intent. *Mitigation:* require full existing suite to pass; lower confidence when diff touches many files; human review is the final gate.
- **Sandbox escape / secret leakage** from running untrusted code. *Mitigation:* no network during test runs, no tokens inside the container, non-root user, resource and time limits.
- **Scope creep** across 6 features in 48 hours. *Mitigation:* build order is pipeline → sandbox → PR → issue comments → dashboard; dashboard can fall back to a simple log view.
- **Judges ask "how is this different from Copilot/Devin?"** *Mitigation:* lead the pitch with red→green proof + mandatory human gate + zero cost / self-hostable for private repos.

## Open questions (all ASSUMPTION:)
1. Which LLM provider (Gemini / Groq free tier) and what are its real rate limits?
2. How do we handle non-Python repos that get labeled? → post "need more info" comment.
3. Max sandbox time/memory limit that still runs real test suites? → 5 min, 1 GB.
4. GitHub App installed per-org or just our demo repo? → demo repo only for v1.
5. LLM cache key and TTL for rehearsed issues? → hash of issue title + body.