"""Manual reproduction test for demo issue 2: wrong boundary in validate_age.

Not part of the seeded repo's suite. Copy into its tests/ folder to reproduce.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app import validate_age


def test_validate_age_accepts_65():
    assert validate_age(65) is True, "Age 65 is inside the inclusive range 18-65"
