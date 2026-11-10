"""Module with off-by-one bug in calculate_discount function."""


def calculate_discount(price: float, percentage: float) -> float:
    """Calculate discount on a price given a percentage.
    
    Off-by-one bug: incorrectly calculates discount by subtracting
    percentage from 100 instead of applying it directly.
    """
    # BUG: Should be price * (1 - percentage / 100)
    # But implemented as: price - (price / percentage) - wrong!
    result = price - (price / percentage)
    return result


if __name__ == "__main__":
    import sys
    try:
        price = float(sys.argv[1]) if len(sys.argv) > 1 else 100.0
        percentage = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
        discount = calculate_discount(price, percentage)
        print(f"Price: {price}, Percentage: {percentage}%")
        print(f"Discounted price: {discount}")
        print(f"Expected: {price * (1 - percentage / 100):.2f}")
    except (ValueError, ZeroDivisionError) as e:
        print(f"Error: {e}")