# evaluator/helpfulness_attributes.py
#
# Evaluates the quality of docstring Attributes sections in class docstrings.
# Checks whether attribute descriptions go beyond type hints to explain
# lifecycle, initialization patterns, and relationships with class behavior.
#
# Only runs for class components that have an Attributes section.

import re
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass

try:
    from backend.evaluator.evaluation_common import ScoreLevel
except ImportError:
    from evaluator.evaluation_common import ScoreLevel


@dataclass
class AttributeEvaluationExample:
    """Stores an example of attribute evaluation with different quality levels."""
    class_signature:  str
    init_function:    str
    attributes:       Dict[str, str]
    quality_examples: Dict[ScoreLevel, Dict[str, str]]
    explanations:     Dict[ScoreLevel, str]


class DocstringAttributeEvaluator:
    """
    Evaluates the quality of docstring Attributes sections in class docstrings.

    Assesses how well attribute descriptions convey purpose, lifecycle,
    and usage context beyond mere type information.

    Attributes:
        criteria (Dict): Evaluation criteria per score level.
        examples (List): Concrete examples at each quality level.
    """

    def __init__(self):
        self.criteria = self._initialize_criteria()
        self.examples = self._initialize_examples()

    def _initialize_criteria(self) -> Dict[str, Any]:
        return {
            "description": (
                "Evaluate how effectively the attribute descriptions convey the purpose, "
                "lifecycle, and usage context of class attributes. High-quality descriptions "
                "should go beyond type information to provide meaningful guidance about "
                "attribute roles, initialization, modification patterns, and relationships "
                "with class behavior."
            ),
            "score_criteria": {
                ScoreLevel.POOR: (
                    "The attribute descriptions merely restate the attribute types or "
                    "convert the type hints to natural language without adding any "
                    "meaningful information about purpose or lifecycle."
                ),
                ScoreLevel.FAIR: (
                    "The descriptions provide basic information about attribute purpose "
                    "but lack details about initialization, modification, or usage patterns."
                ),
                ScoreLevel.GOOD: (
                    "The descriptions explain attribute purpose and include some key "
                    "information about initialization or usage patterns, but might miss "
                    "important lifecycle details or relationships with class behavior."
                ),
                ScoreLevel.VERY_GOOD: (
                    "The descriptions clearly explain purpose, initialization, and common "
                    "usage patterns. They note important relationships with class methods "
                    "and document any special handling or constraints."
                ),
                ScoreLevel.EXCELLENT: (
                    "The descriptions provide comprehensive guidance including purpose, "
                    "initialization, modification patterns, relationships with class behavior, "
                    "and any special considerations like thread-safety or constraints."
                ),
            },
        }

    def _initialize_examples(self) -> List[AttributeEvaluationExample]:
        return [
            AttributeEvaluationExample(
                class_signature="class DataProcessor:",
                init_function="""def __init__(self, config: Dict[str, Any]):
    self.config = config
    self.data_cache = {}
    self.is_initialized = False
    self.stats = defaultdict(int)
    self._lock = threading.Lock()""",
                attributes={
                    "config":         "Configuration settings for the processor",
                    "data_cache":     "Cache for processed data",
                    "is_initialized": "Whether the processor is initialized",
                    "stats":          "Processing statistics",
                    "_lock":          "Thread synchronization lock",
                },
                quality_examples={
                    ScoreLevel.POOR: {
                        "config":         "Dictionary of configuration",
                        "data_cache":     "Dictionary for cache",
                        "is_initialized": "Boolean flag",
                        "stats":          "Dictionary of statistics",
                        "_lock":          "Threading lock object",
                    },
                    ScoreLevel.FAIR: {
                        "config":         "Configuration settings for processing",
                        "data_cache":     "Cache storage for processed items",
                        "is_initialized": "Tracks initialization status",
                        "stats":          "Counts of processed items",
                        "_lock":          "Lock for thread safety",
                    },
                    ScoreLevel.GOOD: {
                        "config":         "Configuration dictionary controlling processing behavior. Set at initialization",
                        "data_cache":     "Cache of processed items to avoid recomputation. Cleared with reset()",
                        "is_initialized": "Flag indicating if setup() has been called successfully",
                        "stats":          "Counters tracking number of items processed, errors, cache hits",
                        "_lock":          "Thread lock ensuring thread-safe access to shared resources",
                    },
                    ScoreLevel.VERY_GOOD: {
                        "config":         "Configuration dictionary controlling processing behavior. Set at initialization and accessed by all processing methods. Read-only after initialization",
                        "data_cache":     "Cache of processed items to avoid recomputation. Cleared with reset(). Keys are item IDs, values are processed results",
                        "is_initialized": "Flag indicating if setup() has been called successfully. Methods will raise RuntimeError if called before initialization",
                        "stats":          "Counters tracking processing metrics. Updated by process() and reset by clear_stats()",
                        "_lock":          "Thread lock ensuring thread-safe access to cache and stats. Used internally by all public methods",
                    },
                    ScoreLevel.EXCELLENT: {
                        "config":         "Configuration dictionary controlling processing behavior. Set at initialization, read-only after. Must contain 'batch_size' and 'max_cache_size' keys. See CONFIG_SCHEMA for full spec",
                        "data_cache":     "Cache of processed items. Keys are item IDs, values are results. Limited to max_cache_size with LRU eviction. Thread-safe via _lock",
                        "is_initialized": "True after setup() completes successfully, False after reset(). Methods raise RuntimeError if False. Thread-safe via _lock",
                        "stats":          "Processing metrics counters. Updated by process(), reset by clear_stats(). Use get_stats() for thread-safe snapshot",
                        "_lock":          "Reentrant thread lock for cache and stats. Used by all public methods. Consider async methods for high-concurrency scenarios",
                    },
                },
                explanations={
                    ScoreLevel.POOR:      "Merely restates attribute types without adding value",
                    ScoreLevel.FAIR:      "Basic purpose but lacks lifecycle and usage guidance",
                    ScoreLevel.GOOD:      "Initialization context present but lifecycle details incomplete",
                    ScoreLevel.VERY_GOOD: "Clear purpose, initialization, usage patterns with thread-safety",
                    ScoreLevel.EXCELLENT: "Comprehensive: constraints, thread-safety, practical usage tips",
                },
            )
        ]

    def get_evaluation_prompt(
        self,
        class_signature: str,
        init_function: str,
        attribute_descriptions: Dict[str, str],
    ) -> str:
        """
        Generate a prompt for LLM evaluation of attribute descriptions.

        Args:
            class_signature: The complete class signature line.
            init_function: The __init__ method source code.
            attribute_descriptions: Dict mapping attribute name to description.

        Returns:
            str: Formatted prompt string.
        """
        example = self.examples[0]

        prompt = [
            "Evaluate the following Python docstring attribute descriptions based on these criteria:",
            "",
            "<class_info>",
            f"Class signature:\n{class_signature}",
            "",
            f"Init function:\n{init_function}",
            "</class_info>",
            "",
            "<attributes_to_evaluate>",
            "Attribute descriptions to evaluate:",
        ]
        for attr, desc in attribute_descriptions.items():
            prompt.append(f"{attr}: {desc}")
        prompt.append("</attributes_to_evaluate>")

        prompt.extend([
            "",
            "<evaluation_criteria>",
            self.criteria["description"],
            "",
            "Score levels:",
        ])
        for level in ScoreLevel:
            prompt.append(f"{level.value}. {self.criteria['score_criteria'][level]}")
        prompt.append("</evaluation_criteria>")

        prompt.extend([
            "",
            "<reference_example>",
            f"Class: {example.class_signature}",
            f"Init:\n{example.init_function}",
            "",
            "Attribute descriptions at different quality levels:",
        ])
        for level in ScoreLevel:
            prompt.extend([
                f"Level {level.value}:",
                *[f"  {attr}: {desc}" for attr, desc in example.quality_examples[level].items()],
                f"Explanation: {example.explanations[level]}",
                "",
            ])
        prompt.append("</reference_example>")

        prompt.extend([
            "",
            "<response_format>",
            "1. Analyze each attribute description's strengths and weaknesses.",
            "2. Compare against the criteria and example quality levels.",
            "3. Provide your score (1-5) enclosed in <score></score> tags.",
            "</response_format>",
            "",
            "Take time to analyze thoroughly. The score should be the last part of your response.",
        ])

        return "\n".join(prompt)

    def parse_llm_response(self, response: str) -> Tuple[int, str]:
        """
        Extract score and analysis from LLM response.

        Args:
            response: Full LLM response text.

        Returns:
            Tuple of (score 1-5, analysis text).

        Raises:
            ValueError: If no valid score found.
        """
        score_matches = re.findall(r"<score>(\d)</score>", response)

        if not score_matches:
            # Fallback: try other patterns
            for pattern in [r"score:\s*(\d)", r"(\d)\s*/\s*5"]:
                matches = re.findall(pattern, response, re.IGNORECASE)
                if matches:
                    score_matches = matches
                    break

        if not score_matches:
            return 3, response.strip()  # default instead of raising

        score = int(score_matches[0])
        if not (1 <= score <= 5):
            score = 3

        analysis = re.sub(r"<score>\d</score>", "", response).strip()
        return score, analysis


