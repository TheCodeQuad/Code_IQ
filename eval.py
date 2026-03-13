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
        Create a new User for authentication and access control.

        Args:
            name (str): Full display name. Must be a non-empty string,
                        used in logs and UI display.
            age (int): User's age in years. Must be >= 0.
                       Determines access to age-restricted features.
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