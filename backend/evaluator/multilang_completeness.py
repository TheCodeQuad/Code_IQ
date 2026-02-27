# evaluator/multilang_completeness.py
#
# Multi-language completeness evaluator.
# Supports ALL 4 languages: Python, Java, JavaScript, TypeScript
# Uses CodeComponent objects directly — no re-parsing needed.
# Same logic for all languages. No special cases.
#
# Entry point: MultiLangCompletenessEvaluator.evaluate_component(component)

import re
from typing import Dict, List, Optional, Tuple

from evaluator.base import BaseEvaluator
from evaluator.language_config import LANGUAGE_CONFIG


class MultiLangCompletenessEvaluator(BaseEvaluator):
    """
    Evaluates docstring completeness for Python, Java, JavaScript, and TypeScript
    components extracted by your Tree-sitter based extractors.

    Same logic for all languages — no special cases.
    Works directly from CodeComponent fields:
    - existing_docstring
    - parameters
    - return_type
    - metadata (throws, modifiers)
    - is_public, is_private
    - type (class / method / function / field / constructor)
    - name
    - source_code

    Attributes:
        score (float): The completeness score from 0 to 1.
        element_scores (Dict[str, bool]): Per-section presence results.
        element_required (Dict[str, bool]): Which sections were required.
        required_sections (List[str]): List of required section names.
    """

    def __init__(self):
        super().__init__(
            name="MultiLang Completeness Evaluator",
            description="Evaluates docstring completeness for Java, JavaScript, TypeScript",
        )
        self.element_scores: Dict[str, bool] = {}
        self.element_required: Dict[str, bool] = {}
        self.required_sections: List[str] = []

    # ================================================================
    # PUBLIC ENTRY POINT
    # ================================================================

    def evaluate_component(self, component) -> float:
        """
        Evaluate completeness for a single CodeComponent.

        Args:
            component: A CodeComponent object from your extractor.

        Returns:
            float: Completeness score between 0 and 1.
        """
        language = getattr(component, 'language', None)
        if language not in LANGUAGE_CONFIG:
            self.score = 0.0
            return self.score

        # Determine what sections are required for this component
        self.required_sections = self._get_required_sections(component, language)

        # Initialize tracking dicts
        all_sections = ["summary", "description", "args", "returns", "raises", "examples", "attributes"]
        self.element_scores = {s: False for s in all_sections}
        self.element_required = {s: s in self.required_sections for s in all_sections}

        # No docstring → score 0
        docstring = getattr(component, 'existing_docstring', None)
        if not docstring:
            self.score = 0.0
            return self.score

        # Check each required section
        for section in self.required_sections:
            self.element_scores[section] = self._check_section(
                section, docstring, language
            )

        # Score = present / required (equal weights, same as Python version)
        required_count = len(self.required_sections)
        present_count = sum(
            1 for s in self.required_sections if self.element_scores[s]
        )

        self.score = round(present_count / required_count, 3) if required_count > 0 else 0.0
        return self.score

    def evaluate_using_string(self, docstring: str, element_required: Dict, language: str) -> Dict:
        """
        Evaluate completeness from a raw docstring string.
        Mirror of Python version's evaluate_using_string() for compatibility.

        Args:
            docstring (str): The docstring text.
            element_required (Dict): Which elements are required {section: bool}.
            language (str): "java" | "javascript" | "typescript"

        Returns:
            Dict: {section: bool} presence results.
        """
        element_scores = {key: False for key in element_required}

        if not docstring:
            return element_scores

        for key, required in element_required.items():
            if required:
                element_scores[key] = self._check_section(key, docstring, language)

        return element_scores

    # ================================================================
    # DETERMINE REQUIRED SECTIONS
    # Same dynamic logic as Python version, adapted for CodeComponent
    # ================================================================

    def _get_required_sections(self, component, language: str) -> List[str]:
        """
        Dynamically determine required sections based on:
        - Component type (class / method / function / constructor / field)
        - Whether it has parameters
        - Whether it has a return value
        - Whether it throws exceptions
        - Whether it is public

        Args:
            component: CodeComponent object.
            language (str): Target language.

        Returns:
            List[str]: Required section names.
        """
        comp_type = component.type.value  # "class", "method", "function", "field", "constructor", "static_field"
        is_public = getattr(component, 'is_public', True)
        is_private = getattr(component, 'is_private', False)
        name = getattr(component, 'name', '')
        parameters = getattr(component, 'parameters', []) or []
        return_type = getattr(component, 'return_type', None)
        source_code = getattr(component, 'source_code', '') or ''
        metadata = getattr(component, 'metadata', {}) or {}

        required = ["summary"]

        # Fields: only need summary (they're simple declarations)
        if comp_type in ("field", "static_field"):
            return required

        # Description required for all public non-field components
        if is_public and not is_private:
            required.append("description")

        # Args required if there are parameters
        # For constructors, parameters list is populated
        if parameters and len(parameters) > 0:
            required.append("args")

        # Returns: required if not void
        if comp_type in ("method", "function", "constructor"):
            if comp_type != "constructor" and self._has_return_value(return_type, source_code, language):
                required.append("returns")

        # Raises: required if component throws exceptions
        if self._has_exceptions(metadata, source_code, language):
            required.append("raises")

        # Examples: required for public non-private non-underscore components
        # Same rule as Python version
        if is_public and not is_private:
            if comp_type == "class":
                required.append("examples")
            elif comp_type in ("method", "function") and not name.startswith("_"):
                required.append("examples")

        # Attributes: only for classes in Java (JavaDoc doesn't have standard attributes section)
        # For JS/TS classes we check attributes too
        if comp_type == "class":
            if language in ("javascript", "typescript"):
                # Only add if class likely has properties (hard to know without AST, so always add for public classes)
                if is_public:
                    required.append("attributes")
            # Java: attributes not standard in JavaDoc — skip

        return required

    def _has_return_value(self, return_type: Optional[str], source_code: str, language: str) -> bool:
        """
        Check if component has a meaningful return value.

        Args:
            return_type: The return type string from CodeComponent.
            source_code: Raw source code of the component.
            language: Target language.

        Returns:
            bool: True if returns something meaningful.
        """
        config = LANGUAGE_CONFIG[language]
        void_types = config["void_return_types"]
        return_pattern = config["return_keyword"]

        # If return type is explicitly void/None → no return needed
        if return_type in void_types:
            return False

        # If return type is explicitly set and not void → return needed
        if return_type and return_type not in void_types:
            return True

        # No return type info → check source code for return statement
        if source_code and return_pattern:
            return bool(re.search(return_pattern, source_code))

        return False

    def _has_exceptions(self, metadata: Dict, source_code: str, language: str) -> bool:
        """
        Check if component throws/raises exceptions.

        Args:
            metadata: Component metadata dict (contains 'throws' for Java).
            source_code: Raw source code.
            language: Target language.

        Returns:
            bool: True if component throws exceptions.
        """
        config = LANGUAGE_CONFIG[language]
        exception_pattern = config["exception_keyword"]

        # Java: check throws list from metadata (populated by extractor)
        if language == "java":
            throws = metadata.get('throws', [])
            if throws:
                return True

        # All languages: scan source code for throw/raise
        if source_code and exception_pattern:
            return bool(re.search(exception_pattern, source_code))

        return False

    # ================================================================
    # CHECK SECTION PRESENCE IN DOCSTRING
    # Language-aware: Python uses word labels, Java/JS/TS use @tags
    # ================================================================

    def _check_section(self, section: str, docstring: str, language: str) -> bool:
        """
        Check if a specific section is present in the docstring.

        Args:
            section: Section name ("summary", "args", "returns", etc.)
            docstring: The docstring text.
            language: Target language.

        Returns:
            bool: True if section is present.
        """
        if section == "summary":
            return self._has_summary(docstring, language)

        elif section == "description":
            return self._has_description(docstring, language)

        else:
            config = LANGUAGE_CONFIG[language]
            labels = config["section_labels"].get(section, [])
            return any(label.lower() in docstring.lower() for label in labels)

    def _has_summary(self, docstring: str, language: str) -> bool:
        """
        Check if docstring has a non-empty summary line.

        Args:
            docstring (str): The docstring text.
            language (str): Target language.

        Returns:
            bool: True if summary exists.
        """
        lines = docstring.strip().split('\n')
        for line in lines:
            # Strip JavaDoc asterisks
            cleaned = line.strip().lstrip('*').strip()
            if cleaned:
                return True
        return False

    def _has_description(self, docstring: str, language: str) -> bool:
        """
        Check if docstring has a description beyond just the summary.
        Works for both Python-style and JavaDoc-style comments.

        For JavaDoc: description is text between the summary line and
        the first @tag section.

        Args:
            docstring (str): The docstring text.
            language (str): Target language.

        Returns:
            bool: True if description exists.
        """
        if language == "python":
            # Same chunk-based logic as original Python evaluator
            chunks = []
            current_chunk = []
            for line in docstring.strip().split("\n"):
                if not line.strip():
                    if current_chunk:
                        chunks.append(current_chunk)
                        current_chunk = []
                else:
                    current_chunk.append(line.strip())
            if current_chunk:
                chunks.append(current_chunk)

            if len(chunks) < 2:
                return False

            first_line = chunks[1][0].lower()
            section_starters = [
                "args:", "arguments:", "parameters:", "params:",
                "returns:", "return:", "raises:", "examples:",
                "attributes:", "members:",
            ]
            return not any(first_line.startswith(s) for s in section_starters)

        else:
            # JavaDoc/JSDoc style
            # Strip lines and find content between summary and first @tag
            lines = []
            for line in docstring.split('\n'):
                cleaned = line.strip().lstrip('*').strip()
                lines.append(cleaned)

            # Find non-empty lines
            non_empty = [l for l in lines if l]

            if len(non_empty) < 2:
                return False

            # Check if second non-empty line starts an @tag or section
            second = non_empty[1].lower()
            if second.startswith('@'):
                return False

            # There's text between summary and first @tag → description exists
            description_lines = []
            for line in non_empty[1:]:
                if line.startswith('@'):
                    break
                description_lines.append(line)

            return bool(description_lines)