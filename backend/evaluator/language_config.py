# evaluator/language_config.py
# Centralized configuration for all supported languages
# Used by both completeness.py and multilang_completeness.py

LANGUAGE_CONFIG = {
    "python": {
        "comment_prefix": None,  # Python uses string literals as docstrings
        "section_labels": {
            "args": ["args:", "arguments:", "parameters:", "params:"],
            "returns": ["returns:", "return:", "yields:", "yield:"],
            "raises": ["raises:", "exceptions:", "throws:"],
            "examples": ["example:", "examples:", "usage:", "usage example:", "usage examples:"],
            "attributes": ["attributes:", "members:", "member variables:", "instance variables:", "properties:"],
        },
        "void_return_types": [None, "None", ""],
        "exception_keyword": r"\braise\b",
        "return_keyword": r"\breturn\b\s+(?!None\b|\n)",
    },
    "java": {
        "comment_prefix": "/**",
        "section_labels": {
            "args": ["@param"],
            "returns": ["@return"],
            "raises": ["@throws", "@exception"],
            "examples": ["example:", "examples:", "usage:", "@example"],
            "attributes": [],  # Not standard in JavaDoc — covered by @param in constructor
        },
        "void_return_types": [None, "void"],
        "exception_keyword": r"\bthrow\b",
        "return_keyword": r"\breturn\b",
    },
    "javascript": {
        "comment_prefix": "/**",
        "section_labels": {
            "args": ["@param"],
            "returns": ["@returns", "@return"],
            "raises": ["@throws"],
            "examples": ["@example", "example:", "examples:", "usage:"],
            "attributes": ["@property", "@prop", "properties:", "property:", "attributes:", "members:"],
        },
        "void_return_types": [None, "void", "undefined"],
        "exception_keyword": r"\bthrow\b",
        "return_keyword": r"\breturn\b",
    },
    "typescript": {
        "comment_prefix": "/**",
        "section_labels": {
            "args": ["@param"],
            "returns": ["@returns", "@return"],
            "raises": ["@throws"],
            "examples": ["@example", "example:", "examples:"],
            "attributes": ["@property", "@prop", "properties:", "property:", "attributes:", "members:"],
        },
        "void_return_types": [None, "void", "undefined", "never"],
        "exception_keyword": r"\bthrow\b",
        "return_keyword": r"\breturn\b",
    },
}