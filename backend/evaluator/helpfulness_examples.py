# evaluator/helpfulness_examples.py
#
# Evaluates the quality of docstring Examples sections by asking the LLM
# to predict correct usage from the example alone.
#
# Three evaluator classes — one per component type:
#   FunctionExampleEvaluator  → standalone functions
#   ClassExampleEvaluator     → class instantiation
#   MethodExampleEvaluator    → instance method calls
#
# How it works:
#   1. Extract the Examples section from the docstring
#   2. Give the LLM: signature + example (but NOT the implementation)
#   3. Ask it to predict the correct usage call
#   4. Compare prediction to ground truth via AST comparison
#   5. Score: 1.0 if correct, 0.0 if wrong
#
# Usage in eval_helpfulness.py:
#   from evaluator.helpfulness_examples import evaluate_examples
#   score, suggestion = evaluate_examples(component, llm_call_fn)

import ast
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union


# ================================================================
# DATACLASSES
# ================================================================

@dataclass
class FunctionCallExample:
    """Stores an example of function usage with context and expected output."""
    context_code:       str  # Code leading up to the function call
    function_signature: str  # The complete function signature
    docstring_example:  str  # Only the example part of the docstring
    expected_call:      str  # The expected function call line(s)


@dataclass
class ClassCallExample:
    """Stores an example of class instantiation with context and expected output."""
    context_code:      str  # Code leading up to class instantiation
    class_signature:   str  # The class signature
    init_signature:    str  # The __init__ method signature
    docstring_example: str  # Only the example part of the docstring
    expected_call:     str  # The expected instantiation line(s)


@dataclass
class MethodCallExample:
    """Stores an example of method usage with context and expected output."""
    context_code:      str  # Code leading up to method call
    method_signature:  str  # The method signature
    docstring_example: str  # Only the example part of the docstring
    expected_call:     str  # The expected method call line(s)


# ================================================================
# HELPER
# ================================================================

