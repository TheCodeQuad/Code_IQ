"""
Runtime-Aware Writer Agent

A separate writer agent that extends the base WriterAgent with an
additional **runtime signals** block in the prompt.  It consumes
``RuntimeProfile`` data from ``component.metadata['runtime_profile']``
and injects statically-inferred runtime observations into the prompt
so the LLM can produce documentation that reflects actual behaviour
(exceptions raised, side effects, decorator semantics, test examples).

This agent does NOT modify the original ``WriterAgent`` prompts.
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.agents.base_agent import BaseAgent, AgentContext, AgentResult, AgentStatus
from backend.agents.writer_agent import (
    WriterAgent,
    DocumentationStyle,
    get_documentation_style,
    _LANGUAGE_ALIASES,
)
from backend.models.code_component import CodeComponent, ComponentType
from backend.models.documentation import Documentation
from backend.models.runtime_profile import RuntimeProfile
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class RuntimeWriterAgent(WriterAgent):
    """Writer agent enhanced with statically-inferred runtime signals.

    Inherits all formatting, style-resolution, and persistence logic
    from ``WriterAgent``.  The only difference is:

    1. ``_build_runtime_system_prompt`` — adds an extra instruction
       block about how to use runtime signals.
    2. ``_build_runtime_user_prompt`` — injects a ``RUNTIME SIGNALS``
       section before the source code in the user prompt.

    Everything else (reader/searcher context formatting, type-instructions,
    static-analysis hints, persistence, refinement) is reused as-is.
    """

    def __init__(self):
        super().__init__()
        # Override the output directory so runtime-aware docs don't mix
        self.output_dir = Path("data/output/runtime_documentation/agent_output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Runtime profile extraction helper
    # ------------------------------------------------------------------

    @staticmethod
    def _get_runtime_profile(component: CodeComponent) -> Optional[RuntimeProfile]:
        """Extract RuntimeProfile from component metadata (if present)."""
        raw = (component.metadata or {}).get("runtime_profile")
        if raw is None:
            return None
        if isinstance(raw, RuntimeProfile):
            return raw
        if isinstance(raw, dict):
            return RuntimeProfile.from_dict(raw)
        return None

    # ------------------------------------------------------------------
    # Runtime-specific system prompt addendum
    # ------------------------------------------------------------------

    def _build_runtime_system_addendum(self) -> str:
        """Extra system-level instructions for consuming runtime signals."""
        return """
RUNTIME-AWARE DOCUMENTATION RULES (apply when RUNTIME SIGNALS are present):
1. If RUNTIME SIGNALS list raised exceptions, include them in the Raises
   section — these are **confirmed** by static analysis of the source.
2. If RUNTIME SIGNALS list side effects (filesystem, network, database,
   subprocess, etc.), mention them in the description body.
3. If RUNTIME SIGNALS include behavioural hints (memoization, async,
   generator, decorator semantics), fold them into the summary or
   description as appropriate.
4. If RUNTIME SIGNALS include test examples, you may use ONE example as
   a ``Note:`` or ``Example:`` in the docstring (keep it short).
5. If a complexity label is given, warn about high complexity when relevant.
6. Do NOT fabricate runtime signals beyond what is provided in the
   RUNTIME SIGNALS block.  If the block is empty, generate documentation
   normally without any runtime references.
