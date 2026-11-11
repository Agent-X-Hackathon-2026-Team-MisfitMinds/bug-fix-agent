"""Unit tests for get_user_profile missing null bug."""

from demo_bugs.profiles.get_user_profile import get_user_profile


def test_get_user_profile_valid_id():
    """Valid user ID should return profile dict."""
    result = get_user_profile(1)
    assert result is not None, "Expected profile dict, got None"
    assert result["id"] == 1, f"Expected id=1, got {result.get('id')}"
    assert result["name"] == "User 1", f"Expected name='User 1', got {result.get('name')}"
    assert result["email"] == "user1@example.com", f"Expected email='user1@example.com', got {result.get('email')}"


def test_get_user_profile_valid_id_42():
    """Another valid user ID."""
    result = get_user_profile(42)
    assert result is not None, "Expected profile dict, got None"
    assert result["id"] == 42, f"Expected id=42, got {result.get('id')}"
    assert result["name"] == "User 42", f"Expected name='User 42', got {result.get('name')}"


def test_get_user_profile_none_returns_none():
    """None user ID should return None (missing null check bug)."""
    result = get_user_profile(None)
    assert result is None, f"Expected None, got {result}"


def test_get_user_profile_empty_string_returns_none():
    """Empty string user ID should return None."""
    result = get_user_profile("")
    assert result is None, f"Expected None for empty string, got {result}"