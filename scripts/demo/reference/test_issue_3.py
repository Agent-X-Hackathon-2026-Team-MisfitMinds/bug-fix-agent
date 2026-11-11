"""Manual reproduction test for demo issue 3: missing null check in get_user_profile.

Not part of the seeded repo's suite. Copy into its tests/ folder to reproduce.
The GitHub issue for this bug is deliberately too thin for the agent, which
must answer "couldn't reproduce". This test is the lead's proof the bug is real.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app import get_user_profile


def test_get_user_profile_returns_none_for_unknown_user():
    result = get_user_profile(999)
    assert result is None, f"Expected None, got {result}"