7. All runtime signals were extracted statically — phrase them as
   "May raise ...", "Interacts with ...", "Uses memoization via ..."
   rather than "Was observed to ..."."""

    # ------------------------------------------------------------------
    # System prompt (overrides parent to append runtime addendum)
    # ------------------------------------------------------------------

    def _build_system_prompt(self, style: DocumentationStyle) -> str:
        """Build the system prompt with the runtime addendum appended."""
        base_prompt = super()._build_system_prompt(style)
        runtime_addendum = self._build_runtime_system_addendum()
        return base_prompt + "\n" + runtime_addendum

    # ------------------------------------------------------------------
    # Runtime signals block for user prompt
    # ------------------------------------------------------------------

    @staticmethod
    def _format_runtime_block(profile: RuntimeProfile) -> str:
        """Format a RuntimeProfile into a human-readable prompt block."""
        if profile.is_empty:
            return ""

        lines: List[str] = ["RUNTIME SIGNALS (statically inferred — do not fabricate beyond these):"]

        # Exceptions
        if profile.raised_exceptions:
            lines.append(f"  - May raise: {', '.join(profile.raised_exceptions)}")
        if profile.caught_exceptions:
            lines.append(f"  - Catches internally: {', '.join(profile.caught_exceptions)}")

        # Side effects
        if profile.side_effects:
            for se in profile.side_effects:
                lines.append(f"  - Side effect: {se}")

        # Behavioural hints
        if profile.behavioural_hints:
            for hint in profile.behavioural_hints:
                lines.append(f"  - Behaviour: {hint}")

        # Complexity
        if profile.complexity_label:
            lines.append(f"  - Complexity: {profile.complexity_label}")

        # Test examples
        if profile.test_examples:
            ex = profile.test_examples[0]
            expected = f" → {ex['expected']}" if ex.get("expected") else ""
            lines.append(f"  - Test example: {ex['call']}{expected}  (from {ex.get('source_file', 'tests')})")

        # Observed return types
        if profile.observed_return_types:
            lines.append(f"  - Observed return types: {', '.join(profile.observed_return_types)}")

        lines.append("")  # trailing newline
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # User prompt (overrides parent to inject runtime block)
    # ------------------------------------------------------------------

    def _build_user_prompt(
        self,
        component: CodeComponent,
        style: DocumentationStyle,
        reader_context: str,
        searcher_context: str,
        verifier_feedback: Optional[str] = None,
    ) -> str:
        """Build user prompt with an additional RUNTIME SIGNALS section."""

        # Get the full base prompt from the parent
        base_prompt = super()._build_user_prompt(
            component, style, reader_context, searcher_context,
            verifier_feedback=verifier_feedback,
        )

        # Extract runtime profile
        profile = self._get_runtime_profile(component)
        if profile is None or profile.is_empty:
            return base_prompt

        runtime_block = self._format_runtime_block(profile)

        # Inject the runtime block just before SOURCE CODE:
        if "SOURCE CODE:" in base_prompt:
            base_prompt = base_prompt.replace(
                "SOURCE CODE:",
                f"{runtime_block}\nSOURCE CODE:",
            )
        else:
            # Fallback: append before the focal code tag
            base_prompt = base_prompt.replace(
                "<FOCAL_CODE>",
                f"{runtime_block}\n<FOCAL_CODE>",
            )

        return base_prompt

    # ------------------------------------------------------------------
    # Documentation factory (tag as runtime-aware)
    # ------------------------------------------------------------------

    @staticmethod
    def _create_documentation(
        component: CodeComponent,
        raw_response: str,
        style: DocumentationStyle,
    ) -> Documentation:
        """Wrap in Documentation, tagged as runtime-aware."""
        return Documentation(
            component_id=component.id,
            component_name=component.name,
            component_type=component.type.value,
            summary="",
            description="",
            docstring=raw_response,
            style=style.name,
            generated_by="runtime-writer-agent",
            metadata={
                "component_language": component.language,
                "documentation_style": style.name,
                "is_async": component.is_async,
                "runtime_aware": True,
            },
        )

    # ------------------------------------------------------------------
    # Main process (identical flow, but uses overridden prompt builders)
    # ------------------------------------------------------------------

    def process(self, context: AgentContext) -> AgentResult:
        """Generate runtime-aware documentation for a code component."""
        try:
            component = context.component
            style = self._get_style(component)
            self.logger.info(
                f"[RuntimeWriter] Generating runtime-aware docs for "
                f"{component.name} [{component.language}/{style.name}]"
            )

            # Gather upstream context (reader/searcher are optional here)
            reader_ctx = self._format_reader_context(context.get_result("reader"))
            searcher_ctx = self._format_searcher_context(context.get_result("searcher"))

            # Build prompts (overridden versions with runtime signals)
            system_prompt = self._build_system_prompt(style)
            user_prompt = self._build_user_prompt(
                component, style, reader_ctx, searcher_ctx,
            )

            # LLM call
            self.clear_memory()
            self.add_to_memory("system", system_prompt)
            self.add_to_memory("user", user_prompt)

            response = self.generate_response(temperature=0.2, max_tokens=2000)
            self.logger.debug(
                f"[RuntimeWriter] Raw response for {component.name}: {response[:500]}"
            )

            documentation = self._create_documentation(component, response, style)
            self._save_output(component, documentation)

            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.SUCCESS,
                output=documentation,
            )
        except Exception as e:
            self.logger.error(f"[RuntimeWriter] error: {e}", exc_info=True)
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILED,
                output=None,
                error=str(e),
            )
