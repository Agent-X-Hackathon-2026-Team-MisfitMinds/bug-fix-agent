"""Existing test suite for the shop utilities."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app import calculate_discount, get_user_profile, validate_age


def test_bigger_discount_gives_lower_price():
    assert calculate_discount(100, 50) < calculate_discount(100, 10)


def test_discount_scales_with_price():
    assert calculate_discount(200, 10) > calculate_discount(100, 10)


def test_validate_age_accepts_adult():
    assert validate_age(30) is True


def test_validate_age_accepts_18():
    assert validate_age(18) is True


def test_validate_age_rejects_minor():
    assert validate_age(17) is False


def test_validate_age_rejects_over_65():
    assert validate_age(66) is False


def test_get_user_profile_returns_known_user():
    assert get_user_profile(1) == {"name": "Alice", "id": 1}
