"""Module with missing null check in get_user_profile function."""


def get_user_profile(user_id: int | str | None) -> dict[str, object] | None:
    """Get user profile by user ID.
    
    Missing null bug: Does not handle None user_id, causes TypeError.
    Should return None for None input, but crashes instead.
    """
    # BUG: No None check - will raise TypeError if user_id is None
    # Should have: if user_id is None: return None
    profile: dict[str, object] = {
        "id": user_id,
        "name": f"User {user_id}",
        "email": f"user{user_id}@example.com",
    }
    return profile


if __name__ == "__main__":
    import sys
    try:
        user_id = sys.argv[1] if len(sys.argv) > 1 else None
        profile = get_user_profile(user_id)
        print(f"User ID: {user_id}")
        print(f"Profile: {profile}")
    except TypeError as e:
        print(f"TypeError: {e} - Missing null check bug!")