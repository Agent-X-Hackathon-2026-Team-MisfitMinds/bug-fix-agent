# PR #28 Review: Seeded Demo Repo Baseline Rework (T-17)

**PR URL**: https://github.com/Agent-X-Hackathon-2026-Team-MisfitMinds/bug-fix-agent/pull/28  
**Commits**: 2 (5ee9b52, 4146744)  
**Author**: mahajansarthaksm13 (Sarthak Mahajan)  
**Date**: Wed Nov 11 14:24:30 - 14:43:11 2026

---

## What This PR Does

This is a **major rework** of the seeded demo repository (T-17). The core problem identified: the original seeded repo had reproduction tests that FAIL with the bugs present, meaning `pytest` would show "4 failed / 0 passed" before any fix. The "Verify" gate requires the existing suite to stay green, which could never hold if the tests are designed to fail.

### Solution: Split into two layers

| Layer | Location | Purpose | Passes with bugs? |
|-------|----------|---------|-------------------|
| **Baseline suite** | `seeded-demo-repo/tests/test_app.py` | 7 tests that PASS with bugs present | ✅ Yes |
| **Reference tests** | `scripts/demo/reference/test_issue_{1,2,3}.py` | Prove red→green for each bug | ❌ Red before fix, ✅ Green after |
| **Verification script** | `scripts/demo/verify_seeded_repo.py` | Proves baseline green + red→green for each bug on temp copy | ✅ All 13 checks pass |

---

## Commit 1: `5ee9b52` - Make Seeded Demo Repo Baseline Green

### Files Changed (10 files, 266 insertions, 79 deletions)

#### 1. `seeded-demo-repo/src/app.py` - Source Code Changes

**Before**:
```python
def calculate_discount(price, discount_percent):
    """Apply a percentage discount to a price.
    Expected: price * (1 - discount_percent / 100)
    Bug: off-by-one — adds 1 to the result.
    """
    discount = price * (discount_percent / 100)
    return price - discount + 1

def validate_age(age):
    """Return True if age is between 18 and 65 inclusive.
    Expected: 18 <= age <= 65
    Bug: wrong boundary — rejects age 65 (uses >= instead of >).
    """
    if age < 18 or age >= 65:
        return False
    return True

def get_user_profile(user_id):
    """Fetch a user profile by ID.
    Expected: returns profile dict or None if not found
    Bug: missing null check — crashes with AttributeError if user not found.
    """
    user = _lookup_user(user_id)
    return user.name  # BUG: crashes on None
```

**After**:
```python
def calculate_discount(price, discount_percent):
    """Apply a percentage discount to a price.
    Returns price * (1 - discount_percent / 100).
    """
    discount = price * (discount_percent / 100)
    return price - discount + 1  # BUG STILL PRESENT

def validate_age(age):
    """Return True if age is between 18 and 65 inclusive."""
    if age < 18 or age >= 65:
        return False
    return True  # BUG STILL PRESENT

def get_user_profile(user_id):
    """Fetch a user profile by ID."""
    user = _lookup_user(user_id)
    return {"name": user["name"], "id": user["id"]}  # BUG STILL PRESENT (crashes on None)
```

