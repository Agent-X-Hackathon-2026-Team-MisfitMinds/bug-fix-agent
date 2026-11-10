"""Module with wrong boundary condition in validate_age function."""


def validate_age(age: int) -> bool:
    """Validate if age is within acceptable range.
    
    Wrong boundary bug: age 18 is incorrectly rejected when it should be accepted.
    The valid range should be age >= 18, but implementation rejects age 18.
    """
    # BUG: Should be age >= 18 (adult)
    # But implemented as: age > 18 (rejects 18)
    if age > 18:
        return True
    return False


if __name__ == "__main__":
    import sys
    try:
        age = int(sys.argv[1]) if len(sys.argv) > 1 else 18
        result = validate_age(age)
        print(f"Age: {age}")
        print(f"Valid: {result}")
        print(f"Expected (age >= 18): {age >= 18}")
    except ValueError as e:
        print(f"Error: {e}")