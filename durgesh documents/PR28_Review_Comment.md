## Review: PR #28 - Seeded Demo Repo Baseline Rework (T-17)

**Reviewer**: Durgesh (Project Lead / QA)  
**Date**: Nov 11, 2026  
**Status**: ✅ Approved with Minor Recommendations

---

### Overall Assessment

This PR is a **significant and correct improvement**. It solves the fundamental problem of the Verify gate requiring a green baseline suite, while still proving the bugs are real and reproducible through reference tests. The architecture (baseline green + reference red→green) is the right approach.

---

### ✅ Approved: Key Changes

1. **Baseline tests now pass with bugs present** (7 tests) - Solves the Verify gate problem
2. **Reference tests** in `scripts/demo/reference/` - Prove red→green for each bug
3. **`verify_seeded_repo.py`** - Automated 13-check verification on temp copy
4. **`docs/19`** - Single source of truth, keeps answers out of seeded repo
5. **Neutral README/docstrings** - Prevents agent from "cheating"
6. **Issue numbers corrected** - #1, #4, #5 (real GitHub issue numbers)

---

### ⚠️ Changes Requested

#### 1. Fix `???` encoding (Low priority)
Multiple files use `???` instead of `—` (em-dash). This causes rendering issues.

**Files affected**:
- `docs/18-demo-rehearsal-t33.md`
- `docs/19-seeded-demo-reference.md`
- `README.md` (seeded-demo-repo)

**Fix**: Replace all `???` with `—` in these files.

#### 2. Update T-17 status in project board (Low priority)
`docs/12-project-board-setup.md` shows:
```
| T-17 | Seeded demo repo | In Progress (baseline-green rework, see docs/19) | You (QA) |
```
After this PR merges, update to:
```
| T-17 | Seeded demo repo | Done | You (QA) |
```

#### 3. Verify `verify_seeded_repo.py` passes after merge
The doc says "Last result (local, 2026-11-11): 13 checks, all passed." Please re-run after merge to confirm all 13 checks still pass.

---

### ⚠️ Action Required from Other Team Members

The following files describe **different bugs** than what's in the seeded repo. Their owners need to align them:

| File | Owner | Mismatch | Action Needed |
|------|-------|----------|---------------|
| `apps/api/demo_bugs/*` | **Durgesh** | Different formulas and boundary (`price - price / percentage`, age 18) | Align with seeded repo (`src/app.py`, boundary at 65) |
| `apps/api/pipeline/langgraph.py` (`write_reproduction_test`) | **Durgesh** | Hardcoded tests import `calculate_discount`/`validate_age`/`get_user_profile` as top-level modules and assert `validate_age(18)` | Align with seeded repo module structure (`src/app.py`) and boundary at 65 |
| `apps/api/tests/fixtures/conftest_bugs.py` | **Durgesh** | Same definitions as `demo_bugs` | Align with seeded repo |

**Note**: These are documented in `docs/19-seeded-demo-reference.md` under "Open mismatches for other owners (not edited by the lead)."

---

### 💡 Minor Suggestions (Not Blocking)

1. **Add a test for valid user in baseline**: The baseline test `test_get_user_profile_returns_known_user` checks `get_user_profile(1) == {"name": "Alice", "id": 1}`. This passes with the bug present. Consider adding a test that would fail if the function returned `None` for a known user.

2. **Verify the fix for Bug 3**: The known fix is `if user is None: return None`. But the current code is `return {"name": user["name"], "id": user["id"]}` which crashes on `None["name"]`. The reference test correctly proves this (TypeError before fix, None after fix). ✅ This is correct.

3. **Consider adding `pytest` version pin to seeded repo**: The README says `pip install pytest==8.3.4` but `requirements.txt` doesn't pin pytest. Consider adding `pytest==8.3.4` to `requirements.txt` for consistency.

---

### Summary

| Item | Status |
|------|--------|
| Baseline green approach | ✅ Approved |
| Reference tests (red→green) | ✅ Approved |
| verify_seeded_repo.py (13 checks) | ✅ Approved |
| docs/19 single source of truth | ✅ Approved |
| Neutral README/docstrings | ✅ Approved |
| Issue numbers (#1, #4, #5) | ✅ Approved |
| `???` encoding fix | ⚠️ Requested |
| T-17 status update | ⚠️ Requested |
| Durgesh alignment (demo_bugs, langgraph.py, conftest_bugs.py) | ⚠️ Action required from Durgesh |

**Overall**: ✅ Approved - merge when ready. The minor fixes can be done in a follow-up PR. The Durgesh alignment is a separate task that doesn't block this PR.