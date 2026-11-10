"""Seeded demo repository with three deterministic bugs for Bug-Fix Agent.

Bug 1: Off-by-one in calculate_discount (calculations module)
Bug 2: Wrong boundary condition in validate_age (validation module)  
Bug 3: Missing null check in get_user_profile (profiles module)

Each bug is designed to be:
- Reproducible inside Docker sandbox
- Fixed with minimal code change
- Verified with passing reproduction test + green full pytest suite
"""

from .calculations import calculate_discount
from .validation import validate_age
from .profiles import get_user_profile

__all__ = ["calculate_discount", "validate_age", "get_user_profile"]