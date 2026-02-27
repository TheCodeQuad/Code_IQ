class User:
    """
    Represents a system user.

    This class stores user-related information and provides utility
    methods to validate user state.

    Attributes:
        name (str): The name of the user.
        age (int): The age of the user.

    Examples:
        >>> user = User("Alice", 25)
        >>> user.is_adult()
        True
    """

    def __init__(self, name: str, age: int):
        """
        Initializes a new User.

        Args:
            name (str): The name of the user.
            age (int): The age of the user.
        """
        self.name = name
        self.age = age

    def is_adult(self) -> bool:
        """
        Checks if the user is an adult.

        Returns:
            bool: True if age >= 18, otherwise False.

        Examples:
            >>> user.is_adult()
            True
        """
        return self.age >= 18