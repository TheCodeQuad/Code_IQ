"""
Writer Agent - Language-Aware Documentation Generator
Generates high-quality docstrings with language-specific formatting,
structured context from Reader/Searcher agents, and iterative refinement.
"""
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from backend.agents.base_agent import BaseAgent, AgentContext, AgentResult, AgentStatus
from backend.models.code_component import CodeComponent, ComponentType
from backend.models.documentation import Documentation
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Language-specific documentation styles
# ---------------------------------------------------------------------------

@dataclass
class DocumentationStyle:
    """Language-specific documentation style configuration."""
    name: str           # e.g. "google", "jsdoc", "tsdoc", "javadoc"
    language: str       # e.g. "python", "javascript"
    comment_prefix: str # e.g. '\"\"\"', '/**'
    comment_suffix: str # e.g. '\"\"\"', ' */'
    param_tag: str      # e.g. "Args:", "@param"
    return_tag: str     # e.g. "Returns:", "@returns"
    raises_tag: str     # e.g. "Raises:", "@throws"
    example_tag: str    # e.g. "Examples:", "@example"


DOCUMENTATION_STYLES: Dict[str, DocumentationStyle] = {
    "python": DocumentationStyle(
        name="google", language="python",
        comment_prefix='"""', comment_suffix='"""',
        param_tag="Args:", return_tag="Returns:",
        raises_tag="Raises:", example_tag="Examples:",
    ),
    "javascript": DocumentationStyle(
        name="jsdoc", language="javascript",
        comment_prefix="/**", comment_suffix=" */",
        param_tag="@param", return_tag="@returns",
        raises_tag="@throws", example_tag="@example",
    ),
    "typescript": DocumentationStyle(
        name="tsdoc", language="typescript",
        comment_prefix="/**", comment_suffix=" */",
        param_tag="@param", return_tag="@returns",
        raises_tag="@throws", example_tag="@example",
    ),
    "java": DocumentationStyle(
        name="javadoc", language="java",
        comment_prefix="/**", comment_suffix=" */",
        param_tag="@param", return_tag="@return",
        raises_tag="@throws", example_tag="{@code",
    ),
    "c": DocumentationStyle(
        name="doxygen", language="c",
        comment_prefix="/**", comment_suffix=" */",
        param_tag="@param", return_tag="@return",
        raises_tag="@throws", example_tag="@code",
    ),
    "go": DocumentationStyle(
        name="godoc", language="go",
        comment_prefix="//", comment_suffix="",
        param_tag="", return_tag="",
        raises_tag="", example_tag="",
    ),
    "rust": DocumentationStyle(
        name="rustdoc", language="rust",
        comment_prefix="///", comment_suffix="",
        param_tag="# Arguments", return_tag="# Returns",
        raises_tag="# Panics", example_tag="# Examples",
    ),
}

_LANGUAGE_ALIASES: Dict[str, str] = {
    "js": "javascript", "jsx": "javascript",
    "ts": "typescript", "tsx": "typescript",
    "py": "python", "cpp": "c", "c++": "c",
    "rs": "rust",
}


def get_documentation_style(language: str) -> DocumentationStyle:
    """Resolve language string to a DocumentationStyle (defaults to Python/Google)."""
    lang = _LANGUAGE_ALIASES.get(language.lower().strip(), language.lower().strip())
    return DOCUMENTATION_STYLES.get(lang, DOCUMENTATION_STYLES["python"])


# ---------------------------------------------------------------------------
# Writer Agent
# ---------------------------------------------------------------------------

