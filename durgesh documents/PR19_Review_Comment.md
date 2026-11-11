## Review Comment for PR #19: Seeded Demo Repo (T-17)

**Reviewer**: Durgesh  
**Date**: Nov 10, 2026  
**Status**: ⚠️ Changes Requested

---

### Overall Assessment
The seeded demo repo is well-structured and Bugs 1 and 2 are correctly implemented. However, **Bug 3 has an incomplete fix** that would cause the function to still crash for valid users after the "fix" is applied. Please address the following before merging.

---

### ✅ Approved: Bugs 1 & 2

**Bug 1 - calculate_discount (off-by-one)**:
- Bug correctly implemented: `return price - discount + 1` returns 81 instead of 80
- Known fix is correct: `return price - discount`
- Test correctly encodes expected behavior (80)

**Bug 2 - validate_age (wrong boundary)**:
- Bug correctly implemented: `age >= 65` rejects age 65
- Known fix is correct: change `>=` to `>`
- Test correctly encodes expected behavior (True for age 65)

---

### ⚠️ Changes Required: Bug 3 - get_user_profile (missing null check)

**Issue**: The documented "known fix" is incomplete and would leave the function broken for valid users.

#### Current Code:
```python
def get_user_profile(user_id):
    user = _lookup_user(user_id)
    return user.name  # BUG: crashes if user is None
```

#### Current Helper:
```python
def _lookup_user(user_id):
    users = {1: {"name": "Alice", "id": 1}}
    return users.get(user_id)  # Returns a DICT, not an object
```

#### Documented Fix (in README):
```python
return user.name if user else None
```

#### Problem:
1. `_lookup_user()` returns a **dict** `{"name": "Alice", "id": 1}`, not an object with a `.name` attribute
2. The documented fix `return user.name if user else None` would still crash for `user_id=1` because dicts don't have `.name`
3. The test only covers `user_id=999` (unknown user), so the test would pass but the function would still be broken for valid users
4. README states expected behavior is "returns profile dict" but the code returns `user.name` (a string, not a dict)

#### Required Fix - Option A (Recommended):
Update the function to return the dict or None (matches README's stated expected behavior):
```python
def get_user_profile(user_id):
    user = _lookup_user(user_id)
    return user if user else None
```

#### Required Fix - Option B:
If the intent is to return just the name, update both the code and README:
```python
def get_user_profile(user_id):
    user = _lookup_user(user_id)
    return user.get("name") if user else None
```
And update README: "Expected: returns user name or None if not found"

#### Required Fix - Option C (if keeping current behavior):
Change `_lookup_user` to return an object with `.name` attribute:
```python
from types import SimpleNamespace

def _lookup_user(user_id):
    users = {1: SimpleNamespace(name="Alice", id=1)}
    return users.get(user_id)
```

---

### Additional Recommendations

1. **Add a test for valid user**: Add a test case for `get_user_profile(1)` to verify the function works for known users:
```python
def test_get_user_profile_returns_profile_for_known_user():
    result = get_user_profile(1)
    assert result is not None, "Known user should return a profile"
```

2. **Clarify README expected behavior**: Ensure the README's "Expected: returns profile dict or None if not found" matches the actual implementation.

3. **Update "Known fixes" in README**: Change:
   - From: `get_user_profile`: add null check → `return user.name if user else None`
   - To: `get_user_profile`: add null check → `return user if user else None`

---

### Test Verification

After applying the fix, please verify:
```bash
cd seeded-demo-repo
pip install pytest
pytest tests/ -v
```

All 3 tests should:
- FAIL before the fix (red)
- PASS after the fix (green)

And additionally, `get_user_profile(1)` should return a valid profile (not crash).

---

### Summary
- **Bugs 1 & 2**: ✅ Approved
- **Bug 3**: ⚠️ Changes required - documented fix is incomplete
- **Overall**: Please fix Bug 3 and add a test for valid user before merging

This is actually a great test case for the agent's "honest uncertainty" principle - the agent should detect that the fix is incomplete and report it rather than claiming success.

---

**Please update the PR with the fixes and re-request review.**