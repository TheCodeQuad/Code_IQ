"""
Security-Aware Writer Agent

A writer agent that extends RuntimeWriterAgent with security vulnerability
documentation. It consumes SecurityProfile data and generates documentation
that includes security warnings, vulnerability descriptions, and mitigation
recommendations.

This agent does NOT modify the original WriterAgent or RuntimeWriterAgent.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.agents.base_agent import AgentContext, AgentResult, AgentStatus
from backend.agents.runtime_writer_agent import RuntimeWriterAgent
from backend.agents.writer_agent import DocumentationStyle, get_documentation_style
from backend.models.code_component import CodeComponent, ComponentType
from backend.models.documentation import Documentation
from backend.models.security_profile import (
    SecurityProfile,
    VulnerabilitySignal,
    Severity,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SecurityWriterAgent(RuntimeWriterAgent):
    """Writer agent enhanced with security vulnerability documentation.

    Inherits all functionality from RuntimeWriterAgent and adds:

    1. `_build_security_system_addendum` — extra instructions for security docs
    2. `_format_security_block` — formats SecurityProfile for the prompt
    3. Security-specific sections in generated documentation

    The agent produces documentation that includes:
    - Security warnings for vulnerable code
    - CWE references and severity levels
    - Mitigation recommendations
    - Secure coding alternatives
    """

    def __init__(self):
        super().__init__()
        # Override output directory for security-aware docs
        self.output_dir = Path("data/output/security_documentation/agent_output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.agent_name = "security-writer-agent"

    # ------------------------------------------------------------------
    # Security profile extraction helper
    # ------------------------------------------------------------------

    @staticmethod
    def _get_security_profile(component: CodeComponent) -> Optional[SecurityProfile]:
        """Extract SecurityProfile from component metadata (if present)."""
        raw = (component.metadata or {}).get("security_profile")
        if raw is None:
            return None
        if isinstance(raw, SecurityProfile):
            return raw
        if isinstance(raw, dict):
            return SecurityProfile.from_dict(raw)
        return None

    # ------------------------------------------------------------------
    # Security-specific system prompt addendum
    # ------------------------------------------------------------------

    def _build_security_system_addendum(self) -> str:
        """Extra system-level instructions for security documentation."""
        return """
SECURITY DOCUMENTATION RULES (apply when SECURITY SIGNALS are present):

1. VULNERABILITY DOCUMENTATION:
   - If vulnerabilities are detected, add a "Security:" or "Warning:" section
   - Include the CWE ID (e.g., CWE-89) and vulnerability name
   - Briefly explain the risk in plain language
   - Mention the severity level (Critical, High, Medium, Low)

2. MITIGATION GUIDANCE:
   - Include the recommended mitigation in the docstring
   - If a secure alternative is provided, show it as an example
   - Phrase recommendations as actionable items

3. SECURITY CONTEXT:
   - If the component handles sensitive operations (auth, crypto, user input),
     document these security responsibilities
   - Note any input validation requirements
   - Document expected input sources and output sinks

4. FORMATTING:
   - Use "Security:" as the section header for security notes
   - Use "Warning:" for critical vulnerabilities
   - Keep security notes concise but complete
   - Place security section after the main description, before Args

5. PHRASING:
   - Use "Potential vulnerability" or "May be vulnerable to" (static analysis)
   - Be specific: "SQL injection via string formatting" not just "injection"
   - Include line references when available

6. DO NOT:
   - Fabricate security issues beyond what is provided in SECURITY SIGNALS
   - Ignore critical or high severity vulnerabilities
   - Use alarmist language - be factual and professional

Example Security Section:
    Security:
        Warning: Potential SQL injection vulnerability (CWE-89, Critical).
        User input is concatenated into the SQL query at line 42.
        Use parameterized queries instead: cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
