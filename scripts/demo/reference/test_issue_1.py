"""Manual reproduction test for demo issue 1: off-by-one in calculate_discount.

Not part of the seeded repo's suite. Copy into its tests/ folder to reproduce.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app import calculate_discount


def test_calculate_discount_returns_exact_discount():
    result = calculate_discount(100, 20)
    assert result == 80, f"Expected 80, got {result}"
