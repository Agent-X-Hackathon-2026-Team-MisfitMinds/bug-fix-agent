# 02 — Content & SEO: Bug-Fix Agent

## Voice and tone
**Do:**
1. Lead with proof, not promises — red→green output, human gate, draft PRs, sandbox isolation.
2. Use plain engineering language — no marketing fluff, no hype adjectives.
3. Be transparent about limits — Python/pytest only, seeded demo repo, agent never merges.

**Don't:**
1. Don't claim autonomy — the agent never merges; human review is mandatory.
2. Don't use hype words — "revolutionary," "magic," "autonomous," "kills triage."
3. Don't hide the sandbox/security story — put it front and center.

**Sample lines (real customer-trust copy):**
- "Add the `agent-fix` label. The agent reproduces the bug in a Docker sandbox, writes a failing test, patches it, and opens a draft PR — with red→green proof. A human always approves the merge."
- "No network after dependency install. No host mounts. No tokens inside the container."
- "MVP supports Python repos with pytest only. Other languages are a roadmap slide."

## Page inventory
| URL | Job | Primary search intent |
|-----|-----|----------------------|
| `/` | Convert visitor → add `agent-fix` label or view demo | Commercial investigation ("AI bug fix agent GitHub", "auto fix GitHub issues") |
| `/how-it-works` | Explain the 6-step pipeline; build trust via proof | Informational ("how does bug fix agent work", "red green test agent") |
| `/demo` | Live seeded-repo demo (the hackathon DoD) | Investigational ("see agent fix bug live") |
| `/security` | Address trust/sandbox concerns — the #1 blocker for this audience | Investigational ("is AI code agent safe", "Docker sandbox code execution") |
| `/pricing` | Confirm ₹0 / free, self-hostable | Commercial ("bug fix agent pricing", "free GitHub issue agent") |
| `/changelog` | SEO freshness; show active development | Informational / navigational |
| `/about` | Team credibility (4-person hackathon team) | Navigational |
| `/privacy` | Legal compliance (GitHub App OAuth, data handling) | Navigational / legal |
| `/terms` | Legal compliance | Navigational / legal |

## Page copy

### `/` — Home
**H1:** Turn GitHub issues into tested pull requests  
**Subhead:** Add the `agent-fix` label to an issue. The agent reads it, reproduces the bug in an isolated Docker sandbox, writes a failing test, patches it, and opens a draft PR with red→green proof. A human always makes the final merge decision.  
**CTA 1 (primary):** Add the agent-fix label  
**CTA 2 (secondary):** View the live demo  
**Title (≤60 chars):** Bug-Fix Agent: GitHub Issues → Tested PRs  
**Meta description (≤155 chars):** Add the `agent-fix` label to a GitHub issue. The agent reproduces the bug, writes a test, and opens a draft PR with red→green proof. Free, private-repo safe.

### `/how-it-works` — How it works
**H1:** How the agent fixes bugs  
**Steps:** Label → Read → Reproduce → Diagnose → Fix → Verify → Draft PR  
**CTA:** Try it on a seeded issue  
**Title:** How Fixie Works — Issue to Draft PR in 6 Steps  
**Meta description:** See the 6-step pipeline: label an issue, reproduce in Docker sandbox, red→green test proof, draft PR for human review.

### `/demo` — Demo
**H1:** Live demo  
**Subhead:** Label one of 3 seeded issues on our demo repo. Watch the agent reproduce, fix, and open a draft PR — or honestly say "couldn't reproduce."  
**CTA:** Open the demo repo  
**Title:** Live Demo — Bug-Fix Agent on Seeded Issues  
**Meta description:** Watch the agent fix seeded Python bugs live. Label an issue, see red→green proof, review the draft PR.

### `/security` — Security
**H1:** Security and trust  
**Points:** Docker sandbox, no network after dependency install, no host mounts, non-root user, CPU/memory/time limits, no tokens inside the container, draft PRs only, agent never merges, branch protection required  
**CTA:** Read the brief  
**Title:** Security — Sandboxed Code Execution, Human Review Only  
**Meta description:** How the bug-fix agent keeps your code safe: Docker sandbox, no network after install, draft PRs, agent never merges.

### `/pricing` — Pricing
**H1:** Free for private repos  
**Subhead:** ₹0. Self-hostable. No paid tiers. No credit card.  
**CTA:** Get started  
**Title:** Pricing — Free, Self-Hostable Bug-Fix Agent  
**Meta description:** ₹0 bug-fix agent for private GitHub repos. Self-hostable, no paid tiers, no credit card.

## Structured data (schema.org)
| URL | Type | Notes |
|-----|------|-------|
| `/` | `SoftwareApplication` + `Organization` | appName "Fixie Bug-Fix Agent", applicationCategory "DeveloperTool" |
| `/how-it-works` | `FAQPage` | Q+A pairs for each pipeline step |
| `/demo` | `SoftwareApplication` | demo repo link, screenshot |
| `/security` | `AboutPage` | trust/safety claims |
| `/pricing` | `Product` | price ₹0, priceCurrency INR, offers |
| `/about` | `Organization` | team of 4, hackathon project |
| `/privacy`, `/terms` | None | legal pages only |

## Open Graph plan
- og:title, og:description, og:type=website, og:url set on every page
- og:image: shared dashboard screenshot via Next.js dynamic `og:image` route
- Twitter card: `summary_large_image`

## Internal links
- Home → How it works, Demo, Security, Pricing
- How it works → Demo, Security
- Demo → Home, Security
- Security → How it works, Home
- Pricing → Home, Demo
- All pages → Privacy, Terms (footer)

## Legal pages
- `/privacy` — data collected (issue text, repo metadata, GitHub App tokens), retention policy, no PII in logs or URLs, delete-my-data via GitHub App uninstall
- `/terms` — no warranty on agent output, human review required before any merge, hackathon project (no SLA), not for production use without review

## Locales
- English (`en`) only — hackathon project, ₹0 budget, no i18n tooling

## Content ownership and updates
- **Who updates:** Pitch/QA team member (one of the 4 team roles from the brief)
- **How:** Markdown files in the Next.js repo (`content/` directory), updated via pull request, deployed with the app
- **CMS:** None — ₹0 budget, static/Next.js, no paid content platform