"""

    # ------------------------------------------------------------------
    # System prompt (overrides parent to append security addendum)
    # ------------------------------------------------------------------

    def _build_system_prompt(self, style: DocumentationStyle) -> str:
        """Build the system prompt with runtime and security addenda."""
        # Get parent prompt (includes runtime addendum)
        base_prompt = super()._build_system_prompt(style)
        # Add security addendum
        security_addendum = self._build_security_system_addendum()
        return base_prompt + "\n" + security_addendum

    # ------------------------------------------------------------------
    # Security signals block for user prompt
    # ------------------------------------------------------------------

    @staticmethod
    def _format_vulnerability(vuln: VulnerabilitySignal) -> str:
        """Format a single vulnerability signal."""
        lines = []
        severity_emoji = {
            Severity.CRITICAL: "[CRITICAL]",
            Severity.HIGH: "[HIGH]",
            Severity.MEDIUM: "[MEDIUM]",
            Severity.LOW: "[LOW]",
            Severity.INFO: "[INFO]",
        }

        severity_str = severity_emoji.get(vuln.severity, "[UNKNOWN]")
        lines.append(f"  - {severity_str} {vuln.cwe_id}: {vuln.cwe_name}")
        lines.append(f"    Description: {vuln.description}")

        if vuln.line_number:
            lines.append(f"    Location: Line {vuln.line_number}")

        if vuln.code_snippet:
            snippet = vuln.code_snippet[:100].replace('\n', ' ')
            lines.append(f"    Code: {snippet}")

        lines.append(f"    Mitigation: {vuln.mitigation}")

        if vuln.secure_alternative:
            lines.append(f"    Secure alternative: {vuln.secure_alternative}")

        return "\n".join(lines)

    @staticmethod
    def _format_security_block(profile: SecurityProfile) -> str:
        """Format a SecurityProfile into a human-readable prompt block."""
        if profile.is_empty and not profile.has_vulnerabilities:
            return ""

        lines = ["SECURITY SIGNALS (statically detected — document these in the docstring):"]

        # Vulnerabilities (most important)
        if profile.vulnerabilities:
            lines.append("\n  VULNERABILITIES DETECTED:")
            # Sort by severity (critical first)
            sorted_vulns = sorted(
                profile.vulnerabilities,
                key=lambda v: {
                    Severity.CRITICAL: 0,
                    Severity.HIGH: 1,
                    Severity.MEDIUM: 2,
                    Severity.LOW: 3,
                    Severity.INFO: 4,
                }.get(v.severity, 5)
            )
            for vuln in sorted_vulns:
                lines.append(SecurityWriterAgent._format_vulnerability(vuln))

        # Security context
        context_flags = []
        if profile.handles_user_input:
            context_flags.append("handles user/external input")
        if profile.handles_authentication:
            context_flags.append("involved in authentication")
        if profile.handles_authorization:
            context_flags.append("involved in authorization")
        if profile.handles_cryptography:
            context_flags.append("performs cryptographic operations")
        if profile.handles_sensitive_data:
            context_flags.append("processes sensitive data")
        if profile.handles_database:
            context_flags.append("interacts with database")
        if profile.handles_file_operations:
            context_flags.append("performs file operations")
        if profile.handles_network:
            context_flags.append("makes network requests")
        if profile.handles_subprocess:
            context_flags.append("executes subprocesses")

        if context_flags:
            lines.append(f"\n  SECURITY CONTEXT: This component {', '.join(context_flags)}.")

        # Data flow
        if profile.input_sources:
            lines.append(f"  INPUT SOURCES: {', '.join(profile.input_sources)}")
        if profile.output_sinks:
            lines.append(f"  OUTPUT SINKS: {', '.join(profile.output_sinks)}")

        # Positive patterns
        if profile.security_patterns:
            lines.append(f"  SECURITY PATTERNS (good): {', '.join(profile.security_patterns)}")

        # Risk score
        if profile.risk_score > 0:
            lines.append(f"  RISK SCORE: {profile.risk_score:.1f}/10")

        lines.append("")  # trailing newline
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # User prompt (overrides parent to inject security block)
    # ------------------------------------------------------------------

    def _build_user_prompt(
        self,
        component: CodeComponent,
        style: DocumentationStyle,
        reader_context: str,
        searcher_context: str,
        verifier_feedback: Optional[str] = None,
    ) -> str:
        """Build user prompt with runtime and security signal sections."""

        # Get the full base prompt from RuntimeWriterAgent (includes runtime signals)
        base_prompt = super()._build_user_prompt(
            component, style, reader_context, searcher_context,
            verifier_feedback=verifier_feedback,
        )

        # Extract security profile
        profile = self._get_security_profile(component)
        if profile is None or (profile.is_empty and not profile.has_vulnerabilities):
            return base_prompt

        security_block = self._format_security_block(profile)

        # Inject the security block just before SOURCE CODE or RUNTIME SIGNALS
        if "RUNTIME SIGNALS" in base_prompt:
            base_prompt = base_prompt.replace(
                "RUNTIME SIGNALS",
                f"{security_block}\nRUNTIME SIGNALS",
            )
        elif "SOURCE CODE:" in base_prompt:
            base_prompt = base_prompt.replace(
                "SOURCE CODE:",
                f"{security_block}\nSOURCE CODE:",
            )
        else:
            # Fallback: append before the focal code tag
            base_prompt = base_prompt.replace(
                "<FOCAL_CODE>",
                f"{security_block}\n<FOCAL_CODE>",
            )

        return base_prompt

    # ------------------------------------------------------------------
    # Documentation factory (tag as security-aware)
    # ------------------------------------------------------------------

    @staticmethod
    def _create_documentation(
        component: CodeComponent,
        raw_response: str,
        style: DocumentationStyle,
    ) -> Documentation:
        """Wrap in Documentation, tagged as security-aware."""
        # Extract security profile for metadata
        profile = SecurityWriterAgent._get_security_profile(component)
        security_metadata = {}
        if profile:
            security_metadata = {
                "has_vulnerabilities": profile.has_vulnerabilities,
                "vulnerability_count": len(profile.vulnerabilities),
                "risk_score": profile.risk_score,
                "is_security_relevant": profile.is_security_relevant,
            }
            if profile.vulnerabilities:
                security_metadata["vulnerability_summary"] = [
                    {
                        "cwe_id": v.cwe_id,
                        "severity": v.severity.value if hasattr(v.severity, 'value') else v.severity,
                        "line": v.line_number,
                    }
                    for v in profile.vulnerabilities
                ]

        return Documentation(
            component_id=component.id,
            component_name=component.name,
            component_type=component.type.value,
            summary="",
            description="",
            docstring=raw_response,
            style=style.name,
            generated_by="security-writer-agent",
            metadata={
                "component_language": component.language,
                "documentation_style": style.name,
                "is_async": component.is_async,
                "runtime_aware": True,
                "security_aware": True,
                **security_metadata,
            },
        )

    # ------------------------------------------------------------------
    # Main process (identical flow, but uses overridden prompt builders)
    # ------------------------------------------------------------------

    def process(self, context: AgentContext) -> AgentResult:
        """Generate security-aware documentation for a code component."""
        try:
            component = context.component
            style = self._get_style(component)

            # Get security profile for logging
            sec_profile = self._get_security_profile(component)
            vuln_count = len(sec_profile.vulnerabilities) if sec_profile else 0

            self.logger.info(
                f"[SecurityWriter] Generating security-aware docs for "
                f"{component.name} [{component.language}/{style.name}] "
                f"({vuln_count} vulnerabilities)"
            )

            # Gather upstream context
            reader_ctx = self._format_reader_context(context.get_result("reader"))
            searcher_ctx = self._format_searcher_context(context.get_result("searcher"))

            # Build prompts (overridden versions with security signals)
            system_prompt = self._build_system_prompt(style)
            user_prompt = self._build_user_prompt(
                component, style, reader_ctx, searcher_ctx,
            )

            # LLM call
            self.clear_memory()
            self.add_to_memory("system", system_prompt)
            self.add_to_memory("user", user_prompt)

            response = self.generate_response(temperature=0.2, max_tokens=2500)
            self.logger.debug(
                f"[SecurityWriter] Raw response for {component.name}: {response[:500]}"
            )

            documentation = self._create_documentation(component, response, style)
            self._save_output(component, documentation)

            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.SUCCESS,
                output=documentation,
            )
        except Exception as e:
            self.logger.error(f"[SecurityWriter] error: {e}", exc_info=True)
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILED,
                output=None,
                error=str(e),
            )
