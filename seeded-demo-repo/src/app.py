"""Seeded demo repository for the Bug-Fix Agent hackathon demo.

Three deterministic Python bugs are planted here:
1. Off-by-one in calculate_discount
2. Wrong boundary condition in validate_age
3. Missing null check in get_user_profile

Each bug has a corresponding reproduction test in tests/.
"""


def calculate_discount(price, discount_percent):
    """Apply a percentage discount to a price.

    Expected: price * (1 - discount_percent / 100)
    Bug: off-by-one — adds 1 to the result.
    """
    discount = price * (discount_percent / 100)
    return price - discount + 1


def validate_age(age):
    """Return True if age is between 18 and 65 inclusive.

    Expected: 18 <= age <= 65
    Bug: wrong boundary — rejects age 65 (uses >= instead of >).
    """
    if age < 18 or age >= 65:
        return False
    return True


def get_user_profile(user_id):
    """Fetch a user profile by ID.

    Expected: returns profile dict or None if not found
    Bug: missing null check — crashes with AttributeError if user not found.
    """
    user = _lookup_user(user_id)
    return user.name


def _lookup_user(user_id):
    """Simulated database lookup. Returns None for unknown IDs."""
    users = {1: {"name": "Alice", "id": 1}}
    return users.get(user_id)
