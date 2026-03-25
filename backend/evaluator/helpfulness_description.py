# evaluator/helpfulness_description.py
# Evaluates the quality of the description section in docstrings.

import re
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    from backend.evaluator.evaluation_common import ScoreLevel
except ImportError:
    from evaluator.evaluation_common import ScoreLevel


class DescriptionAspect(Enum):
    MOTIVATION       = "motivation"
    USAGE_SCENARIOS  = "usage_scenarios"
    INTEGRATION      = "integration"
    FUNCTIONALITY    = "functionality"


@dataclass
class AspectCriteria:
    description:    str
    score_criteria: Dict[ScoreLevel, str]
    example_good:   str
    example_poor:   str


class DocstringDescriptionEvaluator:
    """
    Evaluates the quality of docstring description sections across 4 aspects:
    motivation, usage scenarios, system integration, and functionality.

    Attributes:
        criteria (Dict): Aspect-level evaluation criteria.
    """

    def __init__(self):
        self.criteria = self._initialize_criteria()

    def _initialize_criteria(self) -> Dict[DescriptionAspect, AspectCriteria]:
        return {
            DescriptionAspect.MOTIVATION: AspectCriteria(
                description="How well does the description explain the reason or motivation behind the code?",
                score_criteria={
                    ScoreLevel.POOR:      "No explanation of why the code exists or its purpose",
                    ScoreLevel.FAIR:      "Basic purpose stated but without context or reasoning",
                    ScoreLevel.GOOD:      "Clear explanation of purpose with some context",
                    ScoreLevel.VERY_GOOD: "Thorough explanation of purpose with business/technical context",
                    ScoreLevel.EXCELLENT: "Comprehensive explanation of purpose, context, and value proposition",
                },
                example_good=(
                    "This cache manager addresses the performance bottleneck in our API "
                    "responses by reducing database load during peak hours, while ensuring "
                    "data freshness for critical operations."
                ),
                example_poor="This is a cache manager for storing data.",
            ),
            DescriptionAspect.USAGE_SCENARIOS: AspectCriteria(
                description="How effectively does it describe when and how to use the code?",
                score_criteria={
                    ScoreLevel.POOR:      "No information about usage scenarios",
                    ScoreLevel.FAIR:      "Basic usage information without specific scenarios",
                    ScoreLevel.GOOD:      "Some key usage scenarios described",
                    ScoreLevel.VERY_GOOD: "Detailed usage scenarios with common cases",
                    ScoreLevel.EXCELLENT: "Comprehensive coverage of use cases, including edge cases",
                },
                example_good=(
                    "Use this validator when processing user-submitted data, especially "
                    "for high-stakes operations like financial transactions. Handles "
                    "edge cases including partial submissions and legacy formats."
                ),
                example_poor="Validates data according to rules.",
            ),
            DescriptionAspect.INTEGRATION: AspectCriteria(
                description="How well does it explain integration with other system components?",
                score_criteria={
                    ScoreLevel.POOR:      "No mention of system integration",
                    ScoreLevel.FAIR:      "Minimal reference to other components",
                    ScoreLevel.GOOD:      "Basic explanation of main interactions",
                    ScoreLevel.VERY_GOOD: "Clear description of integration points and dependencies",
                    ScoreLevel.EXCELLENT: "Comprehensive overview of system interactions and data flow",
                },
                example_good=(
                    "This service interfaces with the UserAuth system for validation, "
                    "writes logs to CloudWatch, and triggers notifications through SNS."
                ),
                example_poor="Processes data and sends it to other services.",
            ),
            DescriptionAspect.FUNCTIONALITY: AspectCriteria(
                description="How clearly does it explain the functionality without excessive technical detail?",
                score_criteria={
                    ScoreLevel.POOR:      "No explanation of functionality",
                    ScoreLevel.FAIR:      "Overly technical or vague explanation",
                    ScoreLevel.GOOD:      "Basic explanation of main functionality",
                    ScoreLevel.VERY_GOOD: "Clear, balanced explanation of functionality",
                    ScoreLevel.EXCELLENT: "Perfect balance of clarity and technical detail",
                },
                example_good=(
                    "Processes incoming customer data by first validating format and required fields, "
                    "then enriching with historical data, and finally generating risk scores."
                ),
                example_poor="Processes data using various functions and algorithms.",
            ),
        }

    def get_evaluation_prompt(self, code_implementation: str, docstring: str, eval_type: str = None) -> str:
        """
        Generate a prompt for LLM evaluation of a description section.

        Args:
            code_implementation: The full source code.
            docstring: The docstring to evaluate.
            eval_type: 'class', 'function', or 'method'. Auto-detected if None.

        Returns:
            str: Formatted prompt string.
        """
        if eval_type is None:
            if code_implementation.strip().startswith("class "):
                eval_type = "class"
            else:
                eval_type = "function" if "self" not in code_implementation.split("(")[0] else "method"

        description = self._extract_description(docstring)
        if not description:
            return "The docstring does not have a description section to evaluate."

        prompt = [
            "# Docstring Description Evaluation",
            "",
            "## Code Component",
            "```python",
            code_implementation,
            "```",
            "",
            "## Description to Evaluate",
            "```",
            description,
            "```",
            "",
            "## Evaluation Criteria",
            "Evaluate across these four aspects:",
            "",
        ]

        for aspect in DescriptionAspect:
            c = self.criteria[aspect]
            prompt.extend([
                f"### {aspect.value.title()}",
                c.description,
                "",
                "Score levels:",
            ])
            for level in ScoreLevel:
                prompt.append(f"{level.value}. {c.score_criteria[level]}")
            prompt.extend([
                "",
                f"Good example: \"{c.example_good}\"",
                f"Poor example: \"{c.example_poor}\"",
                "",
            ])

        prompt.extend([
            "## Output Format",
            "```",
            "Motivation: [1-5]",
            "Usage Scenarios: [1-5]",
            "Integration: [1-5]",
            "Functionality: [1-5]",
            "",
            "Overall: [average rounded to integer]",
            "",
            "Suggestions: [2-3 concrete improvements]",
            "```",
        ])

        return "\n".join(prompt)

    def parse_llm_response(self, response: str) -> Tuple[int, str]:
        """
        Extract overall score and suggestions from LLM response.

        Args:
            response: Full LLM response text.

        Returns:
            Tuple of (score 1-5, suggestion string).
        """
        if "does not have a description section" in response:
            return 3, "Add a description section to the docstring."

        score = 3
        overall_match = re.findall(r"Overall:\s*\[?(\d)", response, re.IGNORECASE)
        if overall_match:
            score = int(overall_match[0])

        suggestion = "Consider adding more detail to the description section."
        for pattern in [
            r"Suggestions:\s*(.+?)(?:\n\n|\Z)",
            r"<suggestions>(.*?)</suggestions>",
        ]:
            matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
            if matches:
                suggestion = matches[0].strip()
                break

        return score, suggestion

    def _extract_description(self, docstring: str) -> str:
        """Extract description part from docstring (after summary, before sections)."""
        if not docstring:
            return ""

        lines = [l.strip() for l in docstring.strip().split("\n")]
        if not lines:
            return ""

        lines = lines[1:]  # skip summary

        section_markers = [
            "Args:", "Parameters:", "Arguments:", "Returns:",
            "Raises:", "Yields:", "Examples:", "@param", "@return",
        ]

        description_lines = []
        for line in lines:
            if any(line.strip().startswith(m) for m in section_markers):
                break
            description_lines.append(line)

        return "\n".join(description_lines).strip()