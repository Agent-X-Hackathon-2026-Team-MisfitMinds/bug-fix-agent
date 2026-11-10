"""Reproduction tests for the seeded demo repository.

Each test encodes expected behaviour. The agent should observe these fail
before the fix and pass after the fix.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app import calculate_discount, validate_age, get_user_profile


def test_calculate_discount_returns_exact_discount():
    """100 with 20% discount should equal 80.

    Bug: off-by-one returns 81 instead of 80.
    """
    result = calculate_discount(100, 20)
    assert result == 80, f"Expected 80, got {result}"


def test_validate_age_accepts_65():
    """Age 65 is within the inclusive range [18, 65].

    Bug: wrong boundary rejects 65 because it uses >= instead of >.
    """
    assert validate_age(65) is True, "Age 65 should be valid"


def test_get_user_profile_returns_none_for_unknown_user():
    """Looking up an unknown user should return None, not crash.

    Bug: missing null check raises AttributeError on None.name.
    """
    result = get_user_profile(999)
    assert result is None, f"Expected None, got {result}"
