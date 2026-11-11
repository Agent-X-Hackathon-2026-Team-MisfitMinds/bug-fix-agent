# 19 — Seeded Demo Reference: T-17

**Owner:** You (project lead / QA)
**Purpose:** Single source of truth for the three seeded bugs, their known fixes, the manual
reproduction tests and the exact GitHub issue text. This file lives in the main repo on purpose:
the agent clones `seeded-demo-repo`, so that repo must not contain the answers.

## What the agent sees vs what stays here

| In `seeded-demo-repo` (cloned by the agent) | In the main repo only (lead reference) |
|---|---|
| `src/app.py` with one bug per function | Known fixes (below) |
| `tests/test_app.py`: 7 tests, green with the bugs present | `scripts/demo/reference/test_issue_{1,2,3}.py` |
| Neutral `README.md` | `scripts/demo/verify_seeded_repo.py` |

The existing suite must start green. The Verify step only opens a PR when the new reproduction test
passes **and the full existing suite stays green**; a suite that is red before the fix can never
satisfy that honestly.

## The three bugs

| # | Function | Bug type | Reproduce | Expected | Actual | Known fix | Demo outcome |
|---|----------|----------|-----------|----------|--------|-----------|--------------|
| 1 | `calculate_discount` | Off-by-one | `calculate_discount(100, 20)` | `80` | `81` | `return price - discount` (drop `+ 1`) | Draft PR, confidence High |
| 2 | `validate_age` | Wrong boundary condition | `validate_age(65)` | `True` | `False` | `age >= 65` → `age > 65` | Draft PR, confidence Medium |
| 3 | `get_user_profile` | Missing null check | `get_user_profile(999)` | `None` | `TypeError` | `if user is None: return None` | "couldn't reproduce" comment, no PR |

Bug 3 is real and reproducible with the reference test. The demo outcome is "couldn't reproduce"
because its **issue text** is deliberately too thin (guide §7F.1), not because the bug is fake.

## Verify the seeded repo (run before every rehearsal)

```bash
python scripts/demo/verify_seeded_repo.py
```

Works on a temporary copy. Passes only if the baseline suite is green and, for each bug, the
reference test is red before the known fix and the reference test plus the full suite are green
after it. Last result (local, 2026-11-11): 13 checks, all passed.

## GitHub issues to create on `seeded-demo-repo`

Create all three **without** the `agent-fix` label. The label is added live during rehearsal or the
demo; adding it is the one user action that starts a run.

### Issue 1

**Title:** `calculate_discount returns 1 more than the discounted price`

```
Steps to reproduce:
1. Open a Python shell in the repo root and run: from src.app import calculate_discount
2. Call calculate_discount(100, 20)

Expected behaviour: returns 80 (100 minus 20 percent).
Actual behaviour: returns 81.

Every result is exactly 1 too high, for example calculate_discount(200, 10) returns 181 instead of 180.
```

### Issue 2

**Title:** `validate_age rejects age 65 although the range is 18 to 65 inclusive`

```
Steps to reproduce:
1. Open a Python shell in the repo root and run: from src.app import validate_age
2. Call validate_age(65)

Expected behaviour: returns True. The docstring says ages 18 to 65 inclusive are valid.
Actual behaviour: returns False.

validate_age(64) returns True and validate_age(66) returns False, so only the upper boundary is wrong.
```

### Issue 3 (deliberately thin)

**Title:** `Profile page sometimes breaks`

```
It crashes for some users. Please fix.
```

No function name, no steps, no expected or actual behaviour. The agent must reply that it needs
more information / could not reproduce, and must not open a PR.

## Open mismatches for other owners (not edited by the lead)

The seeded repo above is the definition the demo runs against. These files describe different bugs
and need their owners to align them:

| File | Owner | Mismatch |
|------|-------|----------|
| `apps/api/demo_bugs/*` | Durgesh | Different formulas and boundary (`price - price / percentage`, age 18) and a module layout the seeded repo does not have |
| `apps/api/pipeline/langgraph.py` (`write_reproduction_test`) | Durgesh | Hardcoded tests import `calculate_discount` / `validate_age` / `get_user_profile` as top-level modules and assert `validate_age(18)`; the seeded repo exposes `src/app.py` and the boundary bug is at 65 |
| `apps/api/tests/fixtures/conftest_bugs.py` | Durgesh | Same definitions as `demo_bugs` |