# ================================================================
# ATTRIBUTE EXTRACTION HELPER
# ================================================================

def extract_attribute_descriptions(docstring: str) -> Dict[str, str]:
    """
    Extract the Attributes section from a docstring as a dict.

    Supports both Python (Attributes:) and JavaDoc (@field) styles.

    Args:
        docstring: Full docstring text.

    Returns:
        Dict mapping attribute name to its description.
        Empty dict if no Attributes section found.
    """
    if not docstring:
        return {}

    # Python style: Attributes:\n    name: description
    attr_section_match = re.search(
        r"Attributes?:\s*\n(.*?)(?=\n\s*\w+:|$)",
        docstring,
        re.DOTALL | re.IGNORECASE,
    )
    if attr_section_match:
        section = attr_section_match.group(1)
        attrs = {}
        # Match "    name (type): description" or "    name: description"
        for match in re.finditer(
            r"^\s{2,}(\w+)(?:\s*\([^)]*\))?:\s*(.+?)(?=\n\s{2,}\w+|\Z)",
            section,
            re.MULTILINE | re.DOTALL,
        ):
            name = match.group(1).strip()
            desc = " ".join(match.group(2).split())  # normalize whitespace
            attrs[name] = desc
        if attrs:
            return attrs

    # JavaDoc / JSDoc style: @field name description
    java_attrs = {}
    for match in re.finditer(r"@(?:field|var)\s+(\w+)\s+(.+?)(?=@|\Z)", docstring, re.DOTALL):
        java_attrs[match.group(1)] = match.group(2).strip()

    return java_attrs