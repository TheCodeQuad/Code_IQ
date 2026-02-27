/**
 * Represents a system user.
 *
 * This class stores user-related information and provides
 * utility methods for user validation.
 *
 * @param name The name of the user.
 * @param age The age of the user.
 *
 * @example
 * User user = new User("Alice", 25);
 * boolean result = user.isAdult();
 */
public class User {

    private String name;
    private int age;

    /**
     * Creates a new User instance.
     *
     * @param name The name of the user.
     * @param age The age of the user.
     */
    public User(String name, int age) {
        this.name = name;
        this.age = age;
    }

    /**
     * Checks whether the user is an adult.
     *
     * @return true if age is greater than or equal to 18.
     *
     * @example
     * user.isAdult();
     */
    public boolean isAdult() {
        return age >= 18;
    }
}