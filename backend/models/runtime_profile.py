"""
Runtime Profile Model
Stores statically-inferred runtime behaviour signals for a CodeComponent.

These signals are derived purely from source-code analysis (AST, regex,
tree-sitter) — no actual execution is involved — so they are safe for
arbitrary untrusted repositories.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class RuntimeProfile:
    """Statically-inferred runtime behaviour signals for a code component.

    Every field is **optional / empty-by-default** so a partially-filled
    profile is always valid.  The Writer prompt only emits sections for
    fields that are non-empty.
    """

    # ── Exception signals ────────────────────────────────────────────
    raised_exceptions: List[str] = field(default_factory=list)
    """Exception types explicitly raised (``raise X``)."""

    caught_exceptions: List[str] = field(default_factory=list)
    """Exception types explicitly caught (``except X``)."""

    declared_exceptions: List[str] = field(default_factory=list)
    """Exceptions declared in the signature (Java ``throws``)."""

    # ── Side-effect signals ──────────────────────────────────────────
    side_effects: List[str] = field(default_factory=list)
    """Human-readable side-effect labels,
    e.g. ``["Reads from filesystem", "Makes HTTP requests"]``."""

    # ── Type flow signals ────────────────────────────────────────────
    observed_param_types: Dict[str, List[str]] = field(default_factory=dict)
    """Parameter → list of concrete types seen in call-sites / tests."""

    observed_return_types: List[str] = field(default_factory=list)
    """Concrete return types observed in tests or inferred from code."""

    # ── Decorator / behavioural hints ────────────────────────────────
    behavioural_hints: List[str] = field(default_factory=list)
    """Hints inferred from decorators / patterns,
    e.g. ``["Results are memoized (@lru_cache)", "Retries on failure (@retry)"]``."""

    # ── Test corpus signals ──────────────────────────────────────────
    test_examples: List[Dict[str, Any]] = field(default_factory=list)
    """Example I/O extracted from test files (no execution).
    Each entry: ``{"call": "func(1, 2)", "expected": "3", "source_file": "test_x.py"}``."""

    # ── Complexity / performance hints ───────────────────────────────
    complexity_label: Optional[str] = None
    """``"simple"`` / ``"moderate"`` / ``"complex"`` based on cyclomatic complexity."""

    # ── Confidence ───────────────────────────────────────────────────
    confidence: float = 0.0
    """0.0–1.0 aggregate confidence that the profile is representative."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def is_empty(self) -> bool:
        """True when no signal was extracted at all."""
        return not any([
            self.raised_exceptions,
            self.caught_exceptions,
            self.declared_exceptions,
            self.side_effects,
            self.observed_param_types,
            self.observed_return_types,
            self.behavioural_hints,
            self.test_examples,
            self.complexity_label,
        ])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raised_exceptions": self.raised_exceptions,
            "caught_exceptions": self.caught_exceptions,
            "declared_exceptions": self.declared_exceptions,
            "side_effects": self.side_effects,
            "observed_param_types": self.observed_param_types,
            "observed_return_types": self.observed_return_types,
            "behavioural_hints": self.behavioural_hints,
            "test_examples": self.test_examples,
            "complexity_label": self.complexity_label,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuntimeProfile":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def merge(self, other: "RuntimeProfile") -> "RuntimeProfile":
        """Merge another profile into this one (union of lists, max confidence)."""
        self.raised_exceptions = list(set(self.raised_exceptions + other.raised_exceptions))
        self.caught_exceptions = list(set(self.caught_exceptions + other.caught_exceptions))
        self.declared_exceptions = list(set(self.declared_exceptions + other.declared_exceptions))
        self.side_effects = list(set(self.side_effects + other.side_effects))
        for k, v in other.observed_param_types.items():
            existing = self.observed_param_types.get(k, [])
            self.observed_param_types[k] = list(set(existing + v))
        self.observed_return_types = list(set(self.observed_return_types + other.observed_return_types))
        self.behavioural_hints = list(set(self.behavioural_hints + other.behavioural_hints))
        self.test_examples.extend(other.test_examples)
        if other.complexity_label and not self.complexity_label:
            self.complexity_label = other.complexity_label
        self.confidence = max(self.confidence, other.confidence)
        return self
