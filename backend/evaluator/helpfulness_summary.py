# evaluator/helpfulness_summary.py
# Evaluates the quality of docstring summary lines.

import re
from typing import Dict, Any, List, Tuple

from evaluator.evaluation_common import ScoreLevel, SummaryEvaluationExample


class DocstringSummaryEvaluator:
    """
    Evaluates the quality of docstring summary lines using predefined criteria.

    Checks whether the summary adds real context beyond just restating
    the function signature.

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
                "Evaluate how effectively the one-line summary conveys the purpose "
                "and value of the function/class while providing additional context "
                "beyond what is apparent from the signature."
            ),
            "score_criteria": {
                ScoreLevel.POOR: (
                    "The summary merely restates the function signature in natural "
                    "language or is completely unrelated to the function purpose."
                ),
                ScoreLevel.FAIR: (
                    "The summary provides minimal information beyond the signature, "
                    "perhaps adding one minor detail but failing to convey meaningful context."
                ),
                ScoreLevel.GOOD: (
                    "The summary provides some useful context beyond the signature, "
                    "touching on the 'why' or a key use case, but could be more specific."
                ),
                ScoreLevel.VERY_GOOD: (
                    "The summary effectively communicates both what the function does "
                    "and its higher-level purpose using clear language."
                ),
                ScoreLevel.EXCELLENT: (
                    "The summary excellently balances conciseness with informativeness, "
                    "clearly conveying the function's purpose, value, and context."
                ),
            },
        }

    def _initialize_examples(self) -> List[SummaryEvaluationExample]:
        return [
            SummaryEvaluationExample(
                function_signature=(
                    "def calculate_user_metrics(user_id: str, start_date: datetime, "
                    "end_date: datetime) -> Dict[str, float]"
                ),
                summaries={
                    ScoreLevel.POOR:      "Calculates metrics for a user between two dates.",
                    ScoreLevel.FAIR:      "Processes user metrics data through various calculation methods.",
                    ScoreLevel.GOOD:      "Analyzes user engagement patterns by computing daily interaction statistics.",
                    ScoreLevel.VERY_GOOD: "Generates user engagement insights for quarterly reporting by processing daily interaction metrics.",
                    ScoreLevel.EXCELLENT: "Identifies at-risk users by analyzing engagement patterns against historical churn indicators.",
                },
                explanations={
                    ScoreLevel.POOR:      "Merely converts the function signature into a sentence.",
                    ScoreLevel.FAIR:      "Adds slightly more information but remains vague.",
                    ScoreLevel.GOOD:      "Provides some context but could be more specific.",
                    ScoreLevel.VERY_GOOD: "Communicates both what it does and why (quarterly reporting).",
                    ScoreLevel.EXCELLENT: "Conveys both the technical function and its business purpose.",
                },
            ),
            SummaryEvaluationExample(
                function_signature="class DatasetLoader:",
                summaries={
                    ScoreLevel.POOR:      "A class that loads datasets.",
                    ScoreLevel.FAIR:      "Handles loading of data from various sources.",
                    ScoreLevel.GOOD:      "Provides unified interface for loading and validating datasets.",
                    ScoreLevel.VERY_GOOD: "Streamlines dataset ingestion by providing a consistent interface for loading and validating data.",
                    ScoreLevel.EXCELLENT: "Ensures data quality and consistency by providing a unified interface for loading, validating, and preprocessing datasets across multiple formats.",
                },
                explanations={
                    ScoreLevel.POOR:      "Simply restates the class name.",
                    ScoreLevel.FAIR:      "Adds minimal information.",
                    ScoreLevel.GOOD:      "Provides context about key functionality.",
                    ScoreLevel.VERY_GOOD: "Clearly communicates purpose and value.",
                    ScoreLevel.EXCELLENT: "Balances technical capabilities with practical benefits.",
                },
            ),
        ]

    def get_evaluation_prompt(self, code_component: str, docstring: str, eval_type: str = None) -> str:
        """
        Generate a prompt for LLM evaluation of a docstring summary.

        Args:
            code_component: The full source code of the function or class.
            docstring: The docstring to evaluate.
            eval_type: 'class', 'function', or 'method'. Auto-detected if None.

        Returns:
            str: Formatted prompt string ready to send to LLM.
        """
        if eval_type is None:
            if code_component.strip().startswith("class "):
                eval_type = "class"
            else:
                eval_type = "function" if "self" not in code_component.split("(")[0] else "method"

        is_class = eval_type == "class"
        relevant_example = next(
            e for e in self.examples
            if e.function_signature.startswith("class") == is_class
        )

        prompt = [
            f"Evaluate the summary part of a docstring of a {eval_type} based on these criteria:",
            "",
            "<evaluation_criteria>",
        ]
        for level in ScoreLevel:
            prompt.append(f"{level.value}. {self.criteria['score_criteria'][level]}")
        prompt.append("</evaluation_criteria>")

        prompt.extend([
            "",
            "<reference_example>",
            "Summaries at different quality levels:",
        ])
        for level in ScoreLevel:
            prompt.extend([
                f"Level {level.value}: {relevant_example.summaries[level]}",
                f"Explanation: {relevant_example.explanations[level]}",
                "",
            ])
        prompt.append("</reference_example>")

        prompt.extend([
            "",
            "<original_code_component>",
            code_component,
            "</original_code_component>",
            "",
            "<docstring_to_evaluate>",
            docstring,
            "</docstring_to_evaluate>",
            "",
            "<response_format>",
            "1. Explain your reasoning comparing against the criteria.",
            "2. If applicable, add suggestions in <suggestions></suggestions> tags.",
            "3. Provide your score (1-5) in <score></score> tags.",
            "</response_format>",
        ])

        return "\n".join(prompt)

    def parse_llm_response(self, response: str) -> Tuple[int, str]:
        """
        Extract score and suggestions from LLM response.

        Args:
            response: Full LLM response text.

        Returns:
            Tuple of (score 1-5, suggestion string).
        """
        score = 3  # default
        for pattern in [r"<score>(\d)</score>", r"score:\s*(\d)", r"(\d)\s*/\s*5"]:
            matches = re.findall(pattern, response, re.IGNORECASE)
            if matches:
                s = int(matches[0])
                if 1 <= s <= 5:
                    score = s
                    break

        suggestion = "Consider adding more context and purpose to the summary."
        for pattern in [
            r"<suggestions>(.*?)</suggestions>",
            r"suggestions?:\s*(.+?)(?:\n\n|\Z)",
        ]:
            matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
            if matches:
                suggestion = matches[0].strip()
                break

        return score, suggestion