"""
Verifier Calibration Module
Computes language-agnostic calibration profiles for code components to guide
the Verifier Agent's quality expectations.

The calibration system analyzes a component's structural metadata (complexity,
dependencies, LOC, type, etc.) and context-gathering history (empty searcher
results) to produce a CalibrationProfile that tells the Verifier:
  1. What complexity tier the component falls into (trivial → complex)
  2. What category of documentation is expected (minimal → comprehensive)
  3. Whether external context is realistically available or exhausted
  4. Concrete, tier-specific acceptance criteria for the LLM prompt
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional

from backend.models.code_component import CodeComponent, ComponentType


# ─────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────

class ComplexityTier(Enum):
    """Bucketed complexity level derived from component metadata."""
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class DocumentationCategory(Enum):
    """Expected documentation style for a component."""
    MINIMAL = "minimal"           # Variable, import, constant
    STANDARD = "standard"         # Simple function/method
    DETAILED = "detailed"         # Moderate function, constructor, method
    COMPREHENSIVE = "comprehensive"  # Complex class, API endpoint, generator


# ─────────────────────────────────────────────────────────────────────
# CalibrationProfile
# ─────────────────────────────────────────────────────────────────────

@dataclass
class CalibrationProfile:
    """
    Aggregated calibration data for a single component.

    The orchestrator builds this and passes it to the Verifier via
    ``context.metadata['calibration']``.
    """
    # Computed tiers
    complexity_tier: ComplexityTier = ComplexityTier.SIMPLE
    documentation_category: DocumentationCategory = DocumentationCategory.STANDARD

    # Raw signals (for prompt injection)
    lines_of_code: int = 0
    cyclomatic_complexity: int = 0
    dependency_count: int = 0       # len(calls) + len(depends_on)
    parameter_count: int = 0
    has_return_type: bool = False
    is_async: bool = False
    is_generator: bool = False
    is_abstract: bool = False
    component_type: str = "function"
    language: str = "unknown"

    # Context-gathering history (set by orchestrator)
    empty_searcher_results_count: int = 0
    total_searcher_calls: int = 0
    total_internal_contexts_found: int = 0
    total_external_contexts_found: int = 0
    context_exhausted: bool = False

    # Verifier loop history
    rejection_count: int = 0
    max_rejections: int = 3

    # API metadata (if applicable)
    is_api_endpoint: bool = False
    http_method: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'complexity_tier': self.complexity_tier.value,
            'documentation_category': self.documentation_category.value,
            'lines_of_code': self.lines_of_code,
            'cyclomatic_complexity': self.cyclomatic_complexity,
            'dependency_count': self.dependency_count,
            'parameter_count': self.parameter_count,
            'has_return_type': self.has_return_type,
            'is_async': self.is_async,
            'is_generator': self.is_generator,
            'is_abstract': self.is_abstract,
            'component_type': self.component_type,
            'language': self.language,
            'empty_searcher_results_count': self.empty_searcher_results_count,
            'total_searcher_calls': self.total_searcher_calls,
            'total_internal_contexts_found': self.total_internal_contexts_found,
            'total_external_contexts_found': self.total_external_contexts_found,
            'context_exhausted': self.context_exhausted,
            'rejection_count': self.rejection_count,
            'max_rejections': self.max_rejections,
            'is_api_endpoint': self.is_api_endpoint,
            'http_method': self.http_method,
        }


# ─────────────────────────────────────────────────────────────────────
# Tier Classification
# ─────────────────────────────────────────────────────────────────────

def classify_complexity_tier(component: CodeComponent) -> ComplexityTier:
    """
    Classify a component into a complexity tier based on its structural
    metadata. Language-agnostic — uses only CodeComponent fields.

    Scoring weights:
      - Lines of code        → 0-3 points
      - Cyclomatic complexity → 0-3 points
      - Parameter count       → 0-2 points
      - Dependency count      → 0-2 points
      - Special traits bonus  → 0-2 points  (async, generator, abstract)

    Tier thresholds (out of 12 max):
      - TRIVIAL:  0-2
      - SIMPLE:   3-5
      - MODERATE:  6-8
      - COMPLEX:  9+
    """
    score = 0
    loc = component.lines_of_code or 0
    complexity = component.complexity or 0
    dep_count = len(component.calls or []) + len(component.depends_on or [])
    param_count = len(component.parameters or [])

    # Lines of code score
    if loc <= 5:
        score += 0
    elif loc <= 15:
        score += 1
    elif loc <= 40:
        score += 2
    else:
        score += 3

    # Cyclomatic complexity score
    if complexity <= 2:
        score += 0
    elif complexity <= 5:
        score += 1
    elif complexity <= 10:
        score += 2
    else:
        score += 3

    # Parameter count score
    if param_count <= 1:
        score += 0
    elif param_count <= 3:
        score += 1
    else:
        score += 2

    # Dependency count score
    if dep_count == 0:
        score += 0
    elif dep_count <= 3:
        score += 1
    else:
        score += 2

    # Special trait bonus
    if component.is_async:
        score += 1
    if component.is_generator:
        score += 1
    if component.is_abstract:
        score += 1

    # Map score → tier
    if score <= 2:
        return ComplexityTier.TRIVIAL
    elif score <= 5:
        return ComplexityTier.SIMPLE
    elif score <= 8:
        return ComplexityTier.MODERATE
    else:
        return ComplexityTier.COMPLEX


def classify_documentation_category(
    component: CodeComponent,
    complexity_tier: ComplexityTier,
) -> DocumentationCategory:
    """
    Determine the expected documentation style based on component type and
    complexity tier. Language-agnostic.
    """
    ctype = component.type

    # ── Minimal-doc types (regardless of complexity) ──
    if ctype in (
        ComponentType.VARIABLE,
        ComponentType.GLOBAL_VARIABLE,
        ComponentType.STATIC_FIELD,
        ComponentType.FIELD,
        ComponentType.IMPORT,
    ):
        return DocumentationCategory.MINIMAL

    # ── Module-level always at least DETAILED ──
    if ctype == ComponentType.MODULE:
        return DocumentationCategory.DETAILED

    # ── API endpoints are always COMPREHENSIVE ──
    if ctype == ComponentType.API_ENDPOINT:
        return DocumentationCategory.COMPREHENSIVE

    # ── Classes: at least DETAILED, COMPREHENSIVE if complex ──
    if ctype == ComponentType.CLASS:
        if complexity_tier in (ComplexityTier.COMPLEX, ComplexityTier.MODERATE):
            return DocumentationCategory.COMPREHENSIVE
        return DocumentationCategory.DETAILED

    # ── Constructor: at least DETAILED ──
    if ctype == ComponentType.CONSTRUCTOR:
        if complexity_tier == ComplexityTier.COMPLEX:
            return DocumentationCategory.COMPREHENSIVE
        return DocumentationCategory.DETAILED

    # ── Functions / Methods: scale with complexity ──
    tier_to_category = {
        ComplexityTier.TRIVIAL: DocumentationCategory.MINIMAL,
        ComplexityTier.SIMPLE: DocumentationCategory.STANDARD,
        ComplexityTier.MODERATE: DocumentationCategory.DETAILED,
        ComplexityTier.COMPLEX: DocumentationCategory.COMPREHENSIVE,
    }
    return tier_to_category.get(complexity_tier, DocumentationCategory.STANDARD)


# ─────────────────────────────────────────────────────────────────────
# Profile Builder
# ─────────────────────────────────────────────────────────────────────

def build_calibration_profile(
    component: CodeComponent,
    context_metadata: Optional[Dict[str, Any]] = None,
) -> CalibrationProfile:
    """
    Build a full CalibrationProfile for a component.

    Args:
        component: The code component.
        context_metadata: The context.metadata dict from AgentContext.
            May contain 'calibration_history' with searcher stats.

    Returns:
        A CalibrationProfile ready to inject into the verifier prompt.
    """
    tier = classify_complexity_tier(component)
    category = classify_documentation_category(component, tier)

    dep_count = len(component.calls or []) + len(component.depends_on or [])
    param_count = len(component.parameters or [])

    profile = CalibrationProfile(
        complexity_tier=tier,
        documentation_category=category,
        lines_of_code=component.lines_of_code or 0,
        cyclomatic_complexity=component.complexity or 0,
        dependency_count=dep_count,
        parameter_count=param_count,
        has_return_type=bool(component.return_type),
        is_async=component.is_async,
        is_generator=component.is_generator,
        is_abstract=component.is_abstract,
        component_type=component.type.value,
        language=component.language or "unknown",
        is_api_endpoint=(component.type == ComponentType.API_ENDPOINT),
        http_method=component.http_method,
    )

    # Merge context-gathering history from orchestrator
    if context_metadata:
        cal_hist = context_metadata.get('calibration_history', {})
        profile.empty_searcher_results_count = cal_hist.get('empty_searcher_results', 0)
        profile.total_searcher_calls = cal_hist.get('total_searcher_calls', 0)
        profile.total_internal_contexts_found = cal_hist.get('total_internal_found', 0)
        profile.total_external_contexts_found = cal_hist.get('total_external_found', 0)
        profile.rejection_count = cal_hist.get('rejection_count', 0)
        profile.max_rejections = cal_hist.get('max_rejections', 3)

        # Context is exhausted if searcher returned empty results ≥2 times
        # OR if we've called searcher ≥3 times with 0 total findings
        profile.context_exhausted = (
            profile.empty_searcher_results_count >= 2
            or (
                profile.total_searcher_calls >= 3
                and profile.total_internal_contexts_found == 0
                and profile.total_external_contexts_found == 0
            )
        )

    return profile


# ─────────────────────────────────────────────────────────────────────
# Prompt Generation
# ─────────────────────────────────────────────────────────────────────

_TIER_ACCEPTANCE_CRITERIA: Dict[ComplexityTier, str] = {
    ComplexityTier.TRIVIAL: (
        "ACCEPTANCE CRITERIA (Trivial component):\n"
        "- A clear one-line summary is sufficient\n"
        "- Parameter/return docs not required if self-evident from naming\n"
        "- Do NOT request additional context for trivial or stateless utilities\n"
        "- Do NOT reject for missing implementation details — there are none\n"
        "- Accept if the docstring correctly conveys purpose and is not misleading"
    ),
    ComplexityTier.SIMPLE: (
        "ACCEPTANCE CRITERIA (Simple component):\n"
        "- Summary + parameter descriptions + return description expected\n"
        "- Only request context if the function depends on non-obvious external state\n"
        "- Accept if docstring is factually correct and covers basic usage\n"
        "- Do NOT demand context for pure utility / transformation functions"
    ),
    ComplexityTier.MODERATE: (
        "ACCEPTANCE CRITERIA (Moderate component):\n"
        "- Summary, parameters, returns, and key behavioral notes expected\n"
        "- Requesting context is justified if important dependencies are undocumented\n"
        "- Side effects and error conditions should be mentioned if present\n"
        "- Accept if the docstring enables a first-time reader to use this component"
    ),
    ComplexityTier.COMPLEX: (
        "ACCEPTANCE CRITERIA (Complex component):\n"
        "- Full documentation expected: summary, params, returns, raises, side effects\n"
        "- Requesting additional context is justified for complex dependency chains\n"
        "- Behavioral contracts and edge cases should be covered\n"
        "- Architectural context (how this fits in the system) is valuable"
    ),
}

_CATEGORY_EXPECTATIONS: Dict[DocumentationCategory, str] = {
    DocumentationCategory.MINIMAL: (
        "Documentation expectation: MINIMAL — a brief description of purpose and type. "
        "Detailed parameter/return docs, examples, and context are NOT required."
    ),
    DocumentationCategory.STANDARD: (
        "Documentation expectation: STANDARD — summary, parameters, and return value. "
        "Sufficient to use the component without reading the source code."
    ),
    DocumentationCategory.DETAILED: (
        "Documentation expectation: DETAILED — summary, all parameters with types, "
        "return value, important side effects, and error conditions."
    ),
    DocumentationCategory.COMPREHENSIVE: (
        "Documentation expectation: COMPREHENSIVE — full documentation with summary, "
        "parameters, return type, raises, side effects, usage notes, and behavioral contracts."
    ),
}


def build_calibration_prompt_section(profile: CalibrationProfile) -> str:
    """
    Generate the calibration section to inject into the Verifier's task prompt.

    This gives the LLM concrete, tier-specific signals so it can properly
    calibrate its quality expectations instead of applying a one-size-fits-all
    standard.

    Returns:
        A multi-line string to prepend to the task prompt.
    """
    lines: List[str] = []

    lines.append("═══ COMPONENT CALIBRATION ═══")

    # ── Structural profile ──
    lines.append(
        f"Component type: {profile.component_type} | "
        f"Language: {profile.language} | "
        f"Complexity tier: {profile.complexity_tier.value.upper()}"
    )
    lines.append(
        f"Lines of code: {profile.lines_of_code} | "
        f"Cyclomatic complexity: {profile.cyclomatic_complexity} | "
        f"Parameters: {profile.parameter_count} | "
        f"Dependencies: {profile.dependency_count}"
    )

    # Trait flags
    traits = []
    if profile.is_async:
        traits.append("async")
    if profile.is_generator:
        traits.append("generator")
    if profile.is_abstract:
        traits.append("abstract")
    if profile.is_api_endpoint:
        traits.append(f"API endpoint ({profile.http_method or 'unknown method'})")
    if profile.has_return_type:
        traits.append("typed return")
    if traits:
        lines.append(f"Traits: {', '.join(traits)}")

    lines.append("")

    # ── Tier-specific acceptance criteria ──
    lines.append(_TIER_ACCEPTANCE_CRITERIA.get(
        profile.complexity_tier,
        _TIER_ACCEPTANCE_CRITERIA[ComplexityTier.SIMPLE],
    ))
    lines.append("")

    # ── Documentation category expectation ──
    lines.append(_CATEGORY_EXPECTATIONS.get(
        profile.documentation_category,
        _CATEGORY_EXPECTATIONS[DocumentationCategory.STANDARD],
    ))
    lines.append("")

    # ── Context exhaustion warning ──
    if profile.context_exhausted:
        lines.append(
            "⚠ CONTEXT EXHAUSTED: The searcher has been run "
            f"{profile.total_searcher_calls} time(s) and returned empty results "
            f"{profile.empty_searcher_results_count} time(s). "
            f"Total findings: {profile.total_internal_contexts_found} internal, "
            f"{profile.total_external_contexts_found} external.\n"
            "There is NO additional context available in the codebase for this component. "
            "Do NOT set MORE_CONTEXT=true. Evaluate the docstring strictly based on "
            "what can be determined from the code itself."
        )
        lines.append("")
    elif profile.total_searcher_calls > 0:
        lines.append(
            f"Context gathering: {profile.total_searcher_calls} searcher call(s) made, "
            f"{profile.total_internal_contexts_found} internal + "
            f"{profile.total_external_contexts_found} external results found."
        )
        lines.append("")

    # ── Rejection history ──
    if profile.rejection_count > 0:
        remaining = max(0, profile.max_rejections - profile.rejection_count)
        lines.append(
            f"Rejection history: {profile.rejection_count}/{profile.max_rejections} "
            f"rejections used ({remaining} remaining). "
            "Focus suggestions on the most impactful improvement only."
        )
        lines.append("")

    # ── Zero-dependency reminder ──
    if profile.dependency_count == 0:
        lines.append(
            "NOTE: This component has ZERO dependencies on other components. "
            "It is self-contained. Requesting additional context will not yield "
            "useful results. Evaluate the docstring based solely on the code."
        )
        lines.append("")

    lines.append("═══ END CALIBRATION ═══")
    return "\n".join(lines)
