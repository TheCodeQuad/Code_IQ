## 3. Verifier Agent

### `backend/agents/verifier_agent.py`
"""
Verifier Agent
Validates and improves generated documentation using LLM-driven quality assessment.

Evaluates docstrings from the perspective of a first-time user encountering the code.
Uses structured XML tags in LLM output to determine if revision is needed and whether
additional context should be gathered.
"""
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from backend.agents.base_agent import BaseAgent, AgentContext, AgentResult, AgentStatus
from backend.agents.verifier_calibration import (
    CalibrationProfile,
    build_calibration_profile,
    build_calibration_prompt_section,
)
from backend.models.code_component import CodeComponent
from backend.models.documentation import Documentation
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VerificationResult:
    """Result of documentation verification."""
    need_revision: bool
    more_context: bool = False
    suggestion: Optional[str] = None
    suggestion_context: Optional[str] = None
    raw_response: str = ""
    improved_documentation: Optional[Documentation] = None


class VerifierAgent(BaseAgent):
    """Agent responsible for verifying the quality of generated docstrings.

    Uses an LLM to evaluate documentation from a first-time reader's perspective,
    checking information value, appropriate detail level, and completeness.

    The verification output uses structured XML tags:
        <NEED_REVISION>true/false</NEED_REVISION>
        <MORE_CONTEXT>true/false</MORE_CONTEXT>
        <SUGGESTION>...</SUGGESTION>  or  <SUGGESTION_CONTEXT>...</SUGGESTION_CONTEXT>

    Orchestrator compatibility:
        - Returns AgentResult whose ``output`` is a VerificationResult
        - VerificationResult.improved_documentation is set so the orchestrator
          can swap in the improved docstring when available.
    """

    def __init__(self):
        """Initialize the Verifier agent."""
        super().__init__("verifier")

        # Load config-driven settings
        self.validation_rules = self.agent_config.get('validation_rules', [
            'completeness', 'accuracy', 'consistency'
        ])

        # Output persistence
        self.output_dir = Path("data/intermediate/agent_output/verifier")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.consolidated_outputs: List[Dict[str, Any]] = []

        # ── System prompt (Meta-style, added to memory once per call) ──
        self.system_prompt = (
            "You are a Verifier agent responsible for ensuring the quality of "
            "generated docstrings.\n"
            "Your role is to evaluate docstrings from the perspective of a "
            "first-time user encountering the code component.\n\n"
            "IMPORTANT — Calibrated Evaluation:\n"
            "Each verification request includes a COMPONENT CALIBRATION section "
            "that describes the component's complexity tier, documentation category, "
            "dependency count, and context-gathering history.\n"
            "You MUST calibrate your expectations to match the calibration data:\n"
            "- TRIVIAL/SIMPLE components with zero dependencies need only a clear "
            "summary. Do NOT demand context that does not exist.\n"
            "- If context is marked as EXHAUSTED, you MUST NOT set MORE_CONTEXT=true.\n"
            "- Use the tier-specific ACCEPTANCE CRITERIA as your quality bar.\n\n"
            "Analysis Process:\n"
            "1. Read the COMPONENT CALIBRATION section to understand expectations\n"
            "2. Read the code component as if you are seeing it for the first time\n"
            "3. Read the docstring and evaluate against the tier-specific criteria\n"
            "4. Decide: accept (good enough for the tier) or reject (with focused fix)\n\n"
            "Verification Criteria:\n"
            "1. Information Value:\n"
            "   - Identify parts that merely repeat the code without adding value\n"
            "   - Flag docstrings that state the obvious without providing insights\n"
            "   - Check if explanations actually help understand the purpose and usage\n\n"
            "2. Appropriate Detail Level (calibrated by tier):\n"
            "   - MINIMAL/STANDARD tiers: a concise, correct summary is acceptable\n"
            "   - DETAILED/COMPREHENSIVE tiers: expect thorough parameter, return, "
            "and behavioral documentation\n"
            "   - Ensure focus is on usage and purpose, not line-by-line explanation\n\n"
            "3. Completeness Check (calibrated by category):\n"
            "   - MINIMAL category: only a purpose statement is required\n"
            "   - STANDARD category: summary + params + returns\n"
            "   - DETAILED category: summary + params + returns + side effects\n"
            "   - COMPREHENSIVE category: all sections with behavioral contracts\n\n"
            "Context Request Rules:\n"
            "- NEVER request context for components with zero dependencies\n"
            "- NEVER request context when the calibration says CONTEXT EXHAUSTED\n"
            "- Only request context when specific, named dependencies lack documentation\n"
            "- Prefer suggesting content fixes (MORE_CONTEXT=false) over context requests\n\n"
            "Output Format:\n"
            "Your analysis must include:\n"
            "1. <NEED_REVISION>true/false</NEED_REVISION>\n"
            "   - Indicates if docstring needs improvement\n\n"
            "2. If revision needed:\n"
            "   <MORE_CONTEXT>true/false</MORE_CONTEXT>\n"
            "   - Set true ONLY when you can name specific missing dependencies "
            "AND context is NOT exhausted\n\n"
            "3. Based on MORE_CONTEXT, provide suggestions at the end of your response:\n"
            "   If true:\n"
            "   <SUGGESTION_CONTEXT>explain why and what specific context is needed"
            "</SUGGESTION_CONTEXT>\n\n"
            "   If false:\n"
            "   <SUGGESTION>specific improvement suggestions</SUGGESTION>\n\n"
            "Do not generate other things after </SUGGESTION> or </SUGGESTION_CONTEXT>.\n"
        )

    # ------------------------------------------------------------------
    # Core pipeline entry point
    # ------------------------------------------------------------------

    def process(self, context: AgentContext) -> AgentResult:
        """Verify the quality of a generated docstring.

        Pulls the Writer's Documentation output and the CodeComponent from
        *context*, builds a calibration profile, sends it to the LLM via the
        memory-based conversation API, and parses the structured response.

        Args:
            context: AgentContext populated by the orchestrator.  Must contain
                ``context.component`` (CodeComponent) and a Writer result
                accessible via ``context.get_result('writer')``.

        Returns:
            AgentResult with a VerificationResult as ``output``.
        """
        try:
            component = context.component
            documentation = context.get_result('writer')

            if not documentation or not isinstance(documentation, Documentation):
                return AgentResult(
                    agent_name=self.agent_name,
                    status=AgentStatus.FAILED,
                    output=None,
                    error="No Writer output available for verification",
                )

            self.logger.info(f"Verifying documentation for: {component.name}")

            # ── Build calibration profile from component + context history ──
            calibration = build_calibration_profile(
                component, context.metadata
            )
            self.logger.info(
                f"Calibration: tier={calibration.complexity_tier.value}, "
                f"category={calibration.documentation_category.value}, "
                f"deps={calibration.dependency_count}, "
                f"context_exhausted={calibration.context_exhausted}"
            )

            # ── Build context string from accumulated searcher data ──
            context_str = self._build_context_string(context)

            # ── Run LLM-driven verification ──
            verification = self._verify_with_llm(
                component, documentation, context_str, calibration
            )

            # Apply hard overrides based on calibration
            verification = self._apply_calibration_overrides(
                verification, calibration
            )

            # Verifier is detection-only; the orchestrator delegates
            # improvement to the Writer via refine_documentation().
            verification.improved_documentation = None

            self.logger.info(
                f"Verification complete for {component.name}: "
                f"need_revision={verification.need_revision}, "
                f"more_context={verification.more_context}"
            )

            # Log the suggestion or context reason if present
            if verification.need_revision:
                if verification.more_context and verification.suggestion_context:
                    self.logger.info(
                        f"Verifier context request reason: {verification.suggestion_context}"
                    )
                elif verification.suggestion:
                    self.logger.info(
                        f"Verifier improvement suggestion: {verification.suggestion}"
                    )

            # Save verification output to disk
            self._save_verification_output(component, verification)

            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.SUCCESS,
                output=verification,
                metadata={
                    'need_revision': verification.need_revision,
                    'more_context': verification.more_context,
                    'suggestion': verification.suggestion,
                    'suggestion_context': verification.suggestion_context,
                    'calibration': calibration.to_dict(),
                },
            )

        except Exception as e:
            self.logger.error(f"Verifier agent error: {e}", exc_info=True)
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILED,
                output=None,
                error=str(e),
            )

    # ------------------------------------------------------------------
    # LLM-driven verification
    # ------------------------------------------------------------------

    def _verify_with_llm(
        self,
        component: CodeComponent,
        documentation: Documentation,
        context_str: str,
        calibration: CalibrationProfile,
    ) -> VerificationResult:
        """Send a verification request to the LLM and parse the response.

        Args:
            component: The code component under review.
            documentation: The Writer-generated documentation.
            context_str: Aggregated context from Reader/Searcher stages.
            calibration: The calibration profile for this component.

        Returns:
            Parsed VerificationResult.
        """
        # Fresh memory for each verification call
        self.clear_memory()
        self.add_to_memory("system", self.system_prompt)

        task_description = self._build_task_prompt(
            component, documentation, context_str, calibration
        )
        self.add_to_memory("user", task_description)

        # Generate response via BaseAgent memory API
        full_response = self.generate_response(
            temperature=0.3,
            max_tokens=1500,
        )

        self.add_to_memory("assistant", full_response)

        return self._parse_verification_response(full_response)

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_task_prompt(
        self,
        component: CodeComponent,
        documentation: Documentation,
        context_str: str,
        calibration: CalibrationProfile,
    ) -> str:
        """Build the user-turn task prompt for the LLM.

        Injects the calibration section first so the LLM reads it before
        evaluating the docstring. This primes the model to use tier-specific
        acceptance criteria.

        Args:
            component: The code component.
            documentation: Generated documentation from Writer.
            context_str: Accumulated context from prior agents.
            calibration: The calibration profile with tier/category/history.

        Returns:
            Formatted prompt string.
        """
        # Extract the docstring (the raw LLM output stored by the Writer)
        docstring = documentation.docstring or ""

        # Build a readable representation of the focal component
        focal = component.source_code or component.signature or component.name

        # Build calibration section
        calibration_section = build_calibration_prompt_section(calibration)

        return (
            f"{calibration_section}\n\n"
            f"Context Used:\n"
            f"{context_str if context_str else 'No context was used.'}\n\n"
            f"Verify the quality of the following docstring for the following "
            f"Code Component:\n\n"
            f"Code Component ({component.type.value} | "
            f"language={component.language}):\n"
            f"{focal}\n\n"
            f"Generated Docstring:\n"
            f"{docstring}\n"
        )

    def _build_context_string(self, context: AgentContext) -> str:
        """Extract accumulated context from the AgentContext metadata.

        The orchestrator stores Reader/Searcher gathered context under
        ``context.metadata['accumulated_context']``.

        Args:
            context: The agent context passed by the orchestrator.

        Returns:
            A human-readable context string for the LLM prompt.
        """
        parts: List[str] = []
        accumulated = (context.metadata or {}).get('accumulated_context', {})

        internal = accumulated.get('internal', [])
        if internal:
            parts.append("Internal dependencies / references:")
            for item in internal:
                if isinstance(item, dict):
                    name = item.get('name', item.get('component_name', ''))
                    summary = item.get('summary', item.get('usage_summary', ''))
                    sig = item.get('signature', '')
                    parts.append(f"  - {name}: {summary} {sig}".strip())
                else:
                    parts.append(f"  - {item}")

        external = accumulated.get('external', [])
        if external:
            parts.append("External knowledge:")
            for item in external:
                if isinstance(item, dict):
                    query = item.get('query', '')
                    summary = item.get('summary', '')
                    parts.append(f"  - [{query}] {summary}".strip())
                else:
                    parts.append(f"  - {item}")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Calibration overrides (hard rules the LLM cannot bypass)
    # ------------------------------------------------------------------

    def _apply_calibration_overrides(
        self,
        verification: VerificationResult,
        calibration: CalibrationProfile,
    ) -> VerificationResult:
        """Apply deterministic overrides based on calibration signals.

        These are safety nets that catch cases where the LLM ignores the
        calibration instructions — e.g. requesting context when it is
        exhausted, or demanding context for zero-dependency components.

        Args:
            verification: The LLM-parsed VerificationResult.
            calibration: The calibration profile.

        Returns:
            The (possibly modified) VerificationResult.
        """
        if not verification.need_revision:
            return verification

        # ── Override 1: Context exhausted → force MORE_CONTEXT=false ──
        if verification.more_context and calibration.context_exhausted:
            self.logger.info(
                "Calibration override: context exhausted, "
                "converting MORE_CONTEXT → false"
            )
            verification.more_context = False
            # Convert context suggestion to content suggestion
            if verification.suggestion_context and not verification.suggestion:
                verification.suggestion = (
                    f"(Context unavailable) {verification.suggestion_context}"
                )
                verification.suggestion_context = None

        # ── Override 2: Zero dependencies → no context request makes sense ──
        if verification.more_context and calibration.dependency_count == 0:
            self.logger.info(
                "Calibration override: zero dependencies, "
                "converting MORE_CONTEXT → false"
            )
            verification.more_context = False
            if verification.suggestion_context and not verification.suggestion:
                verification.suggestion = (
                    f"(No dependencies to look up) {verification.suggestion_context}"
                )
                verification.suggestion_context = None

        # ── Override 3: TRIVIAL tier with MINIMAL category → accept as-is ──
        #    unless the docstring is truly empty or misleading (need_revision
        #    is still respected for content issues, but context requests are blocked)
        if (verification.more_context
                and calibration.complexity_tier.value == "trivial"
                and calibration.documentation_category.value == "minimal"):
            self.logger.info(
                "Calibration override: trivial/minimal component, "
                "blocking context request"
            )
            verification.more_context = False

        return verification

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_verification_response(self, response: str) -> VerificationResult:
        """Parse the LLM's structured XML-tag response.

        Expected tags:
            <NEED_REVISION>true/false</NEED_REVISION>
            <MORE_CONTEXT>true/false</MORE_CONTEXT>   (only when revision needed)
            <SUGGESTION>...</SUGGESTION>              (when MORE_CONTEXT is false)
            <SUGGESTION_CONTEXT>...</SUGGESTION_CONTEXT> (when MORE_CONTEXT is true)

        Args:
            response: Raw LLM response string.

        Returns:
            VerificationResult populated from the parsed tags.
        """
        need_revision = self._extract_bool_tag(response, "NEED_REVISION")
        more_context = self._extract_bool_tag(response, "MORE_CONTEXT") if need_revision else False

        suggestion = self._extract_tag(response, "SUGGESTION")
        suggestion_context = self._extract_tag(response, "SUGGESTION_CONTEXT")

        return VerificationResult(
            need_revision=need_revision,
            more_context=more_context,
            suggestion=suggestion,
            suggestion_context=suggestion_context,
            raw_response=response,
        )

    @staticmethod
    def _extract_tag(text: str, tag: str) -> Optional[str]:
        """Extract content between <TAG>...</TAG>."""
        pattern = rf"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_bool_tag(text: str, tag: str) -> bool:
        """Extract a boolean value from <TAG>true/false</TAG>."""
        pattern = rf"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip().lower() == "true"
        return False

    # ------------------------------------------------------------------
    # Output persistence
    # ------------------------------------------------------------------

    def _save_verification_output(
        self,
        component: CodeComponent,
        verification: VerificationResult,
    ) -> None:
        """Save individual verification result to disk for audit trail."""
        try:
            output_data = {
                'component_id': component.id,
                'component_name': component.name,
                'component_type': component.type.value,
                'language': component.language,
                'need_revision': verification.need_revision,
                'more_context': verification.more_context,
                'suggestion': verification.suggestion,
                'suggestion_context': verification.suggestion_context,
                'verified_at': datetime.now().isoformat(),
            }

            # Track for consolidated output
            self.consolidated_outputs.append(output_data)

            # Save individual file
            safe_name = re.sub(r'[^\w\-.]', '_', component.name)
            path = self.output_dir / f"{safe_name}_{component.id[:8]}_verification.json"
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"Saved verification output to {path}")
        except Exception as e:
            self.logger.warning(f"Failed to save verification output: {e}")

    def save_consolidated_output(
        self,
        filename: str = "consolidated_verifier_output.json",
    ) -> Optional[Path]:
        """Save all verification results as a single consolidated JSON file.

        Returns:
            Path to the consolidated file, or None if nothing to save.
        """
        if not self.consolidated_outputs:
            return None

        try:
            output_path = self.output_dir / filename
            consolidated = {
                'total_verified': len(self.consolidated_outputs),
                'needed_revision': sum(
                    1 for o in self.consolidated_outputs if o.get('need_revision')
                ),
                'needed_more_context': sum(
                    1 for o in self.consolidated_outputs if o.get('more_context')
                ),
                'needed_content_fix': sum(
                    1 for o in self.consolidated_outputs
                    if o.get('need_revision') and not o.get('more_context')
                ),
                'generated_at': datetime.now().isoformat(),
                'results': self.consolidated_outputs,
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(consolidated, f, indent=2, ensure_ascii=False)
            self.logger.info(
                f"Consolidated verifier output saved: {len(self.consolidated_outputs)} results"
            )
            return output_path
        except Exception as e:
            self.logger.warning(f"Failed to save consolidated verifier output: {e}")
            return None