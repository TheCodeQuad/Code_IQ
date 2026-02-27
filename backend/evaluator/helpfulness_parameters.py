# evaluator/helpfulness_parameters.py
# Evaluates the quality of docstring parameter descriptions.

import re
from typing import Dict, Any, List, Tuple

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
                "Evaluate how effectively the parameter descriptions convey the purpose, "
                "constraints, and usage context of parameters. High-quality descriptions "
                "should go beyond type information to provide meaningful guidance about "
                "parameter usage, valid values, and impact on behavior."
            ),
            "score_criteria": {
                ScoreLevel.POOR:      "Descriptions merely restate the parameter types without adding information.",
                ScoreLevel.FAIR:      "Basic purpose stated but lacks constraints, valid values, or usage context.",
                ScoreLevel.GOOD:      "Explains purpose and some constraints but misses edge cases.",
                ScoreLevel.VERY_GOOD: "Clearly explains purpose, constraints, and common usage patterns.",
                ScoreLevel.EXCELLENT: "Comprehensive: purpose, constraints, examples, edge cases, and behavior impact.",
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
                        "model_id":     "The model ID",
                        "config":       "The config",
                        "train_module": "The training module",
                    },
                    ScoreLevel.FAIR: {
                        "model_id":     "A number that identifies the model",
                        "config":       "Settings for the run",
                        "train_module": "Module that manages training",
                    },
                    ScoreLevel.GOOD: {
                        "model_id":     "Identifier for the model entity in the registry",
                        "config":       "Configuration controlling run behavior and resource limits",
                        "train_module": "Module that implements training logic and checkpointing",
                    },
                    ScoreLevel.VERY_GOOD: {
                        "model_id":     "Unique numeric ID for the model in the registry. Must be a registered model",
                        "config":       "Controls run frequency, storage, and resource constraints. Important for disk usage",
                        "train_module": "Orchestrates training workflow and defines what model components get saved",
                    },
                    ScoreLevel.EXCELLENT: {
                        "model_id":     "Unique integer ID (e.g. 1014925). Must exist in registry before use, otherwise raises ModelNotFoundError",
                        "config":       "Specifies saving intervals, naming formats, and retention. See docs for advanced async options",
                        "train_module": "Manages end-to-end training flow and triggers saves at correct intervals",
                    },
                },
                explanations={
                    ScoreLevel.POOR:      "Recites type info, no usage or constraints",
                    ScoreLevel.FAIR:      "Basic purpose but lacks detail",
                    ScoreLevel.GOOD:      "Core constraints present but some usage details missing",
                    ScoreLevel.VERY_GOOD: "Usage patterns, constraints, and environment needs explained",
                    ScoreLevel.EXCELLENT: "Comprehensive: resource impact, constraints, error cases",
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