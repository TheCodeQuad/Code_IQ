/**
 * Represents a system user.
 *
 * This class stores user information and provides utility
 * methods to validate user state.
 *
 * @example
 * const user = new User("Alice", 25);
 * user.isAdult();
 */
class User {

    /**
     * Creates a new User.
     *
     * @param {string} name - The name of the user.
     * @param {number} age - The age of the user.
     */
    constructor(name, age) {
        this.name = name;
        this.age = age;
    }

    /**
     * Checks whether the user is an adult.
     *
     * Determines if age is greater than or equal to 18.
     *
     * @returns {boolean} True if adult, otherwise false.
     *
     * @example
     * user.isAdult();
     */
    isAdult() {
        return this.age >= 18;
    }

    /**
 * Updates the user's age.
 *
 * Sets a new age value for the user after validating
 * that the provided value is not negative.
 *
 * @param {number} newAge - The new age value.
 *
 * @throws {Error} If the provided age is negative.
 *
 * @example
 * const user = new User("Alice", 25);
 * user.updateAge(30);
 */
    updateAge(newAge) {
        if (newAge < 0) {
            throw new Error("Age cannot be negative");
        }
        this.age = newAge;
    }
}