class User:
    """
    Represents an authenticated system user for access control decisions.

    Used throughout the auth pipeline to check permissions and validate
    user state before allowing access to protected resources.

    Attributes:
        name (str): Full display name of the user. Must be non-empty.
        age (int): User's age in years. Must be >= 0.

    Examples:
        >>> user = User("Alice", 25)
        >>> user.is_adult()
        True
    """

    def __init__(self, name: str, age: int):
        """
        Stores user identity and age to enable age-based eligibility checks for protected resources.

        Creates a User instance that holds authentication data and supports
        adult status verification via the is_adult() method using an 18+ threshold.

        Args:
            name: User's full display name or identifier. Must be a non-empty string.
                  Used for logging, UI display, and audit trails throughout the auth pipeline.
            age: User's age in years. Must be a non-negative integer (>= 0).
                 Used to determine adult status (18+ threshold) for gating access to
                 age-restricted content and operations.

        Attributes:
            name (str): The stored display name used for identification.
            age (int): The stored age value used for eligibility checks via is_adult().

        Raises:
            Implicit: No validation is performed. Callers must ensure name is non-empty
                     and age is non-negative to meet the documented contract.
        """
        self.name = name
        self.age = age

    def is_adult(self) -> bool:
        """
        Check if this user is eligible for adult-only features.

        Uses the legal adult threshold (18+) to gate access to
        age-restricted content and operations.

        Returns:
            bool: True if age >= 18, otherwise False.

        Examples:
            >>> user = User("Alice", 25)
            >>> user.is_adult()
            True
        """
        return self.age >= 18