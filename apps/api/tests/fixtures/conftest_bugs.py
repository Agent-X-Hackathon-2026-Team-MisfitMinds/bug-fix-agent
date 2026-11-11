"""Fixtures for Bug-Fix Agent integration tests.

Provides demo repo structure, bug instances, and test data for
integration testing of the LangGraph pipeline.
"""

from demo_bugs.calculations.calculations import calculate_discount
from demo_bugs.profiles.get_user_profile import get_user_profile
from demo_bugs.validation.validate_age import validate_age


# Demo repo metadata
DEMO_REPO_INFO = {
    "name": "bug-fix-agent-demo",
    "language": "python",
    "bugs": [
        {
            "id": 1,
            "name": "off_by_one_in_calculate_discount",
            "function": "calculate_discount",
            "description": "Off-by-one error in discount calculation formula",
            "bug_type": "off-by-one",
            "file": "apps/api/demo_bugs/calculations/calculations.py",
        },
        {
            "id": 2,
            "name": "wrong_boundary_in_validate_age",
            "function": "validate_age",
            "description": "Wrong boundary condition: age 18 rejected when it should be accepted",
            "bug_type": "wrong-boundary",
            "file": "apps/api/demo_bugs/validation/validate_age.py",
        },
        {
            "id": 3,
            "name": "missing_null_check_in_get_user_profile",
            "function": "get_user_profile",
            "description": "No null guard: None user_id causes TypeError instead of returning None",
            "bug_type": "missing-null-check",
            "file": "apps/api/demo_bugs/profiles/get_user_profile.py",
        },
    ],
}


# Bug 1: Off-by-one test data
CALCULATION_TEST_DATA = {
    "price": 100.0,
    "percentage": 10.0,
    "buggy_result": calculate_discount(100.0, 10.0),  # Will be wrong
    "correct_result": 90.0,  # 100 * (1 - 10/100)
    "expected_formula": "price * (1 - percentage / 100)",
}


# Bug 2: Wrong boundary test data
VALIDATE_AGE_TEST_DATA = {
    "age": 18,
    "buggy_result": validate_age(18),  # Will be False (wrong boundary)
    "correct_result": True,  # age >= 18 should be True
    "expected_formula": "age >= 18",
}


# Bug 3: Missing null check test data
GET_USER_PROFILE_TEST_DATA = {
    "user_id": None,
    "buggy_result": get_user_profile(None),  # Will crash or return None incorrectly
    "correct_result": None,  # Should return None
    "expected_formula": "if user_id is None: return None",
}


# Valid user profiles for integration tests
VALID_PROFILES = {
    1: {"id": 1, "name": "User 1", "email": "user1@example.com"},
    2: {"id": 2, "name": "User 2", "email": "user2@example.com"},
    42: {"id": 42, "name": "User 42", "email": "user42@example.com"},
    100: {"id": 100, "name": "User 100", "email": "user100@example.com"},
}


# Invalid (None) user input
INVALID_INPUTS = [None, "", -1, -100]


# Reproduction test scripts (as strings - to be written to temp files by pipeline)
REPRODUCTION_TEST_SCRIPTS = {
    "calculate_discount": '''"\"\"\"Reproduction test for off-by-one bug in calculate_discount.\"\"\"
def test_calculate_discount_off_by_one():
    from demo_bugs.calculations.calculations import calculate_discount
    result = calculate_discount(100, 10)
    # Buggy: returns wrong value due to off-by-one formula
    # Correct: should be 90.0
    assert result == 90.0, f"Expected 90.0, got {result}"
''',
    "validate_age": '''"\"\"\"Reproduction test for wrong boundary bug in validate_age.\"\"\"
def test_validate_age_wrong_boundary():
    from demo_bugs.validation.validate_age import validate_age
    result = validate_age(18)
    # Buggy: returns False due to age > 18 instead of age >= 18
    # Correct: should be True for age 18
    assert result == True, f"Expected True for age 18, got {result}"
''',
    "get_user_profile": '''"\"\"\"Reproduction test for missing null check bug in get_user_profile.\"\"\"
def test_get_user_profile_null_check():
    from demo_bugs.profiles.get_user_profile import get_user_profile
    result = get_user_profile(None)
    # Buggy: raises TypeError due to missing null check
    # Correct: should return None
    assert result is None, f"Expected None, got {result}"
''',
}