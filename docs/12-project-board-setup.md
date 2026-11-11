# 12 — GitHub Project Board Setup

Board name: `Bug-Fix Agent — Agent-X Hackathon 2026`
Template: Kanban or Board (not Projects classic)
Columns: Backlog → Ready → In Progress → Review → QA → Done

## Column definitions

| Column | Entry criteria | Exit criteria | WIP limit |
|--------|---------------|---------------|-----------|
| Backlog | Ticket exists in 11-tickets.md | Assigned owner, branch named, deps merged | None |
| Ready | Acceptance checklist written, files identified | Owner starts work | None |
| In Progress | Branch created, work underway | PR opened, review requested | 1 per owner |
| Review | PR open, reviewer assigned, CI triggered | Approved + CI green | None |
| QA | Merged to main, QA sign-off performed | Ticket moved to Done | None |
| Done | Ticket complete, branch deleted | Archived | None |

## Ticket-to-column mapping (from 11-tickets.md)

### Phase 0 · Foundation (merged)
| Ticket | Title | Status | Owner |
|--------|-------|--------|-------|
| T-00 | Repo init | Done | Yash + Subhi + Durgesh |
| T-01 | CI pipeline | Done | Yash |
| T-02 | Shared types | Done | Durgesh |

### Phase 1 · Design shell
| Ticket | Title | Status | Owner |
|--------|-------|--------|-------|
| T-03 | Design tokens | Backlog | Subhi |
| T-04 | Base components | Backlog | Subhi |
| T-05 | Nav shell + dark mode | Backlog | Subhi |

### Phase 2 · Data + auth
| Ticket | Title | Status | Owner |
|--------|-------|--------|-------|
| T-06 | Data repo + schemas | Done | Yash |
| T-07 | API routes | Done | Yash |
| T-08 | GitHub OAuth + sessions | Done | Yash |

### Phase 3 · Core pages
| Ticket | Title | Status | Owner |
|--------|-------|--------|-------|
| T-09 | Marketing pages | Backlog | Subhi |
| T-10 | Auth routes | Backlog | Subhi |
| T-11 | Dashboard + run detail | Backlog | Subhi |
| T-12 | Error pages + SSE client | Backlog | Subhi |

### Phase 4 · Core agent
| Ticket | Title | Status | Owner |
|--------|-------|--------|-------|
| T-13 | LangGraph pipeline | Backlog | Durgesh |
| T-14 | Docker sandbox | Done | Yash |
| T-15 | LLM + caching | Backlog | Durgesh |
| T-16 | Webhook handler | Done | Yash |
| T-17 | Seeded demo repo | In Progress (baseline-green rework, see docs/19) | You (QA) |

### Phase 5 · Integrations
| Ticket | Title | Status | Owner |
|--------|-------|--------|-------|
| T-18 | GitHub App + webhook | Done | Yash |
| T-19 | Vercel deploy + env | Backlog | Yash + Subhi |
| T-20 | SSE bridge | Backlog | Subhi + Yash |

### Phase 6 · Hardening
| Ticket | Title | Status | Owner |
|--------|-------|--------|-------|
| T-21 | Security headers + rate limits | Done | Yash |
| T-22 | CI pipeline | Done | Yash |
| T-23 | E2E suite | Backlog | Subhi; you verify |
| T-24 | Bundle + visual baselines | Backlog | Subhi |

### Phase 7 · Content + SEO
| Ticket | Title | Status | Owner |
|--------|-------|--------|-------|
| T-25 | Page copy | Backlog | Subhi |
| T-26 | Structured data + OG | Backlog | Subhi |
| T-27 | Sitemap/robots/canonical | Backlog | Subhi |

### Phase 8 · Launch
| Ticket | Title | Status | Owner |
|--------|-------|--------|-------|
| T-28 | Production deploy + smoke test | Backlog | All four |
| T-29 | Real-phone QA sign-off | Backlog | You |
| T-30 | Restore + rollback drills | Backlog | You |

### Phase 9 · Post-launch
| Ticket | Title | Status | Owner |
|--------|-------|--------|-------|
| T-31 | Monitoring + alerts | Backlog | You |
| T-32 | Maintenance runbook | Backlog | You |
| T-33 | Demo rehearsal script | Backlog | You |

## Dependency order (merge sequence)

```
T-00 → T-01 → T-02
T-00 → T-03 → T-04 → T-05
T-02 → T-06 → T-07 → T-08 → T-10 → T-11
T-06 → T-13 → T-16 → T-18 → T-19 → T-20
T-14 → T-17
T-11 → T-23 → T-22
T-09 → T-25 → T-26 → T-27
T-28 → T-29 → T-30 → T-31 → T-32
T-17 → T-33
```

## GitHub project board steps

1. Create project: `https://github.com/orgs/Agent-X-Hackathon-2026-Team-MisfitMinds/projects/new`
2. Template: Board (Kanban)
3. Add the 6 columns above
4. Create an issue for each ticket T-00 through T-33
5. Link each issue to its corresponding PR when opened
6. Set WIP limit of 1 per owner on "In Progress"
7. Move tickets left-to-right as work progresses
8. Review daily at stand-up; blockers documented in issue comments
