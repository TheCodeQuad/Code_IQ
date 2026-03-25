"""
Static Runtime Profiler — Python-only (Phase 1)

Extracts runtime-behaviour signals from Python source code using **only
static analysis** (AST + regex).  No code is ever imported or executed,
making this safe for arbitrary untrusted repositories.

Four independent signal extractors feed a unified ``RuntimeProfile``:
    1. ExceptionSignalExtractor  — raise / except statements
    2. SideEffectSignalExtractor — I/O, network, DB patterns in calls & imports
    3. TypeFlowSignalExtractor   — decorators, async, generator, type hints
    4. TestCorpusSignalExtractor  — example I/O scraped from test/*.py files

Every extractor silently returns an empty ``RuntimeProfile`` on failure
(graceful degradation) so one broken file can never crash the pipeline.
"""
from __future__ import annotations

import ast
import glob
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from backend.models.code_component import CodeComponent, ComponentType
from backend.models.runtime_profile import RuntimeProfile
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# ======================================================================
# 1.  Exception Signal Extractor
# ======================================================================

class ExceptionSignalExtractor:
    """Extract ``raise`` and ``except`` exception types from Python source."""

    @staticmethod
    def extract(component: CodeComponent) -> RuntimeProfile:
        profile = RuntimeProfile()
        try:
            source = component.source_code
            if not source:
                return profile

            tree = ast.parse(source)

            for node in ast.walk(tree):
                # raise SomeException(...) / raise SomeException
                if isinstance(node, ast.Raise) and node.exc:
                    exc_type = ExceptionSignalExtractor._resolve_exc_type(node.exc)
                    if exc_type:
                        profile.raised_exceptions.append(exc_type)

                # except SomeException / except (A, B)
                if isinstance(node, ast.ExceptHandler) and node.type:
                    if isinstance(node.type, ast.Tuple):
                        for elt in node.type.elts:
                            name = ExceptionSignalExtractor._name_of(elt)
                            if name:
                                profile.caught_exceptions.append(name)
                    else:
                        name = ExceptionSignalExtractor._name_of(node.type)
                        if name:
                            profile.caught_exceptions.append(name)

            # Deduplicate
            profile.raised_exceptions = sorted(set(profile.raised_exceptions))
            profile.caught_exceptions = sorted(set(profile.caught_exceptions))

            if profile.raised_exceptions or profile.caught_exceptions:
                profile.confidence = max(profile.confidence, 0.85)

        except SyntaxError:
            # Fallback to regex for files with f-string or encoding issues
            profile = ExceptionSignalExtractor._regex_fallback(component.source_code)
        except Exception as e:
            logger.debug(f"ExceptionSignalExtractor skipped {component.name}: {e}")
        return profile

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _resolve_exc_type(node: ast.expr) -> Optional[str]:
        """Resolve the exception class name from a ``raise`` value."""
        if isinstance(node, ast.Call):
            return ExceptionSignalExtractor._name_of(node.func)
        return ExceptionSignalExtractor._name_of(node)

    @staticmethod
    def _name_of(node: ast.expr) -> Optional[str]:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None

    @staticmethod
    def _regex_fallback(source: str) -> RuntimeProfile:
        profile = RuntimeProfile()
        if not source:
            return profile
        for m in re.finditer(r'raise\s+(\w+)', source):
            profile.raised_exceptions.append(m.group(1))
        for m in re.finditer(r'except\s+\(?([\w, ]+)\)?', source):
            for exc in m.group(1).split(','):
                exc = exc.strip()
                if exc and exc[0].isupper():
                    profile.caught_exceptions.append(exc)
        profile.raised_exceptions = sorted(set(profile.raised_exceptions))
        profile.caught_exceptions = sorted(set(profile.caught_exceptions))
        return profile


# ======================================================================
# 2.  Side-Effect Signal Extractor
# ======================================================================

