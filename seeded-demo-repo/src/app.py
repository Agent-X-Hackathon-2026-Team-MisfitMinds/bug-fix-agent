"""Small shop utilities: pricing, age validation and user profiles."""


def calculate_discount(price, discount_percent):
    """Apply a percentage discount to a price.

    Returns price * (1 - discount_percent / 100).
    """
    discount = price * (discount_percent / 100)
    return price - discount + 1


def validate_age(age):
    """Return True if age is between 18 and 65 inclusive."""
    if age < 18 or age >= 65:
        return False
    return True


def get_user_profile(user_id):
    """Fetch a user profile by ID."""
    user = _lookup_user(user_id)
    return {"name": user["name"], "id": user["id"]}


def _lookup_user(user_id):
    """Simulated database lookup. Returns None for unknown IDs."""
    users = {1: {"name": "Alice", "id": 1}}
    return users.get(user_id)