**Key Changes**:
- Docstrings neutralized (no mention of bugs - so agent can't cheat)
- `get_user_profile` now returns `{"name": user["name"], "id": user["id"]}` instead of `user.name`
  - This makes the function work for known users (user_id=1) but still crashes for unknown users (TypeError on None["name"])
- `_lookup_user` unchanged (returns dict or None)

**Assessment**: ✅ Correct - bugs remain in source, docstrings are neutral

#### 2. `seeded-demo-repo/tests/test_app.py` - Baseline Tests (7 tests, all green)

**Before**: 4 tests designed to FAIL with bugs present
**After**: 7 tests that PASS with bugs present:

```python
def test_bigger_discount_gives_lower_price():
    assert calculate_discount(100, 50) < calculate_discount(100, 10)

def test_discount_scales_with_price():
    assert calculate_discount(200, 10) > calculate_discount(100, 10)

def test_validate_age_accepts_adult():
    assert validate_age(30) is True

def test_validate_age_accepts_18():
    assert validate_age(18) is True

def test_validate_age_rejects_minor():
    assert validate_age(17) is False

def test_validate_age_rejects_over_65():
    assert validate_age(66) is False

def test_get_user_profile_returns_known_user():
    assert get_user_profile(1) == {"name": "Alice", "id": 1}
```

**Assessment**: ✅ Correct - all 7 tests pass with bugs present. The tests are "neutral" - they test general behavior, not the specific bug scenarios.

#### 3. `seeded-demo-repo/README.md` - Neutralized

**Before**: Listed bugs, known fixes, issue labeling instructions
**After**: Neutral description, no bug list, no known fixes, generic issue reporting instructions

**Assessment**: ✅ Correct - prevents the agent from "cheating" by reading the README

#### 4. `scripts/demo/reference/test_issue_{1,2,3}.py` - Reference Tests (New)

Three manual reproduction tests that prove each bug exists:
- `test_issue_1.py`: `calculate_discount(100, 20) == 80` → FAILS pre-fix, PASSES post-fix
- `test_issue_2.py`: `validate_age(65) is True` → FAILS pre-fix, PASSES post-fix
- `test_issue_3.py`: `get_user_profile(999) is None` → FAILS pre-fix (TypeError), PASSES post-fix

**Assessment**: ✅ Correct - these prove the bugs are real and reproducible

#### 5. `scripts/demo/verify_seeded_repo.py` - Verification Script (79 lines)

Proves on a temporary copy:
1. Baseline suite is green with bugs present
2. For each bug: reference test fails before fix (red)
3. For each bug: buggy line found exactly once
4. For each bug: reference test passes after fix (green)
5. For each bug: full suite green after fix

**Known fixes applied by the script**:
- Bug 1: `return price - discount + 1` → `return price - discount`
- Bug 2: `if age < 18 or age >= 65:` → `if age < 18 or age > 65:`
- Bug 3: `user = _lookup_user(user_id)` → `user = _lookup_user(user_id)\n    if user is None:\n        return None`

**Assessment**: ✅ Correct - 13 checks, all passed

#### 6. `docs/19-seeded-demo-reference.md` - Single Source of Truth (96 lines)

Contains:
- What the agent sees vs what stays here (table)
- The three bugs (table with reproduce, expected, actual, known fix, demo outcome)
- Verify instructions
- GitHub issue text for all 3 issues (exact titles and bodies)
- Open mismatches for other owners (Durgesh's demo_bugs, langgraph.py, conftest_bugs.py)

**Assessment**: ✅ Correct - comprehensive reference

#### 7. `docs/18-demo-rehearsal-t33.md` - Updated

- Added reference to docs/19 for exact issue text
- Added verify step: `python scripts/demo/verify_seeded_repo.py`
- Updated issue numbers (#1, #4, #5 instead of #1, #2, #3)

#### 8. `docs/12-project-board-setup.md` - Updated

- T-17 status changed from "Done" to "In Progress (baseline-green rework, see docs/19)"

---

## Commit 2: `4146744` - Use Real Demo Issue Numbers

### Changes (2 files, 23 insertions, 13 deletions)

- Issue numbers are #1, #4, #5 (not #1, #2, #3 because #2 and #3 on the repo are pull requests)
- docs/18 and docs/19 updated with correct issue numbers
- Reference test file names follow bug number, not issue number

---

## Guide Alignment Check

### ✅ Guide Requirements (Section F - You/QA):
- "Create three demo issues with simple, deterministic details: (1) off-by-one in calculate_discount; (2) wrong boundary condition in validate_age; (3) missing null check in get_user_profile" ✅
- "Make the third issue intentionally too thin to reproduce honestly" ✅
- "Verify existing pytest suite. green." ✅ (baseline tests now pass)
- "Ask Yash/GitHub integration to push and open draft PR" ✅

### ✅ Non-Negotiable Product Rules:
- "MVP is Python + pytest only" ✅ (standard library only)
- "Use the prepared seeded demo repository" ✅
- "The agent opens draft PRs only; it never merges" ✅ (documented in README)

### ✅ Team Execution Guide Section 7F:
- "Create three demo issues with simple, deterministic details" ✅
- "Make the third issue intentionally too thin to reproduce honestly" ✅
- "Rehearse the full three-issue demo. Confirm two red-to-green draft PRs and the honest failure for the third" ✅

---

## Cross-Team Requirements Check

### ✅ Durgesh (AI Agent) Requirements:
- The agent's `write_reproduction_test` node needs to generate tests that prove the bug
- The agent's `Verify` step requires the existing suite to stay green
- The baseline tests now pass with bugs present, so the Verify gate can work
- **Open mismatch noted in docs/19**: Durgesh's `langgraph.py` has hardcoded tests that import `calculate_discount`/`validate_age`/`get_user_profile` as top-level modules and assert `validate_age(18)`. The seeded repo exposes `src/app.py` and the boundary bug is at 65. Durgesh needs to align.
- **Open mismatch noted**: `apps/api/demo_bugs/*` has different formulas and boundary. Durgesh needs to align.

### ✅ Yash (Backend) Requirements:
- The webhook creates a run and calls `app.state.pipeline_queue` (still None)
- The sandbox runs tests in Docker with `--network=none`
- The agent branch is pushed and draft PR opened
- No changes needed from Yash for this PR

### ✅ Subhi (Frontend) Requirements:
- Dashboard shows all 3 runs and their timeline
- SSE client renders 6 steps
- Red/green test output displayed
- No changes needed from Subhi for this PR

### ✅ You (QA/Lead) Requirements:
- "Create three demo issues with simple, deterministic details" ✅
- "Make the third issue intentionally too thin to reproduce honestly" ✅
- "Rehearse the full three-issue demo" ✅ (verify_seeded_repo.py proves demo-ready)
- "Recorded backup run ready" ✅ (documented in 18-demo-rehearsal-t33.md)

---

## Key Architectural Insight

### Why the Rework Was Necessary

**Problem**: The original seeded repo had reproduction tests that FAIL with bugs present. The "Verify" gate requires:
1. New reproduction test passes after fix ✅
2. Full existing suite stays green ✅

But if the existing suite is red before the fix, condition 2 can never be satisfied. The agent would always fail the Verify gate.

**Solution**: Split into two layers:
1. **Baseline suite** (in seeded repo): 7 tests that pass with bugs present. The Verify gate checks these stay green.
2. **Reference tests** (in main repo): Prove each bug exists (red before fix, green after fix). The agent generates its own reproduction test during the pipeline.

This is a **correct architectural decision** that ensures the demo can actually work.

### Why `get_user_profile` Was Changed

**Before**: `return user.name` (crashes for both known and unknown users)
**After**: `return {"name": user["name"], "id": user["id"]}` (works for known users, crashes for unknown users with TypeError)

The change makes the function:
- Work for known users (user_id=1) → returns `{"name": "Alice", "id": 1}`
- Crash for unknown users (user_id=999) → `None["name"]` → TypeError

This is the correct bug for the demo:
- Bug 3 is "missing null check" → the function crashes when user is None
- The reference test proves this: `get_user_profile(999)` → TypeError (red before fix)
- After fix (`if user is None: return None`): `get_user_profile(999)` → None (green after fix)
- The baseline test `get_user_profile(1) == {"name": "Alice", "id": 1}` passes with the bug present

---

## Assessment

### ✅ Correct and Well-Designed
1. **Baseline green approach**: Solves the fundamental problem of Verify gate requiring green suite
2. **Reference tests**: Prove bugs are real and reproducible
3. **verify_seeded_repo.py**: Automated verification on temp copy (no repo modification)
4. **docs/19**: Single source of truth, keeps answers out of seeded repo
5. **Neutral README**: Prevents agent from "cheating"
6. **Docstrings neutralized**: No hints about bugs in source code
7. **Issue numbers corrected**: #1, #4, #5 (real GitHub issue numbers)

### ⚠️ Open Mismatches for Other Owners (Documented in docs/19)

| File | Owner | Mismatch | Action Needed |
|------|-------|----------|---------------|
| `apps/api/demo_bugs/*` | Durgesh | Different formulas and boundary | Align with seeded repo |
| `apps/api/pipeline/langgraph.py` (`write_reproduction_test`) | Durgesh | Hardcoded tests import as top-level, assert `validate_age(18)` | Align with seeded repo (src/app.py, boundary at 65) |
| `apps/api/tests/fixtures/conftest_bugs.py` | Durgesh | Same definitions as demo_bugs | Align with seeded repo |

**These mismatches are correctly documented but NOT fixed in this PR** - they require Durgesh to update his code.

### ⚠️ Minor Issues
1. **Encoding**: Uses `???` instead of `—` (consistent with other PRs)
2. **T-17 status**: Changed to "In Progress (baseline-green rework, see docs/19)" - should be updated to "Done" after merge
3. **docs/19 mentions "Last result (local, 2026-11-11): 13 checks, all passed"** - should be verified after merge

---

## Verdict: ✅ APPROVED

This PR is a **significant and correct improvement** to the seeded demo repo. It solves the fundamental problem of the Verify gate requiring a green baseline suite, while still proving the bugs are real and reproducible through reference tests.

### Key Strengths:
1. **Smart architecture**: Splitting baseline (green) from reference (red→green) is the right approach
2. **Automated verification**: `verify_seeded_repo.py` proves demo-readiness on every run
3. **Documentation**: `docs/19` is a comprehensive single source of truth
4. **Cross-team awareness**: Open mismatches with Durgesh are documented, not ignored
5. **Neutral code**: README and docstrings don't leak bug information to the agent

### Required Actions from Other Team Members:
- **Durgesh**: Align `apps/api/demo_bugs/*`, `langgraph.py` (write_reproduction_test), and `conftest_bugs.py` with the seeded repo's actual bugs and module structure (`src/app.py`, boundary at 65)

### Minor Recommendations:
1. Fix `???` → `—` encoding
2. Update T-17 status to "Done" after merge
3. Verify `verify_seeded_repo.py` passes after merge (13 checks, all passed)