# Pattern categories — keys are human-readable labels for the docstring
_SIDE_EFFECT_PATTERNS: Dict[str, List[str]] = {
    "Reads from / writes to the filesystem": [
        "open(", ".read(", ".write(", ".readlines(", ".writelines(",
        "os.remove", "os.rename", "os.mkdir", "os.makedirs",
        "shutil.", "pathlib.", "Path(", "os.path.",
    ],
    "Makes HTTP / network requests": [
        "requests.get", "requests.post", "requests.put", "requests.delete",
        "requests.patch", "requests.head", "requests.session",
        "httpx.", "urllib.", "http.client.", "aiohttp.",
        "urlopen(", "urlretrieve(",
    ],
    "Interacts with a database": [
        "session.query", "session.add", "session.commit", "session.delete",
        "cursor.execute", "cursor.fetchone", "cursor.fetchall",
        ".execute(", "connection.cursor",
        "sqlalchemy.", "psycopg2.", "sqlite3.", "pymongo.", "redis.",
    ],
    "Uses subprocess / shell commands": [
        "subprocess.", "os.system(", "os.popen(", "Popen(",
    ],
    "Accesses environment variables": [
        "os.environ", "os.getenv(", "dotenv.",
    ],
    "Performs logging": [
        "logger.", "logging.", "log.debug", "log.info", "log.warning",
        "log.error", "log.critical",
    ],
    "Sends email or notifications": [
        "smtplib.", "email.", "send_mail(", "send_email(",
    ],
    "Modifies global / shared state": [
        "global ",
        ".add(", ".remove(", ".discard(", ".pop(", ".clear(",  # set/dict methods
        "[", "] =",  # dict/list assignment
    ],
}


class SideEffectSignalExtractor:
    """Detect side-effect categories by scanning source code & imports."""

    @staticmethod
    def extract(component: CodeComponent) -> RuntimeProfile:
        profile = RuntimeProfile()
        try:
            source = component.source_code or ""
            imports = component.imports or []
            calls = component.calls or []

            # Build a single search corpus from source + imports + calls
            corpus = source + "\n" + "\n".join(str(i) for i in imports) + "\n" + "\n".join(str(c) for c in calls)

            for label, patterns in _SIDE_EFFECT_PATTERNS.items():
                for pattern in patterns:
                    if pattern in corpus:
                        profile.side_effects.append(label)
                        break  # One match is enough for the category

            profile.side_effects = sorted(set(profile.side_effects))

            if profile.side_effects:
                profile.confidence = max(profile.confidence, 0.70)

        except Exception as e:
            logger.debug(f"SideEffectSignalExtractor skipped {component.name}: {e}")
        return profile


# ======================================================================
# 3.  Type-Flow / Decorator Signal Extractor
# ======================================================================

# Decorator → human-readable behavioural hint
_DECORATOR_HINTS: Dict[str, str] = {
    "lru_cache":         "Results are memoized (@lru_cache)",
    "cache":             "Results are memoized (@cache)",
    "cached_property":   "Value is computed once and cached (@cached_property)",
    "retry":             "Retries on failure (@retry)",
    "backoff":           "Uses exponential back-off on retry (@backoff)",
    "deprecated":        "This API is deprecated (@deprecated)",
    "abstractmethod":    "Must be overridden by subclasses (@abstractmethod)",
    "staticmethod":      "Static method — no instance binding (@staticmethod)",
    "classmethod":       "Class method — receives cls as first argument (@classmethod)",
    "property":          "Exposes a computed property (@property)",
    "validator":         "Pydantic field validator (@validator)",
    "field_validator":   "Pydantic V2 field validator (@field_validator)",
    "root_validator":    "Pydantic root validator (@root_validator)",
    "model_validator":   "Pydantic V2 model validator (@model_validator)",
    "overload":          "Overloaded signature (@overload)",
    "contextmanager":    "Used as a context manager (with statement)",
    "asynccontextmanager": "Used as an async context manager (async with)",
    "wraps":             "Preserves wrapped function metadata (@wraps)",
    "login_required":    "Requires user authentication (@login_required)",
    "permission_required": "Requires specific permissions (@permission_required)",
    "app.route":         "Flask route handler",
    "router.":           "FastAPI route handler",
    "app.get":           "FastAPI GET endpoint",
    "app.post":          "FastAPI POST endpoint",
    "app.put":           "FastAPI PUT endpoint",
    "app.delete":        "FastAPI DELETE endpoint",
}


