"""Unit tests for validate_age wrong boundary bug."""

from demo_bugs.validation.validate_age import validate_age


def test_validate_age_adult_18_should_be_valid():
    """Age 18 should be valid (boundary condition bug: uses > instead of >=)."""
    result = validate_age(18)
    assert result is True, f"Expected True for age 18, got {result}"


def test_validate_age_adult_19_should_be_valid():
    """Age 19 should be valid."""
    result = validate_age(19)
    assert result is True, f"Expected True for age 19, got {result}"


def test_validate_age_adult_20_should_be_valid():
    """Age 20 should be valid."""
    result = validate_age(20)
    assert result is True, f"Expected True for age 20, got {result}"


def test_validate_age_minor_17_should_be_invalid():
    """Age 17 should be invalid (underage)."""
    result = validate_age(17)
    assert result is False, f"Expected False for age 17, got {result}"


def test_validate_age_minor_0_should_be_invalid():
    """Age 0 should be invalid."""
    result = validate_age(0)
    assert result is False, f"Expected False for age 0, got {result}"


def test_validate_age_negative_should_be_invalid():
    """Negative age should be invalid."""
    result = validate_age(-5)
    assert result is False, f"Expected False for age -5, got {result}"