class WriterAgent(BaseAgent):
    """
    Language-aware documentation writer agent.

    Pipeline:
        1. Resolve language-specific documentation style
        2. Format reader/searcher context into structured prompt sections
        3. Build system + user prompts tailored to component type & language
        4. Single LLM call via BaseAgent memory API
        5. Wrap raw response in Documentation object
        6. Persist output to data/intermediate/agent_output/writer/

    The raw LLM response (containing <DOCSTRING> tags) is stored in
    Documentation.docstring so that the downstream DocstringInserter can
    extract and clean it as usual.
    """

    def __init__(self):
        super().__init__("writer")
        self.output_dir = Path("data/intermediate/agent_output/writer")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Style helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_style(component: CodeComponent) -> DocumentationStyle:
        """Get the documentation style for a component's language."""
        return get_documentation_style(component.language)

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    def _build_system_prompt(self, style: DocumentationStyle) -> str:
        """Build a language-aware system prompt with concrete format examples."""

        if style.language == "python":
            format_block = """FORMAT: Google-style Python docstring (NO triple quotes).
- First line: one-sentence summary.
- Blank line after summary if more sections follow.
- Args: section for parameters (indented 4 spaces under heading).
- Returns: section for return value.
- Raises: section for exceptions.
- Do NOT include triple quotes — they are added by the system.

EXAMPLE OUTPUT FORMAT:
Calculate the sum of two numbers.

Args:
    x (int): First number.
    y (int): Second number.

Returns:
    int: Sum of x and y."""

        elif style.language in ("javascript", "typescript"):
            format_block = f"""FORMAT: JSDoc/TSDoc-style documentation (NO comment delimiters).
- First line: one-sentence summary.
- Blank line after summary if more sections follow.
- {style.param_tag} {{{{type}}}} name - description (for each parameter).
- {style.return_tag} {{{{type}}}} description.
- {style.raises_tag} {{{{type}}}} description (if applicable).
- Do NOT include /** or */ — they are added by the system.
- Do NOT use Python-specific terms (self, __init__, def, etc.).

EXAMPLE OUTPUT FORMAT:
Calculates the sum of two numbers.

@param {{number}} x - First number.
@param {{number}} y - Second number.
@returns {{number}} Sum of x and y."""

        elif style.language == "java":
            format_block = """FORMAT: Javadoc-style documentation (NO comment delimiters).
- First line: one-sentence summary.
- Blank line after summary if more sections follow.
- @param name description.
- @return description.
- @throws ExceptionType description.
- Do NOT include /** or */ — they are added by the system.

EXAMPLE OUTPUT FORMAT:
Calculates the sum of two integers.

@param x the first integer
@param y the second integer
@return the sum of x and y"""

        else:
            format_block = f"""FORMAT: Standard documentation for {style.language}.
- First line: one-sentence summary.
- Additional description if needed.
- Document parameters, return values, and exceptions as appropriate
  using the conventions of {style.language}."""

        return f"""You are a precise code documentation generator for {style.language}.

STRICT RULES:
1. Output ONLY the documentation content between <DOCSTRING> and </DOCSTRING> tags.
2. Do NOT include comment delimiters ({style.comment_prefix}, {style.comment_suffix}).
3. Do NOT include markdown code fences, backticks, or extra formatting.
4. Do NOT include analysis, reasoning, or commentary outside the tags.
5. Do NOT invent behavior not visible in the source code.
6. Do NOT reference constructs or terminology from other languages.
7. If something cannot be determined from the code, omit it entirely.

{format_block}

CRITICAL: Your ENTIRE useful output must be wrapped in <DOCSTRING>...</DOCSTRING> tags."""

    # ------------------------------------------------------------------
    # Component-type instructions
    # ------------------------------------------------------------------

    @staticmethod
    def _build_type_instructions(component: CodeComponent) -> str:
        """Return component-type-specific documentation guidance."""

        t = component.type

        if t == ComponentType.CLASS:
            return """DOCUMENTING A CLASS:
- Summary: What the class represents and its role.
- Attributes with types and descriptions (if observable).
- Constructor parameters (Args) if applicable.
- Inheritance relationships if visible.
- Do NOT document individual methods here."""

        if t == ComponentType.MODULE:
            return """DOCUMENTING A MODULE:
- Summary: What the module provides.
- Key exports / public components.
- Module-level side effects if any."""

        if t in (ComponentType.GLOBAL_VARIABLE, ComponentType.STATIC_FIELD,
                 ComponentType.VARIABLE, ComponentType.FIELD):
            return """DOCUMENTING A VARIABLE / CONSTANT:
- Summary: What the variable represents and its purpose.
- Constraints or valid value ranges if apparent.
- Do NOT include Args, Returns, or Raises sections."""

        if t == ComponentType.CONSTRUCTOR:
            return """DOCUMENTING A CONSTRUCTOR:
- Summary: What object is created and under what conditions.
- Document all parameters.
- Note side effects of construction."""

        if t == ComponentType.API_ENDPOINT:
            extra = ""
            if component.http_method:
                extra += f"\n- HTTP method: {component.http_method}"
            if component.http_path:
                extra += f"\n- Path: {component.http_path}"
            return f"""DOCUMENTING AN API ENDPOINT:
- Summary: What the endpoint does.{extra}
- Document path parameters, query parameters, request body.
- Document response model and status codes.
- Note authentication requirements if visible."""

        # FUNCTION / METHOD (default)
        return """DOCUMENTING A FUNCTION / METHOD:
- Summary: What action it performs and the outcome.
- Args: all parameters with types.
- Returns: return value with type (omit if void/None).
- Raises / Throws: exceptions that may be raised.
- Side effects if any."""

    # ------------------------------------------------------------------
    # Context formatting (Reader / Searcher)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_reader_context(reader_output: Any) -> str:
        """Extract useful Reader information for the prompt."""
        if not reader_output:
            return ""

        # Handle XML string (primary format from Reader)
        if isinstance(reader_output, str):
            parts: List[str] = []
            complexity_m = re.search(
                r'<COMPLEXITY>(.*?)</COMPLEXITY>', reader_output, re.DOTALL
            )
            if complexity_m:
                parts.append(f"Complexity: {complexity_m.group(1).strip()}")

            info_m = re.search(
                r'<INFO_NEED>(.*?)</INFO_NEED>', reader_output, re.DOTALL
            )
            if info_m:
                parts.append(f"Info needs: {info_m.group(1).strip()}")
            return "\n".join(parts)

        # Handle ReaderOutput dataclass
        if hasattr(reader_output, 'xml_output'):
            return WriterAgent._format_reader_context(reader_output.xml_output)

        return str(reader_output)[:1000]

    @staticmethod
    def _format_searcher_context(searcher_output: Any) -> str:
        """Format Searcher output into a readable context block."""
        if not searcher_output:
            return ""

        sections: List[str] = []

        # SearcherOutput dataclass
        if hasattr(searcher_output, 'dependency_contexts'):
            deps = searcher_output.dependency_contexts
            if deps:
                lines = ["Dependencies:"]
                for dep in deps:
                    name = getattr(dep, 'component_name', str(dep))
                    sig = getattr(dep, 'signature', '')
                    summary = getattr(dep, 'summary', '')
                    lines.append(f"  - {name}: {sig}")
                    if summary:
                        lines.append(f"    {summary}")
                sections.append("\n".join(lines))

        if hasattr(searcher_output, 'reference_contexts'):
            refs = searcher_output.reference_contexts
            if refs:
                lines = ["Usage references:"]
                for ref in refs:
                    name = getattr(ref, 'component_name', str(ref))
                    usage = getattr(ref, 'usage_summary', '')
                    lines.append(f"  - {name}: {usage}")
                sections.append("\n".join(lines))

        if hasattr(searcher_output, 'external_contexts'):
            exts = searcher_output.external_contexts
            if exts:
                lines = ["External context:"]
                for ext in exts:
                    query = getattr(ext, 'query', str(ext))
                    summary = getattr(ext, 'summary', '')
                    lines.append(f"  - {query}: {summary}")
                sections.append("\n".join(lines))

        # Legacy dict format
        if isinstance(searcher_output, dict):
            for key in ('internal', 'external'):
                data = searcher_output.get(key)
                if data:
                    sections.append(
                        f"{key.title()} context:\n"
                        + json.dumps(data, indent=2, default=str)[:1000]
                    )

        # Raw string fallback
        if isinstance(searcher_output, str):
            sections.append(searcher_output[:2000])

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # User prompt builder
    # ------------------------------------------------------------------

    def _build_user_prompt(
        self,
        component: CodeComponent,
        style: DocumentationStyle,
        reader_context: str,
        searcher_context: str,
        verifier_feedback: Optional[str] = None,
    ) -> str:
        """Assemble the user prompt with code, context, and instructions."""

        type_instructions = self._build_type_instructions(component)

        # Parameter metadata
        param_info = ""
        if component.parameters:
            lines = ["Known parameters:"]
            for p in component.parameters:
                if hasattr(p, 'name'):
                    t = f" ({p.type_hint})" if getattr(p, 'type_hint', None) else ""
                    d = f" = {p.default_value}" if getattr(p, 'default_value', None) else ""
                    lines.append(f"  - {p.name}{t}{d}")
                else:
                    lines.append(f"  - {p}")
            param_info = "\n".join(lines)

        # Gather context sections
        ctx_parts: List[str] = []
        if reader_context:
            ctx_parts.append(f"Reader analysis:\n{reader_context}")
        if searcher_context:
            ctx_parts.append(f"Gathered context:\n{searcher_context}")
        context_block = "\n\n".join(ctx_parts) if ctx_parts else "No additional context."

        # Optional refinement block
        refinement_block = ""
        if verifier_feedback:
            refinement_block = f"""
REFINEMENT REQUEST:
Fix ALL listed issues while preserving correct parts.
Feedback:
{verifier_feedback}
"""

        async_note = "ASYNC: Yes" if component.is_async else ""

        return f"""{type_instructions}

TARGET LANGUAGE: {style.language}
DOCUMENTATION STYLE: {style.name}
COMPONENT TYPE: {component.type.value}
COMPONENT NAME: {component.name}
{async_note}
{param_info}

AVAILABLE CONTEXT:
{context_block}
{refinement_block}
SOURCE CODE:
<FOCAL_CODE>
{component.source_code}
</FOCAL_CODE>

Generate the documentation now. Remember:
1. Wrap output in <DOCSTRING> and </DOCSTRING> tags.
2. Do NOT include comment delimiters ({style.comment_prefix} / {style.comment_suffix}).
3. Do NOT include triple quotes, code fences, or markdown formatting.
4. Only document what is visible in the code."""

    # ------------------------------------------------------------------
    # Documentation object factory
    # ------------------------------------------------------------------

    @staticmethod
    def _create_documentation(
        component: CodeComponent,
        raw_response: str,
        style: DocumentationStyle,
    ) -> Documentation:
        """Wrap the raw LLM response in a Documentation dataclass.

        The raw response (with <DOCSTRING> XML tags) is stored in
        `Documentation.docstring` so the DocstringInserter can extract
        and clean it downstream.
        """
        return Documentation(
            component_id=component.id,
            component_name=component.name,
            component_type=component.type.value,
            summary="",       # populated by downstream processing
            description="",
            docstring=raw_response,
            style=style.name,
            generated_by="writer-agent",
            metadata={
                "component_language": component.language,
                "documentation_style": style.name,
                "is_async": component.is_async,
            },
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_output(self, component: CodeComponent, doc: Documentation) -> None:
        """Persist writer output to data/intermediate/agent_output/writer/."""
        try:
            output_data = {
                "component_id": component.id,
                "component_name": component.name,
                "component_type": component.type.value,
                "language": component.language,
                "docstring": doc.docstring,
                "style": doc.style,
                "generated_at": datetime.now().isoformat(),
            }
            safe = re.sub(r'[^\w\-.]', '_', component.name)
            path = self.output_dir / f"{safe}_{component.id[:8]}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"Saved writer output to {path}")
        except Exception as e:
            self.logger.warning(f"Failed to save writer output: {e}")

    # ------------------------------------------------------------------
    # Main process
    # ------------------------------------------------------------------

    def process(self, context: AgentContext) -> AgentResult:
        """Generate documentation for a code component.

        Returns an AgentResult whose *output* is a ``Documentation`` object.
        ``Documentation.docstring`` contains the raw LLM response (with
        <DOCSTRING> XML tags) for the DocstringInserter to extract.
        """
        try:
            component = context.component
            style = self._get_style(component)
            self.logger.info(
                f"Generating docs for {component.name} "
                f"[{component.language}/{style.name}]"
            )

            # Gather upstream context
            reader_ctx = self._format_reader_context(context.get_result('reader'))
            searcher_ctx = self._format_searcher_context(context.get_result('searcher'))

            # Build prompts
            system_prompt = self._build_system_prompt(style)
            user_prompt = self._build_user_prompt(
                component, style, reader_ctx, searcher_ctx
            )

            # LLM call via BaseAgent memory API
            self.clear_memory()
            self.add_to_memory("system", system_prompt)
            self.add_to_memory("user", user_prompt)

            response = self.generate_response(temperature=0.2, max_tokens=2000)
            self.logger.debug(f"Raw LLM response for {component.name}: {response[:500]}")

            # Wrap in Documentation object
            documentation = self._create_documentation(component, response, style)
            self._save_output(component, documentation)

            # Log the generated docstring
            self.logger.info(
                f"Generated docstring for {component.name} ({len(documentation.docstring)} chars): "
                f"{documentation.docstring[:150]}..."
            )

            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.SUCCESS,
                output=documentation,
            )

        except Exception as e:
            self.logger.error(f"Writer agent error: {e}", exc_info=True)
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILED,
                output=None,
                error=str(e),
            )

    # ------------------------------------------------------------------
    # Refinement (called by orchestrator after verifier feedback)
    # ------------------------------------------------------------------

    def refine_documentation(
        self,
        context: AgentContext,
        verifier_feedback: str,
    ) -> AgentResult:
        """Re-generate documentation incorporating verifier feedback.

        Args:
            context: AgentContext with component and prior agent results.
            verifier_feedback: Plain-text feedback from the Verifier agent.

        Returns:
            AgentResult with a refined Documentation object.
        """
        try:
            component = context.component
            style = self._get_style(component)
            self.logger.info(f"Refining docs for {component.name}")
            self.logger.info(f"Verifier feedback: {verifier_feedback}")

            reader_ctx = self._format_reader_context(context.get_result('reader'))
            searcher_ctx = self._format_searcher_context(context.get_result('searcher'))

            system_prompt = self._build_system_prompt(style)
            user_prompt = self._build_user_prompt(
                component, style, reader_ctx, searcher_ctx,
                verifier_feedback=verifier_feedback,
            )

            self.clear_memory()
            self.add_to_memory("system", system_prompt)
            self.add_to_memory("user", user_prompt)

            response = self.generate_response(temperature=0.2, max_tokens=2000)

            documentation = self._create_documentation(component, response, style)
            self._save_output(component, documentation)

            # Log the refined docstring
            self.logger.info(
                f"Refined docstring for {component.name} ({len(documentation.docstring)} chars): "
                f"{documentation.docstring[:150]}..."
            )

            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.SUCCESS,
                output=documentation,
            )
        except Exception as e:
            self.logger.error(f"Refinement error: {e}", exc_info=True)
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILED,
                output=None,
                error=str(e),
            )
