"""Unit tests for calculate_discount off-by-one bug."""

from demo_bugs.calculations.calculations import calculate_discount


def test_calculate_discount_correct_formula():
    """Test with correct formula: price * (1 - percentage/100)."""
    result = calculate_discount(100.0, 10.0)
    expected = 100.0 * (1 - 10.0 / 100.0)  # 90.0
    assert result == expected, f"Expected {expected}, got {result}"


def test_calculate_discount_standard_case():
    """Standard discount test case."""
    result = calculate_discount(200.0, 25.0)
    expected = 200.0 * (1 - 25.0 / 100.0)  # 150.0
    assert result == expected, f"Expected {expected}, got {result}"


def test_calculate_discount_zero_percentage():
    """Zero percentage should return original price."""
    result = calculate_discount(100.0, 0.0)
    expected = 100.0  # No discount
    assert result == expected, f"Expected {expected}, got {result}"


def test_calculate_discount_full_percentage():
    """100% discount should return 0."""
    result = calculate_discount(100.0, 100.0)
    expected = 0.0  # Full discount
    assert result == expected, f"Expected {expected}, got {result}"


def test_calculate_discount_edge_case_small_price():
    """Small price edge case."""
    result = calculate_discount(1.0, 50.0)
    expected = 1.0 * (1 - 50.0 / 100.0)  # 0.5
    assert result == expected, f"Expected {expected}, got {result}"