class TypeFlowSignalExtractor:
    """Infer behavioural hints from decorators, async, generator, and type annotations."""

    @staticmethod
    def extract(component: CodeComponent) -> RuntimeProfile:
        profile = RuntimeProfile()
        try:
            # ── Decorator hints ──────────────────────────────────────
            for dec in component.decorators or []:
                dec_clean = dec.lstrip("@").split("(")[0].strip()
                # Check full decorator name first, then just the last part
                for key, hint in _DECORATOR_HINTS.items():
                    if key in dec_clean or key in dec.lower():
                        profile.behavioural_hints.append(hint)
                        break

            # ── Async ────────────────────────────────────────────────
            if component.is_async:
                profile.behavioural_hints.append(
                    "Async coroutine — callers must await this function"
                )

            # ── Generator ────────────────────────────────────────────
            if component.is_generator:
                profile.behavioural_hints.append(
                    "Generator function — yields values lazily"
                )

            # ── Abstract ─────────────────────────────────────────────
            if component.is_abstract:
                profile.behavioural_hints.append(
                    "Abstract — must be implemented by subclasses"
                )

            # ── Static / classmethod (not from decorator list) ───────
            if component.is_static and "Static method" not in str(profile.behavioural_hints):
                profile.behavioural_hints.append(
                    "Static method — no instance binding"
                )
            if component.is_class_method and "Class method" not in str(profile.behavioural_hints):
                profile.behavioural_hints.append(
                    "Class method — receives cls as first argument"
                )

            # ── Complexity label ─────────────────────────────────────
            cc = component.complexity
            if cc is not None:
                if cc <= 5:
                    profile.complexity_label = "simple"
                elif cc <= 15:
                    profile.complexity_label = "moderate"
                else:
                    profile.complexity_label = "complex"

            profile.behavioural_hints = sorted(set(profile.behavioural_hints))

            if profile.behavioural_hints:
                profile.confidence = max(profile.confidence, 0.60)

        except Exception as e:
            logger.debug(f"TypeFlowSignalExtractor skipped {component.name}: {e}")
        return profile


# ======================================================================
# 4.  Test-Corpus Signal Extractor (reads test files, never executes)
# ======================================================================

# Common test-file glob patterns for Python
_PYTHON_TEST_GLOBS = [
    "test_*.py", "*_test.py",
    "tests/test_*.py", "tests/*_test.py",
    "test/*.py", "tests/**/*.py",
    "**/test_*.py", "**/*_test.py",
]


class TestCorpusSignalExtractor:
    """Scrape example call-sites and assertions from test files (no execution)."""

    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)
        self._test_sources: Optional[Dict[str, str]] = None

    # ── Lazy test-file loading ───────────────────────────────────────

    def _load_test_sources(self) -> Dict[str, str]:
        """Return {relative_path: source_code} for every discovered test file."""
        if self._test_sources is not None:
            return self._test_sources

        self._test_sources = {}
        seen: Set[str] = set()
        for pattern in _PYTHON_TEST_GLOBS:
            for filepath in self.repo_root.glob(pattern):
                rel = str(filepath.relative_to(self.repo_root))
                if rel in seen or not filepath.is_file():
                    continue
                seen.add(rel)
                try:
                    self._test_sources[rel] = filepath.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass
        logger.debug(f"TestCorpus: loaded {len(self._test_sources)} test files from {self.repo_root}")
        return self._test_sources

    # ── Main extraction ──────────────────────────────────────────────

    def extract(self, component: CodeComponent) -> RuntimeProfile:
        profile = RuntimeProfile()
        try:
            name = component.name
            if not name:
                return profile

            test_sources = self._load_test_sources()
            if not test_sources:
                return profile

            for test_file, source in test_sources.items():
                # Quick check: does this test file reference the component?
                if name not in source:
                    continue

                examples = self._extract_call_examples(name, source, test_file)
                profile.test_examples.extend(examples)

                # Extract asserted return types
                ret_types = self._extract_assert_types(name, source)
                profile.observed_return_types.extend(ret_types)

            # Deduplicate & cap
            profile.test_examples = profile.test_examples[:5]
            profile.observed_return_types = sorted(set(profile.observed_return_types))

            if profile.test_examples:
                profile.confidence = max(profile.confidence, 0.75)

        except Exception as e:
            logger.debug(f"TestCorpusSignalExtractor skipped {component.name}: {e}")
        return profile

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_call_examples(
        func_name: str, source: str, test_file: str
    ) -> List[Dict[str, Any]]:
        """Find ``func_name(...)`` call sites inside test source."""
        examples: List[Dict[str, Any]] = []
        # Match: result = func_name(args)  or  assert func_name(args) == expected
        call_pattern = re.compile(
            rf'(?:(\w+)\s*=\s*)?{re.escape(func_name)}\s*\(([^)]*)\)',
        )
        assert_pattern = re.compile(
            rf'assert\w*\s+{re.escape(func_name)}\s*\(([^)]*)\)\s*==\s*(.+)',
        )

        for m in assert_pattern.finditer(source):
            examples.append({
                "call": f"{func_name}({m.group(1).strip()})",
                "expected": m.group(2).strip().rstrip(","),
                "source_file": test_file,
            })
            if len(examples) >= 3:
                return examples

        # Fallback: plain call sites (no expected value)
        if not examples:
            for m in call_pattern.finditer(source):
                args = m.group(2).strip()
                if args:
                    examples.append({
                        "call": f"{func_name}({args})",
                        "expected": None,
                        "source_file": test_file,
                    })
                    if len(examples) >= 3:
                        return examples

        return examples

    @staticmethod
    def _extract_assert_types(func_name: str, source: str) -> List[str]:
        """Infer return types from isinstance assertions on the function's result."""
        types: List[str] = []
        # Pattern: assert isinstance(result, SomeType) where result = func_name(...)
        isinstance_pattern = re.compile(
            r'isinstance\s*\(\s*\w+\s*,\s*(\w+)\s*\)'
        )
        # Only if the function is referenced near the isinstance check
        lines = source.split('\n')
        for i, line in enumerate(lines):
            if func_name in line:
                # Check surrounding lines (±3) for isinstance
                context = "\n".join(lines[max(0, i - 3):i + 4])
                for m in isinstance_pattern.finditer(context):
                    types.append(m.group(1))
        return types


