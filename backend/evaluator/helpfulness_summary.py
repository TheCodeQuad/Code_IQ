# Copyright (c) Meta Platforms, Inc. and affiliates
from typing import Dict, Any, List, Optional, Tuple
import re
from dataclasses import dataclass
from enum import Enum

from evaluator.evaluation_common import ScoreLevel, SummaryEvaluationExample

class DocstringSummaryEvaluator:
    """
    Evaluates the quality of Python docstring summaries using predefined criteria and examples.
    
    This class provides a structured way to assess how well a docstring's summary line conveys
    the purpose and value of a function or class. It includes detailed criteria for different
    quality levels and concrete examples to guide the evaluation process.
    """

    def __init__(self):
        """Initialize the evaluator with predefined criteria and examples."""
        self.criteria = self._initialize_criteria()
        self.examples = self._initialize_examples()

    def _initialize_criteria(self) -> Dict[str, Any]:
        """
        Set up the evaluation criteria for docstring summaries.
        
        The criteria define five quality levels, from mere signature repetition (1) 
        to excellent context and purpose explanation (5).
        
        Returns:
            Dict containing the evaluation criteria and descriptions for each score level.
        """
        return {
                'description': (
                    'Evaluate how effectively the one-line summary conveys '
                    'the purpose and value of the function/class while providing additional '
                    'context beyond what is apparent from the signature. A high-quality '
                    'summary should be concise yet informative.'
                    ),
                'score_criteria': {
                        ScoreLevel.POOR: (
                            'The summary is completely wrong, misleading, or describes something '
                            'unrelated to what the code actually does. OR the summary is empty/missing.'
                        ),
                        ScoreLevel.FAIR: (
                            'The summary is technically correct but adds almost nothing beyond the name. '
                            'It might be a single word or extremely terse phrase that provides no context.'
                        ),
                        ScoreLevel.GOOD: (
                            'The summary accurately describes what the function/class does in a complete '
                            'sentence. It may restate the name in natural language but is clear and correct. '
                            'This is the baseline for any reasonable docstring summary.'
                        ),
                        ScoreLevel.VERY_GOOD: (
                            'The summary goes beyond describing WHAT to explain WHY or HOW it is used. '
                            'It provides context about when/why to call this function or why this class exists. '
                            'Uses clear language that helps readers understand the purpose.'
                        ),
                        ScoreLevel.EXCELLENT: (
                            'The summary excellently balances conciseness with informativeness, '
                            'clearly conveying the function\'s purpose, value, and context in '
                            'practical developer/system terms (entry point, orchestration, validation, '
                            'dispatching, caching, logging, error contract). For SIMPLE utilities/predicates, '
                            'a precise behavioral contract (including thresholds/units visible in code) can '
                            'still be EXCELLENT.'
                        )
                        }
                }

    def _initialize_examples(self) -> List[SummaryEvaluationExample]:
        """
        Set up concrete examples of docstring summaries at different quality levels.
        
        Each example includes a function signature and corresponding summaries at
        different quality levels, along with explanations of the ratings.
        
        Returns:
            List of SummaryEvaluationExample objects containing the example cases.
        """
        return [
            SummaryEvaluationExample(
                function_signature=(
                    "def calculate_user_metrics(user_id: str, start_date: datetime, "
                    "end_date: datetime) -> Dict[str, float]"
                ),
                summaries={
                    ScoreLevel.POOR: "Does something with data.",
                    ScoreLevel.FAIR: "Calculates metrics.",
                    ScoreLevel.GOOD: "Calculates metrics for a user between two dates.",
                    ScoreLevel.VERY_GOOD: (
                        "Generates user engagement insights for quarterly reporting by "
                        "processing daily interaction metrics."
                    ),
                    ScoreLevel.EXCELLENT: (
                        "Centralizes user-metric computation behind a single entry point so callers can "
                        "request time-windowed engagement statistics without re-implementing aggregation logic."
                    )
                },
                explanations={
                    ScoreLevel.POOR: "Vague and doesn't describe what the function actually does.",
                    ScoreLevel.FAIR: "Too terse - doesn't explain the scope or parameters.",
                    ScoreLevel.GOOD: (
                        "Accurately describes what the function does in a clear sentence. "
                        "This is a valid, helpful summary."
                    ),
                    ScoreLevel.VERY_GOOD: (
                        "This effectively communicates both what it does and why "
                        "(quarterly reporting), giving clear context for its use."
                    ),
                    ScoreLevel.EXCELLENT: (
                        "This conveys system-purpose context (entry point + why callers use it) "
                        "without inventing external business claims."
                    )
                }
            ),
            SummaryEvaluationExample(
                function_signature=(
                    "class DatasetLoader:"
                ),
                summaries={
                    ScoreLevel.POOR: "A class.",
                    ScoreLevel.FAIR: "Loads data.",
                    ScoreLevel.GOOD: "A class that loads datasets from various sources.",
                    ScoreLevel.VERY_GOOD: (
                        "Provides unified interface for loading and validating datasets from multiple sources."
                    ),
                    ScoreLevel.EXCELLENT: (
                        "Ensures data quality and consistency by providing a unified interface "
                        "for loading, validating, and preprocessing datasets across multiple "
                        "formats and sources while handling common edge cases."
                    )
                },
                explanations={
                    ScoreLevel.POOR: "No information about what this class does.",
                    ScoreLevel.FAIR: "Too vague - doesn't explain what kind of data or how.",
                    ScoreLevel.GOOD: (
                        "Clearly describes the class purpose. A basic but valid summary."
                    ),
                    ScoreLevel.VERY_GOOD: (
                        "Clearly communicates purpose and value while highlighting key "
                        "features (unified interface, validation)."
                    ),
                    ScoreLevel.EXCELLENT: (
                        "Excellently balances technical capabilities with practical benefits, "
                        "while highlighting key differentiators and value proposition."
                    )
                }
            )
            ,
            SummaryEvaluationExample(
                function_signature=(
                    "def is_adult(self) -> bool"
                ),
                summaries={
                    ScoreLevel.POOR: "Returns a boolean.",
                    ScoreLevel.FAIR: "Checks age.",
                    ScoreLevel.GOOD: "Determines if the user is an adult.",
                    ScoreLevel.VERY_GOOD: "Returns True when the stored age meets the adult threshold (18+).",
                    ScoreLevel.EXCELLENT: "Reports whether the user's age is at least 18 (the explicit threshold used by this code).",
                },
                explanations={
                    ScoreLevel.POOR: "Doesn't say what the boolean means.",
                    ScoreLevel.FAIR: "Missing context about what is being checked.",
                    ScoreLevel.GOOD: "Clear and accurate description of what the method does.",
                    ScoreLevel.VERY_GOOD: "States the contract clearly with the threshold mentioned.",
                    ScoreLevel.EXCELLENT: "Excellent for a simple predicate: surfaces the non-obvious threshold visible in code.",
                },
            ),
            SummaryEvaluationExample(
                function_signature=(
                    "class User:"
                ),
                summaries={
                    ScoreLevel.POOR: "User class.",
                    ScoreLevel.FAIR: "Stores user data.",
                    ScoreLevel.GOOD: "Represents a user with a name and age.",
                    ScoreLevel.VERY_GOOD: "Holds a user's name and age and exposes an age-threshold check used by calling code.",
                    ScoreLevel.EXCELLENT: "Stores a user's name and age and provides a built-in age >= 18 check for simple eligibility decisions.",
                },
                explanations={
                    ScoreLevel.POOR: "Just restates the class name, no information.",
                    ScoreLevel.FAIR: "Too generic, doesn't explain what user data.",
                    ScoreLevel.GOOD: "Accurately describes what the class holds. A valid summary.",
                    ScoreLevel.VERY_GOOD: "Connects stored state to the provided behavior without inventing external context.",
                    ScoreLevel.EXCELLENT: "Excellent for a simple data holder: states stored fields plus the explicit threshold contract.",
                },
            )
        ]

    def _select_relevant_example(self, code_component: str, eval_type: str) -> SummaryEvaluationExample:
        """Pick a reference example that matches the focal component's shape.

        The evaluator is used across languages; we keep matching heuristic and code-driven.
        """
        src = (code_component or "").strip()

        # Classes: pick a simple DTO-like class example when it looks like mostly assignments.
        if eval_type == "class":
            has_simple_assigns = bool(re.search(r"\bself\.\w+\s*=", src))
            has_methods = bool(re.search(r"\bdef\s+\w+\s*\(", src))
            # If it is a tiny class with assignments and few methods, use the User example.
            if has_simple_assigns and has_methods and len(src.splitlines()) <= 35:
                return next(ex for ex in self.examples if ex.function_signature.startswith("class User"))
            return next(ex for ex in self.examples if ex.function_signature.startswith("class DatasetLoader"))

        # Predicates: explicit comparisons are the key signal for high-value summaries.
        looks_like_predicate = bool(re.search(r"\breturn\b[^\n]*\b(>=|<=|==|!=|>|<)\b", src))
        if looks_like_predicate:
            return next(ex for ex in self.examples if ex.function_signature.startswith("def is_adult"))

        # Default: general function example.
        return next(ex for ex in self.examples if ex.function_signature.startswith("def calculate_user_metrics"))

    def get_evaluation_prompt(self, code_component: str, docstring: str, eval_type: str = None) -> str:
        """
        Generates a prompt for LLM evaluation of docstring summaries.
        
        Args:
            code_component: The code implementation (class or function/method)
            docstring: The docstring to evaluate
            eval_type: The type of code component (class, function, method).
                      If not provided, it will be determined from code_component.
        
        Returns:
            Prompt for LLM evaluation
        """
        # Determine eval_type if not provided
        if eval_type is None:
            if code_component.strip().startswith("class "):
                eval_type = "class"
            else:
                eval_type = "function" if "self" not in code_component.split("(")[0] else "method"
        
        # Determine if input is a class or function signature
        is_class = eval_type == "class"
        
        relevant_example = self._select_relevant_example(code_component, eval_type)
        
        prompt = [
            "Please evaluate the summary part of a docstring of a " + eval_type + " based on these criteria:",
        ]

        prompt.append("<evaluation_criteria>")
        prompt.append(self.criteria["description"])
        prompt.append("")
        
        # Add criteria for each score level
        for level in ScoreLevel:
            prompt.append(f"{level.value}. {self.criteria['score_criteria'][level]}")
        prompt.append("</evaluation_criteria>")
        
        # Add single relevant example
        prompt.extend([
            "",
            "<reference_example>",
            "Summaries at different levels:",
        ])
        
        for level in ScoreLevel:
            prompt.extend([
                f"Level {level.value}: {relevant_example.summaries[level]}",
                f"Explanation: {relevant_example.explanations[level]}",
                ""
            ])
        prompt.append("</reference_example>")

        # add the code component and the docstring
        prompt.extend([
            "",
            "<original_code_component>",
            f"{code_component}",
            "</original_code_component>",
        ])

        prompt.extend([
            "",
            "<docstring_to_evaluate>",
            f"{docstring}",
            "</docstring_to_evaluate>",
        ])
        
        prompt.extend([
            "",
            "<analysis_instructions>",
            "IMPORTANT INSTRUCTIONS FOR ANALYSIS:",
            "1. Take your time to analyze the relationship between the focal code component and the summary part of the docstring.",
            "2. Consider how much additional context and value the summary provides beyond the signature.",
            "3. Compare the summary against each score level's criteria methodically.",
            "4. Look for similarities with the provided example at each quality level.",
            "</analysis_instructions>",
            "",
            "<response_format>",
            "Please structure your response as follows:",
            "1. First explain your reasoning by comparing against the criteria",
            "2. If applicable, suggest specific improvements. Include your suggestions in <suggestions></suggestions> tags. No need to provide suggestions for excellent summaries.",
            "3. Finally, provide your score (1-5) enclosed in <score></score> tags",
            "</response_format>",
            "",
            "Remember: Do not rush to assign a score. Take time to analyze thoroughly and justify your reasoning.",
            "The score should reflect your careful analysis and should be the last part of your response."
        ])
        
        return "\n".join(prompt)
    
    def parse_llm_response(self, response: str) -> Tuple[int, str]:
        """
        Extracts the numerical score and suggestions from an LLM's response.
        
        Args:
            response: The complete response text from the LLM.
            
        Returns:
            A tuple containing:
            - The numerical score (1-5)
            - The suggestions for improvement
            
        Raises:
            ValueError: If no valid score is found.
        """
        # Extract score from various patterns
        score_patterns = [
            r'<score>(\d)</score>',  # XML tags
            r'score:\s*(\d)',        # Common format
            r'score\s*=\s*(\d)',     # Alternative format
            r'(\d)\s*/\s*5',         # Rating format
            r'level\s*(\d)',         # Level references
        ]
        
        # Try each pattern
        for pattern in score_patterns:
            score_matches = re.findall(pattern, response, re.IGNORECASE)
            if score_matches:
                score = int(score_matches[0])
                if 1 <= score <= 5:
                    break
        else:
            # If no score found, default to 3
            score = 3
        
        # Extract suggestions - look for several common patterns
        suggestion_patterns = [
            r'<suggestions>(.*?)</suggestions>',    # XML tags
            r'suggestions?:\s*(.+?)(?:\n\n|\Z)',    # Common format
            r'could be improved by:?\s*(.+?)(?:\n\n|\Z)', # Alternative phrasing
            r'improvement:?\s*(.+?)(?:\n\n|\Z)',    # Another alternative
        ]
        
        # Try each pattern
        for pattern in suggestion_patterns:
            suggestion_matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
            if suggestion_matches:
                suggestion = suggestion_matches[0].strip()
                break
        else:
            # If we can't find a suggestion, extract sentences that seem like suggestions
            suggestion_sentences = []
            for sentence in re.split(r'[.!?]\s+', response):
                if any(word in sentence.lower() for word in ['could', 'should', 'might', 'consider', 'suggest', 'improve', 'better']):
                    suggestion_sentences.append(sentence.strip())
            
            if suggestion_sentences:
                suggestion = ' '.join(suggestion_sentences) + '.'
            else:
                # Default suggestion
                suggestion = "Consider adding more context and purpose to the summary."
        
        return score, suggestion

    def get_criteria_description(self) -> str:
        """Returns the main criteria description."""
        return self.criteria['description']

    def get_score_criteria(self, level: ScoreLevel) -> str:
        """Returns the criteria description for a specific score level."""
        return self.criteria['score_criteria'][level]

    def get_examples(self) -> List[SummaryEvaluationExample]:
        """Returns all evaluation examples."""
        return self.examples