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

try:
    from backend.evaluator.base import BaseEvaluator
    from backend.evaluator.language_config import LANGUAGE_CONFIG
except ImportError:
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

    def evaluate_component(self, component, verbose: bool = False) -> float:
        """
        Evaluate completeness for a single CodeComponent.

        Args:
            component: A CodeComponent object from your extractor.
            verbose: If True, print detailed logs about the evaluation.

        Returns:
            float: Completeness score between 0 and 1, or -1 if component should be skipped.
        """
        language = getattr(component, 'language', None)
        comp_name = getattr(component, 'name', 'unknown')
        comp_type = getattr(component, 'type', None)
        comp_type_str = comp_type.value if comp_type else 'unknown'
        
        # Skip global variables - they don't typically have docstrings
        skip_types = ['global_variable', 'variable', 'constant']
        if comp_type_str in skip_types:
            if verbose:
                print(f"\n[COMPLETENESS] Skipping: {comp_name} ({comp_type_str}) - not a documentable component")
            self.score = -1  # Signal to skip this component
            return self.score
        
        if verbose:
            print(f"\n{'='*70}")
            print(f"[COMPLETENESS] Evaluating: {comp_name} ({comp_type_str}) [{language}]")
            print(f"{'='*70}")
        
        if language not in LANGUAGE_CONFIG:
            if verbose:
                print(f"  [ERROR] Unsupported language: {language}")
            self.score = 0.0
            return self.score

        # Determine what sections are required for this component
        self.required_sections = self._get_required_sections(component, language)

        if verbose:
            print(f"\n  [REQUIRED SECTIONS] Based on component analysis:")
            print(f"    → {self.required_sections}")

        # Initialize tracking dicts
        all_sections = ["summary", "description", "args", "returns", "raises", "examples", "attributes"]
        self.element_scores = {s: False for s in all_sections}
        self.element_required = {s: s in self.required_sections for s in all_sections}

        # No docstring → score 0
        docstring = getattr(component, 'existing_docstring', None)
        if not docstring:
            if verbose:
                print(f"\n  [DOCSTRING] None/Empty - Score: 0.0")
            self.score = 0.0
            return self.score

        if verbose:
            print(f"\n  [DOCSTRING CONTENT]:")
            # Show first 500 chars of docstring for context
            docstring_preview = docstring[:500] + "..." if len(docstring) > 500 else docstring
            for line in docstring_preview.split('\n'):
                print(f"    | {line}")

        # Check each required section
        if verbose:
            print(f"\n  [SECTION CHECKS]:")
        for section in self.required_sections:
            present = self._check_section(section, docstring, language)
            self.element_scores[section] = present
            if verbose:
                status = "✓ FOUND" if present else "✗ MISSING"
                print(f"    {section:15} → {status}")

        # Score = present / required (equal weights, same as Python version)
        required_count = len(self.required_sections)
        present_count = sum(
            1 for s in self.required_sections if self.element_scores[s]
        )

        self.score = round(present_count / required_count, 3) if required_count > 0 else 0.0
        
        if verbose:
            print(f"\n  [SCORE CALCULATION]:")
            print(f"    Sections present: {present_count}")
            print(f"    Sections required: {required_count}")
            print(f"    Formula: {present_count} / {required_count} = {self.score}")
            print(f"\n  [FINAL COMPLETENESS SCORE]: {self.score}")
            print(f"{'='*70}\n")
        
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

        is_trivial = self._is_trivial_component(component, language)

        # Fields: only need summary (they're simple declarations)
        if comp_type in ("field", "static_field"):
            return required

        # Description requirement:
        # - For classes: require description unless they have Attributes section
        # - For functions/methods: DON'T require separate description - a good summary is enough
        #   (The summary line itself is descriptive. Requiring a separate "description"
        #   paragraph is overly strict and penalizes well-written concise docstrings)
        # - For constructors: don't require description (they're straightforward)
        if is_public and not is_private and not is_trivial:
            if comp_type == "class":
                # For classes, require description only if no attributes defined
                if language == "python":
                    extracted_attrs = getattr(component, "attributes", []) or []
                    has_attrs = bool(extracted_attrs)
                    if not has_attrs:
                        required.append("description")
                else:
                    # For non-Python classes, also require description
                    required.append("description")
            # Functions/methods: summary is sufficient, no separate description needed

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

        # Examples are intentionally NOT required.
        # Rationale: forcing examples encourages invented/unverifiable usage,
        # which conflicts with the truthfulness constraint.

        # Attributes: only for classes in Java (JavaDoc doesn't have standard attributes section)
        # For JS/TS classes we check attributes too
        if comp_type == "class":
            if language in ("javascript", "typescript"):
                # Only add if class likely has properties (hard to know without AST, so always add for public classes)
                if is_public:
                    required.append("attributes")
            # Java: attributes not standard in JavaDoc — skip

        # For Python classes, require Attributes when we can see fields.
        if comp_type == "class" and language == "python":
            extracted_attrs = getattr(component, "attributes", []) or []
            if extracted_attrs:
                required.append("attributes")

        return required

    # ================================================================
    # TRIVIALITY HEURISTIC
    # ================================================================

    def _is_trivial_component(self, component, language: str) -> bool:
        """Heuristic: detect trivial helpers that shouldn't require description/examples.

        Trivial means: very small body and simple behavior (single return/delegation).
        This intentionally mirrors the WriterAgent's approach, but is self-contained.
        """
        src = getattr(component, 'source_code', '') or ''
        if not src.strip():
            return False

        # Remove obvious comment-only lines
        raw_lines = [ln.strip() for ln in src.splitlines() if ln.strip()]
        filtered: List[str] = []
        for ln in raw_lines:
            if ln.startswith(('#', '//', '/*', '*', '*/')):
                continue
            filtered.append(ln)

        if not filtered:
            return False

        # Drop signature-ish lines and braces
        body_lines: List[str] = []
        for ln in filtered:
            if ln in ('{', '}', ')', ');'):
                continue
            if language in ('javascript', 'typescript'):
                if ln.startswith(('export ', 'function ', 'async function', 'const ', 'let ', 'var ')) and ('{' in ln or '=>' in ln):
                    continue
            if language == 'python' and ln.startswith(('def ', 'async def ', 'class ')):
                continue
            if language == 'java' and (ln.startswith(('public ', 'private ', 'protected ', 'static ')) and '(' in ln and '{' in ln):
                continue
            body_lines.append(ln)

        # Small body only
        if len(body_lines) > 3:
            return False

        trivial_patterns = [
            r'^return\b',
            r'^return\s*\w+\s*\(',          # delegation
            r'^return\s*\w+\s*[+\-*/]',     # simple arithmetic
            r'^\w+\s*=\s*\w+\s*[+\-*/]',   # assignment arithmetic
            r'^(self|this)\.\w+\s*=\s*\w+\b',  # simple field assignment (constructors/data holders)
        ]
        for ln in body_lines:
            if not any(re.match(p, ln) for p in trivial_patterns):
                return False

        return True

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