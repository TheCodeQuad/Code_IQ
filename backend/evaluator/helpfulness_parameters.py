# evaluator/helpfulness_parameters.py
# Evaluates the quality of docstring parameter descriptions.

import re
from typing import Dict, Any, List, Tuple

try:
    from backend.evaluator.evaluation_common import ScoreLevel, ParameterEvaluationExample
except ImportError:
    from evaluator.evaluation_common import ScoreLevel, ParameterEvaluationExample


class DocstringParametersEvaluator:
    """
    Evaluates the quality of docstring parameter descriptions.

    Checks whether parameter descriptions go beyond type hints to provide
    meaningful guidance about usage, constraints, and valid values.

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
                "Evaluate how effectively the parameter descriptions convey the purpose "
                "and usage of parameters. Good descriptions should explain what the "
                "parameter is used for."
            ),
            "score_criteria": {
                ScoreLevel.POOR:      "Descriptions are missing, wrong, or completely uninformative (e.g., just 'The param').",
                ScoreLevel.FAIR:      "Descriptions exist but are very terse (e.g., just the type restated).",
                ScoreLevel.GOOD:      "Descriptions explain what each parameter is used for in a clear sentence.",
                ScoreLevel.VERY_GOOD: "Descriptions explain purpose AND include constraints, valid values, or usage patterns.",
                ScoreLevel.EXCELLENT: "Comprehensive: purpose, constraints, valid values, edge cases, and behavior impact.",
            },
        }

    def _initialize_examples(self) -> List[ParameterEvaluationExample]:
        return [
            ParameterEvaluationExample(
                parameters={
                    "model_id":    "Numeric identifier for the model",
                    "config":      "Configuration for the run",
                    "train_module": "The training module",
                },
                quality_examples={
                    ScoreLevel.POOR: {
                        "model_id":     "The model_id",
                        "config":       "The config",
                        "train_module": "The module",
                    },
                    ScoreLevel.FAIR: {
                        "model_id":     "An integer ID",
                        "config":       "A dictionary",
                        "train_module": "A module object",
                    },
                    ScoreLevel.GOOD: {
                        "model_id":     "Identifier for the model to use",
                        "config":       "Configuration settings for the run",
                        "train_module": "Module that handles training logic",
                    },
                    ScoreLevel.VERY_GOOD: {
                        "model_id":     "Unique numeric ID for the model. Must be a registered model in the registry",
                        "config":       "Configuration controlling run behavior and resource limits",
                        "train_module": "Module that orchestrates the training workflow and checkpointing",
                    },
                    ScoreLevel.EXCELLENT: {
                        "model_id":     "Unique integer ID (e.g. 1014925). Must exist in registry, raises ModelNotFoundError otherwise",
                        "config":       "Specifies saving intervals, naming formats, and retention. See docs for async options",
                        "train_module": "Manages end-to-end training flow, triggers saves at correct intervals",
                    },
                },
                explanations={
                    ScoreLevel.POOR:      "Just restates parameter name, completely useless",
                    ScoreLevel.FAIR:      "Only mentions type, no purpose",
                    ScoreLevel.GOOD:      "Explains what the parameter is used for - this is acceptable",
                    ScoreLevel.VERY_GOOD: "Adds constraints and context beyond basic purpose",
                    ScoreLevel.EXCELLENT: "Comprehensive: constraints, error cases, and practical details",
                },
            )
        ]

    def get_evaluation_prompt(self, code_component: str, docstring: str, eval_type: str = None) -> str:
        """
        Generate a prompt for LLM evaluation of parameter descriptions.

        Args:
            code_component: The full source code of the function or class.
            docstring: The docstring to evaluate.
            eval_type: 'class', 'function', or 'method'. Auto-detected if None.

        Returns:
            str: Formatted prompt string.
        """
        if eval_type is None:
            if code_component.strip().startswith("class "):
                eval_type = "class"
            else:
                eval_type = "function" if "self" not in code_component.split("(")[0] else "method"

        example = self.examples[0]

        prompt = [
            f"Evaluate the parameter descriptions in a docstring of a {eval_type}.",
            "",
            "<evaluation_criteria>",
            self.criteria["description"],
            "",
        ]
        for level in ScoreLevel:
            prompt.append(f"{level.value}. {self.criteria['score_criteria'][level]}")
        prompt.append("</evaluation_criteria>")

        prompt.extend(["", "<reference_example>", "Parameter descriptions at different quality levels:"])
        for level in ScoreLevel:
            prompt.extend([
                f"Level {level.value}:",
                *[f"  {k}: {v}" for k, v in example.quality_examples[level].items()],
                f"Explanation: {example.explanations[level]}",
                "",
            ])
        prompt.append("</reference_example>")

        prompt.extend([
            "",
            "<original_code_component>",
            code_component,
            "</original_code_component>",
            "",
            "<parameters_to_evaluate>",
            docstring,
            "</parameters_to_evaluate>",
            "",
            "<response_format>",
            "1. Compare against criteria and example levels.",
            "2. Add suggestions in <suggestions></suggestions> tags.",
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
        score = 3
        for pattern in [r"<score>(\d)</score>", r"score:\s*(\d)", r"(\d)\s*/\s*5"]:
            matches = re.findall(pattern, response, re.IGNORECASE)
            if matches:
                s = int(matches[0])
                if 1 <= s <= 5:
                    score = s
                    break

        suggestion = "Consider adding more detailed parameter descriptions."
        for pattern in [
            r"<suggestions>(.*?)</suggestions>",
            r"suggestions?:\s*(.+?)(?:\n\n|\Z)",
        ]:
            matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
            if matches:
                suggestion = matches[0].strip()
                break

        return score, suggestion