# ======================================================================
# 5.  Unified Profiler — merges all extractors
# ======================================================================

class StaticRuntimeProfiler:
    """
    Runs all signal extractors over every ``CodeComponent`` and attaches
    a merged ``RuntimeProfile`` into ``component.metadata['runtime_profile']``.

    Usage::

        profiler = StaticRuntimeProfiler(repo_root="/path/to/repo")
        profiler.profile_components(components)
        # components now have component.metadata['runtime_profile']

    Only Python components are profiled in this phase-1 implementation.
    """

    def __init__(self, repo_root: str):
        self.repo_root = repo_root
        self.test_extractor = TestCorpusSignalExtractor(repo_root)
        self.logger = get_logger("runtime_profiler")

    def profile_components(
        self,
        components: Dict[str, CodeComponent],
    ) -> Dict[str, RuntimeProfile]:
        """Profile all Python components and return {component_id: RuntimeProfile}.

        Also injects the profile into ``component.metadata['runtime_profile']``.
        """
        profiles: Dict[str, RuntimeProfile] = {}
        profiled = 0
        skipped = 0

        for cid, comp in components.items():
            if comp.language != "python":
                skipped += 1
                continue

            profile = self._profile_one(comp)
            profiles[cid] = profile

            # Inject into component metadata for downstream agents
            if not comp.metadata:
                comp.metadata = {}
            comp.metadata["runtime_profile"] = profile.to_dict()

            profiled += 1

        self.logger.info(
            f"StaticRuntimeProfiler: profiled {profiled} Python components, "
            f"skipped {skipped} non-Python"
        )
        return profiles

    def _profile_one(self, component: CodeComponent) -> RuntimeProfile:
        """Run all extractors on a single component and merge results."""
        merged = RuntimeProfile()

        # 1. Exceptions
        exc_profile = ExceptionSignalExtractor.extract(component)
        merged.merge(exc_profile)

        # 2. Side effects
        se_profile = SideEffectSignalExtractor.extract(component)
        merged.merge(se_profile)

        # 3. Type-flow / decorators
        tf_profile = TypeFlowSignalExtractor.extract(component)
        merged.merge(tf_profile)

        # 4. Test corpus
        test_profile = self.test_extractor.extract(component)
        merged.merge(test_profile)

        return merged


# ======================================================================
# Convenience function
# ======================================================================

def profile_python_components(
    repo_root: str,
    components: Dict[str, CodeComponent],
) -> Dict[str, RuntimeProfile]:
    """One-liner helper used by the runtime pipeline script."""
    return StaticRuntimeProfiler(repo_root).profile_components(components)