def _get_callable_name(node: Union[ast.Name, ast.Attribute]) -> str:
    """Extract callable name from ast.Name or ast.Attribute node."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return node.attr
    else:
        raise ValueError(f"Unsupported node type: {type(node)}")


def _compare_ast_nodes(node1: ast.AST, node2: ast.AST) -> bool:
    """Compare two AST nodes for equivalence."""
    # Constants (Python 3.8+)
    if isinstance(node1, ast.Constant) and isinstance(node2, ast.Constant):
        return node1.value == node2.value

    # Legacy literal nodes
    if isinstance(node1, (ast.Str, ast.Num, ast.NameConstant)):
        return isinstance(node2, type(node1)) and node1.value == node2.value  # type: ignore

    # Variable names
    if isinstance(node1, ast.Name) and isinstance(node2, ast.Name):
        return node1.id == node2.id

    # Attribute access (e.g., obj.attr)
    if isinstance(node1, ast.Attribute) and isinstance(node2, ast.Attribute):
        return (node1.attr == node2.attr and
                _compare_ast_nodes(node1.value, node2.value))

    # Lists / Tuples
    if isinstance(node1, (ast.List, ast.Tuple)) and isinstance(node2, type(node1)):
        if len(node1.elts) != len(node2.elts):  # type: ignore
            return False
        return all(_compare_ast_nodes(e1, e2)
                   for e1, e2 in zip(node1.elts, node2.elts))  # type: ignore

    # Fallback: dump comparison
    return ast.dump(node1) == ast.dump(node2)


def _extract_examples_section(docstring: str) -> str:
    """
    Extract the Examples section from a docstring.

    Supports both Python style (Examples:) and
    Java/JS style (@example).

    Args:
        docstring: Full docstring text.

    Returns:
        The examples section text, or empty string if not found.
    """
    if not docstring:
        return ""

    # Python style: Examples: ... (until next section or end)
    python_match = re.search(
        r'(?:Examples?:|>>> )(.*?)(?=\n\s*\w+:|$)',
        docstring,
        re.DOTALL | re.IGNORECASE,
    )
    if python_match:
        return python_match.group(0).strip()

    # JavaDoc / JSDoc style: @example ...
    java_match = re.search(
        r'@example\s+(.*?)(?=@|\Z)',
        docstring,
        re.DOTALL,
    )
    if java_match:
        return java_match.group(1).strip()

    return ""


def _extract_expected_call(examples_text: str) -> str:
    """
    Extract the actual function/class call line from examples text.

    Looks for lines that look like function/method calls.

    Args:
        examples_text: The examples section text.

    Returns:
        The call line, or empty string if not found.
    """
    lines = examples_text.strip().split("\n")
    for line in lines:
        line = line.strip().lstrip(">>> ").strip()
        # Looks like a call: contains ( and )
        if "(" in line and ")" in line and not line.startswith("#"):
            return line
    return ""


# ================================================================
# BASE CLASS
# ================================================================

class BaseExampleEvaluator(ABC):
    """
    Base class for evaluating docstring examples.

    Tests whether examples enable correct usage prediction
    without needing to read the implementation.
    """

    @abstractmethod
    def get_evaluation_prompt(
        self, context_code: str, signature: str, example: str
    ) -> str:
        """Generate prompt asking LLM to predict the usage call."""
        pass

    @abstractmethod
    def evaluate_prediction(
        self, prediction: str, ground_truth: str
    ) -> Tuple[bool, str]:
        """Compare LLM prediction to ground truth via AST."""
        pass

    def parse_prediction(self, response: str) -> str:
        """
        Extract the predicted code from LLM response.

        Args:
            response: Full LLM response text.

        Returns:
            The predicted code line, or empty string.
        """
        # Try XML tags first
        match = re.search(r"<prediction>(.*?)</prediction>", response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Fallback: look for code block
        match = re.search(r"```(?:python)?\s*(.*?)```", response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Fallback: last non-empty line
        lines = [l.strip() for l in response.strip().split("\n") if l.strip()]
        return lines[-1] if lines else ""

    def score_example(
        self,
        component_source: str,
        signature: str,
        docstring: str,
        llm_call_fn,
    ) -> Tuple[float, str]:
        """
        Full pipeline: extract example → prompt LLM → compare → score.

        Args:
            component_source: Full source code of the component.
            signature: The signature string.
            docstring: The docstring to evaluate.
            llm_call_fn: Callable that takes a prompt string and returns response string.

        Returns:
            Tuple of (score 0.0-1.0, suggestion string).
        """
        examples_text = _extract_examples_section(docstring)
        if not examples_text:
            return 0.5, "No Examples section found — consider adding usage examples."

        expected_call = _extract_expected_call(examples_text)
        if not expected_call:
            return 0.5, "Examples section found but no callable usage detected."

        try:
            prompt = self.get_evaluation_prompt(
                context_code=component_source,
                signature=signature,
                example=examples_text,
            )
            response = llm_call_fn(prompt)
            prediction = self.parse_prediction(response)

            if not prediction:
                return 0.5, "LLM could not generate a prediction from the example."

            is_correct, explanation = self.evaluate_prediction(prediction, expected_call)

            if is_correct:
                return 1.0, "Example is clear enough for correct usage prediction."
            else:
                return 0.0, (
                    f"Example unclear — LLM predicted wrong usage. "
                    f"Reason: {explanation}. "
                    f"Consider making the example more explicit."
                )

        except Exception as e:
            return 0.5, f"Could not evaluate example: {e}"


# ================================================================
# FUNCTION EVALUATOR
# ================================================================

class FunctionExampleEvaluator(BaseExampleEvaluator):
    """
    Evaluates docstring examples for standalone functions.

    Tests if the example enables correct function call prediction.
    """

    def get_evaluation_prompt(
        self, context_code: str, signature: str, example: str
    ) -> str:
        """
        Generate prompt for function call prediction.

        Args:
            context_code: Code context before the call.
            signature: The function signature.
            example: The Examples section text.

        Returns:
            Formatted prompt string.
        """
        return "\n".join([
            "Given the following context, predict ONLY the next line of code that calls the function.",
            "Base your prediction solely on the function signature and example provided.",
            "",
            "Function signature:",
            signature,
            "",
            "Example from docstring:",
            example,
            "",
            "Context code leading up to function call:",
            context_code,
            "",
            "IMPORTANT INSTRUCTIONS:",
            "1. Predict ONLY the next line(s) that calls the function",
            "2. Base your prediction solely on the signature and example",
            "3. Include ONLY the function call, no additional explanation",
            "4. If the function call spans multiple lines, include all necessary lines",
            "5. Ensure the prediction is valid Python syntax",
            "",
            "Your prediction should be enclosed in <prediction></prediction> tags",
        ])

    def evaluate_prediction(
        self, prediction: str, ground_truth: str
    ) -> Tuple[bool, str]:
        """
        Compare predicted function call to ground truth via AST.

        Args:
            prediction: LLM predicted call.
            ground_truth: Expected call.

        Returns:
            Tuple of (is_correct, explanation).
        """
        try:
            pred_ast  = ast.parse(prediction.strip()).body[0].value   # type: ignore
            truth_ast = ast.parse(ground_truth.strip()).body[0].value  # type: ignore
        except Exception as e:
            return False, f"AST parse error: {e}"

        if not isinstance(pred_ast, ast.Call) or not isinstance(truth_ast, ast.Call):
            return False, "Not a valid function call"

        pred_name  = _get_callable_name(pred_ast.func)
        truth_name = _get_callable_name(truth_ast.func)
        if pred_name != truth_name:
            return False, f"Function name mismatch: expected '{truth_name}', got '{pred_name}'"

        pred_kwargs  = {kw.arg: kw.value for kw in pred_ast.keywords}
        truth_kwargs = {kw.arg: kw.value for kw in truth_ast.keywords}

        if len(pred_ast.args) != len(truth_ast.args):
            return False, "Mismatched number of positional arguments"

        if set(pred_kwargs.keys()) != set(truth_kwargs.keys()):
            return False, "Mismatched keyword argument names"

        for i, (p, t) in enumerate(zip(pred_ast.args, truth_ast.args)):
            if not _compare_ast_nodes(p, t):
                return False, f"Positional argument {i+1} mismatch"

        for name, t_val in truth_kwargs.items():
            if not _compare_ast_nodes(pred_kwargs[name], t_val):
                return False, f"Keyword argument '{name}' value mismatch"

        return True, "Function call matches expected usage"


# ================================================================
# CLASS EVALUATOR
# ================================================================

class ClassExampleEvaluator(BaseExampleEvaluator):
    """
    Evaluates docstring examples for class instantiation.

    Tests if the example enables correct constructor call prediction.
    """

    def get_evaluation_prompt(
        self, context_code: str, signature: str, example: str
    ) -> str:
        """
        Generate prompt for class instantiation prediction.

        Args:
            context_code: Code context before instantiation.
            signature: Combined class + __init__ signature.
            example: The Examples section text.

        Returns:
            Formatted prompt string.
        """
        return "\n".join([
            "Given the following context, predict ONLY the next line of code that creates a class instance.",
            "Base your prediction solely on the class signature and example provided.",
            "",
            "Class and __init__ signatures:",
            signature,
            "",
            "Example from docstring:",
            example,
            "",
            "Context code leading up to class instantiation:",
            context_code,
            "",
            "IMPORTANT INSTRUCTIONS:",
            "1. Predict ONLY the next line(s) that creates the class instance",
            "2. Base your prediction solely on the signatures and example",
            "3. Include ONLY the instantiation code, no additional explanation",
            "4. If the instantiation spans multiple lines, include all necessary lines",
            "5. Ensure the prediction is valid Python syntax",
            "",
            "Your prediction should be enclosed in <prediction></prediction> tags",
        ])

    def evaluate_prediction(
        self, prediction: str, ground_truth: str
    ) -> Tuple[bool, str]:
        """
        Compare predicted class instantiation to ground truth via AST.

        Args:
            prediction: LLM predicted instantiation.
            ground_truth: Expected instantiation.

        Returns:
            Tuple of (is_correct, explanation).
        """
        try:
            pred_ast  = ast.parse(prediction.strip()).body[0].value   # type: ignore
            truth_ast = ast.parse(ground_truth.strip()).body[0].value  # type: ignore
        except Exception as e:
            return False, f"AST parse error: {e}"

        if not isinstance(pred_ast, ast.Call) or not isinstance(truth_ast, ast.Call):
            return False, "Not a valid class instantiation"

        pred_name  = _get_callable_name(pred_ast.func)
        truth_name = _get_callable_name(truth_ast.func)
        if pred_name != truth_name:
            return False, f"Class name mismatch: expected '{truth_name}', got '{pred_name}'"

        pred_kwargs  = {kw.arg: kw.value for kw in pred_ast.keywords}
        truth_kwargs = {kw.arg: kw.value for kw in truth_ast.keywords}

        if len(pred_ast.args) != len(truth_ast.args):
            return False, "Mismatched number of positional arguments"

        if set(pred_kwargs.keys()) != set(truth_kwargs.keys()):
            return False, "Mismatched keyword argument names"

        for i, (p, t) in enumerate(zip(pred_ast.args, truth_ast.args)):
            if not _compare_ast_nodes(p, t):
                return False, f"Positional argument {i+1} mismatch"

        for name, t_val in truth_kwargs.items():
            if not _compare_ast_nodes(pred_kwargs[name], t_val):
                return False, f"Keyword argument '{name}' value mismatch"

        return True, "Class instantiation matches expected usage"


# ================================================================
# METHOD EVALUATOR
# ================================================================

class MethodExampleEvaluator(BaseExampleEvaluator):
    """
    Evaluates docstring examples for class methods.

    Tests if the example enables correct method call prediction.
    """

    def get_evaluation_prompt(
        self, context_code: str, signature: str, example: str
    ) -> str:
        """
        Generate prompt for method call prediction.

        Args:
            context_code: Code context before the method call.
            signature: The method signature.
            example: The Examples section text.

        Returns:
            Formatted prompt string.
        """
        return "\n".join([
            "Given the following context, predict ONLY the next line of code that calls the class method.",
            "Base your prediction solely on the method signature and example provided.",
            "",
            "Method signature:",
            "<method_signature>",
            signature,
            "</method_signature>",
            "",
            "Example from docstring:",
            "<docstring_example>",
            example,
            "</docstring_example>",
            "",
            "Context code leading up to method call:",
            "<context_code>",
            context_code,
            "</context_code>",
            "",
            "IMPORTANT INSTRUCTIONS:",
            "1. Predict ONLY the next line(s) that calls the method",
            "2. Base your prediction solely on the signature and example",
            "3. Include ONLY the method call, no additional explanation",
            "4. If the method call spans multiple lines, include all necessary lines",
            "5. Ensure the prediction is valid Python syntax",
            "",
            "Your prediction should be enclosed in <prediction></prediction> tags",
        ])

    def evaluate_prediction(
        self, prediction: str, ground_truth: str
    ) -> Tuple[bool, str]:
        """
        Compare predicted method call to ground truth via AST.

        Args:
            prediction: LLM predicted call.
            ground_truth: Expected call.

        Returns:
            Tuple of (is_correct, explanation).
        """
        try:
            pred_ast  = ast.parse(prediction.strip()).body[0].value   # type: ignore
            truth_ast = ast.parse(ground_truth.strip()).body[0].value  # type: ignore
        except Exception as e:
            return False, f"AST parse error: {e}"

        if not isinstance(pred_ast, ast.Call) or not isinstance(truth_ast, ast.Call):
            return False, "Not a valid method call"

        if not isinstance(pred_ast.func, ast.Attribute) or not isinstance(truth_ast.func, ast.Attribute):
            return False, "Not a valid method call (missing object reference)"

        if not _compare_ast_nodes(pred_ast.func.value, truth_ast.func.value):
            return False, "Object reference mismatch"

        if pred_ast.func.attr != truth_ast.func.attr:
            return False, (
                f"Method name mismatch: expected '{truth_ast.func.attr}', "
                f"got '{pred_ast.func.attr}'"
            )

        pred_kwargs  = {kw.arg: kw.value for kw in pred_ast.keywords}
        truth_kwargs = {kw.arg: kw.value for kw in truth_ast.keywords}

        if len(pred_ast.args) != len(truth_ast.args):
            return False, "Mismatched number of positional arguments"

        if set(pred_kwargs.keys()) != set(truth_kwargs.keys()):
            return False, "Mismatched keyword argument names"

        for i, (p, t) in enumerate(zip(pred_ast.args, truth_ast.args)):
            if not _compare_ast_nodes(p, t):
                return False, f"Positional argument {i+1} mismatch"

        for name, t_val in truth_kwargs.items():
            if not _compare_ast_nodes(pred_kwargs[name], t_val):
                return False, f"Keyword argument '{name}' value mismatch"

        return True, "Method call matches expected usage"


# ================================================================
# CONVENIENCE FUNCTION — used by eval_helpfulness.py
# ================================================================

def evaluate_examples(
    component,
    llm_call_fn,
) -> Tuple[float, str]:
    """
    Evaluate the Examples section of a component's docstring.

    Automatically selects the right evaluator based on component type.
    Integrates directly with your CodeComponent objects from extractors.

    Args:
        component: CodeComponent object with .type, .existing_docstring,
                   .source_code, .name attributes.
        llm_call_fn: Callable(prompt: str) -> str. Your LLM call function.

    Returns:
        Tuple of (score 0.0-1.0, suggestion string).
        Returns (None, reason) if examples section not applicable.
    """
    docstring = getattr(component, "existing_docstring", None)
    if not docstring:
        return None, "No docstring"

    examples_text = _extract_examples_section(docstring)
    if not examples_text:
        return None, "No Examples section"

    comp_type   = component.type.value
    source_code = getattr(component, "source_code", "") or ""
    name        = getattr(component, "name", "unknown")

    # Build signature from source (first line)
    signature = source_code.split("\n")[0].strip() if source_code else name

    # Pick evaluator by type
    if comp_type == "class":
        evaluator = ClassExampleEvaluator()
    elif comp_type in ("method", "constructor"):
        evaluator = MethodExampleEvaluator()
    else:
        evaluator = FunctionExampleEvaluator()

    return evaluator.score_example(
        component_source=source_code,
        signature=signature,
        docstring=docstring,
        llm_call_fn=llm_call_fn,
    )