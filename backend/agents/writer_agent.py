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
from backend.utils.paths import DATA_ROOT

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
        self.output_dir = DATA_ROOT / "intermediate" / "agent_output" / "writer"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Style helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_style(component: CodeComponent) -> DocumentationStyle:
        """Get the documentation style for a component's language."""
        return get_documentation_style(component.language)

    # ------------------------------------------------------------------
    # Static analysis hints
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_static_hints(source_code: str, language: str) -> Dict[str, bool]:
        """Derive lightweight boolean hints from source code via regex.

        These hints are injected into the user prompt so the LLM can make
        evidence-based decisions without having to infer behaviour.
        """
        lang = _LANGUAGE_ALIASES.get(language.lower().strip(), language.lower().strip())
        code = source_code or ""

        # -- throw / raise detection (literal statements only) --
        # Use negative lookbehind to avoid matching method calls like .toThrow()
        if lang in ("javascript", "typescript"):
            # Match "throw " but not ".toThrow(" or "willThrow "
            detects_throw = bool(re.search(r'(?<![.\w])throw\s+', code))
        elif lang == "python":
            detects_throw = bool(re.search(r'(?<![.\w])raise\s+', code))
        elif lang == "java":
            detects_throw = bool(re.search(r'(?<![.\w])throw\s+', code))
        else:
            detects_throw = bool(re.search(r'(?<![.\w])(throw|raise)\s+', code))

        # -- JS/TS constructor-compatibility patterns --
        uses_instanceof = bool(re.search(r'\binstanceof\b', code))
        modifies_prototype = bool(
            re.search(r'\.prototype\b', code)
            or re.search(r'\bObject\.create\s*\(', code)
        )

        # -- export detection --
        if lang in ("javascript", "typescript"):
            is_exported = bool(
                re.search(r'\bmodule\.exports\b', code)
                or re.search(r'\bexports\.', code)
                or re.search(r'\bexport\s+(default\s+)?', code)
            )
        else:
            is_exported = False  # not reliably detectable in other languages

        # -- async detection (supplement CodeComponent.is_async) --
        uses_await = bool(re.search(r'\bawait\s+', code))

        # -- callback / higher-order function pattern --
        accepts_callback = bool(
            re.search(r'\bcallback\b|\bcb\b|\bfn\b', code)
            and lang in ("javascript", "typescript")
        )

        return {
            "detects_throw": detects_throw,
            "uses_instanceof": uses_instanceof,
            "modifies_prototype": modifies_prototype,
            "is_exported": is_exported,
            "uses_await": uses_await,
            "accepts_callback": accepts_callback,
        }

    @staticmethod
    def _is_trivial_function(source_code: str, language: str) -> bool:
        """Heuristic: detect boilerplate / trivial helper functions.

        A function is considered trivial if it:
          - Has <= 3 non-blank, non-comment body lines, AND
          - Consists only of a single return / assignment / delegation.

        Trivial functions receive a shorter documentation template so the
        LLM does not over-document them.
        """
        if not source_code:
            return False
        lines = [ln.strip() for ln in source_code.splitlines() if ln.strip()]
        # Exclude the signature line(s)
        body_lines = [
            ln for ln in lines
            if not ln.startswith(("def ", "function ", "async ", "export ",
                                 "public ", "private ", "protected ",
                                 "static ", "@", "//", "#", "/*", "*", "}"))
            and ln not in ("{", "}", ")", ");")
        ]
        if len(body_lines) > 3:
            return False
        trivial_patterns = [
            r'^return\s+',          # single return
            r'^this\.\w+\s*=',      # simple field assignment
            r'^self\.\w+\s*=',      # Python field assignment
            r'^\w+\s*=\s*',         # plain assignment
        ]
        for bl in body_lines:
            if not any(re.match(p, bl) for p in trivial_patterns):
                return False
        return True

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
- First line: one-sentence summary beginning with a strong action verb
  (e.g., "Binds", "Creates", "Returns", "Validates", "Wraps", "Ensures", "Asserts", "Bundles", "Narrows").
- Blank line after summary if more sections follow.
- {style.param_tag} {{type}} name - description (for each parameter).
- {style.return_tag} {{type}} description.
- {style.raises_tag} {{Error}} description — MANDATORY when the source contains `throw`.
- Do NOT include /** or */ — they are added by the system.
- Do NOT use Python-specific terms (self, __init__, def, etc.).

DOCUMENTATION PHILOSOPHY (CRITICAL):
Write documentation from the perspective of a developer who will USE this code,
not someone reading the implementation. Every docstring must answer:
  - WHY does this function exist? (purpose and design intent)
  - WHAT should the caller know? (behavioral contract, not implementation)
  - WHAT HAPPENS at the type level? (TypeScript type narrowing, assertion effects)
  - WHEN does behavior change? (environment-specific, conditional paths)
  - WHY are parameters designed this way? (e.g., lazy evaluation via callbacks)

Do NOT merely restate the code structure. Instead, explain:
  - Developer intent behind the design choices
  - Practical usage context and when to call this function
  - TypeScript type-system effects (narrowing, assertion, type guards)
  - Environment-specific behavior differences (dev vs prod, NODE_ENV checks)
  - Why a parameter accepts a function type (lazy/deferred evaluation rationale)

ABSOLUTELY FORBIDDEN TAGS (if ANY of these appear, the output is INVALID):
- @summary — NEVER use. The first line IS the summary. Outputting @summary is a FAILURE.
- @description — NEVER use. The prose paragraph IS the description. Outputting @description is a FAILURE.
- @async (inferred from async keyword)
- @function (inferred from function declaration)
- @method, @name, @kind (redundant metadata)
If you are tempted to write @summary or @description, STOP — the information
already exists in the summary line and prose paragraph. These tags cause
duplication and violate JSDoc/TSDoc best practices.

TYPESCRIPT TYPE RULES (CRITICAL - FOLLOW EXACTLY):
1. PROMISE TYPES - ALWAYS include the generic parameter:
   ✅ CORRECT: {{Promise<string>}}
   ❌ NEVER: {{Promise}} (bare Promise is FORBIDDEN)

2. OBJECT TYPES - Use exact structure from function signature:
   ✅ CORRECT: {{ mode: 'development' | 'production' }}
   ❌ NEVER: {{Object}} or {{object}} (generic Object is FORBIDDEN)

3. UNION TYPES - Use pipe separator:
   ✅ CORRECT: {{string | number}}
   ✅ CORRECT: {{string | (() => string)}}

4. OPTIONAL PARAMETERS - Use square brackets in parameter name:
   ✅ CORRECT: @param {{string}} [message] - Optional parameter

5. ASSERTION SIGNATURES - Use @returns {{void}} and explain narrowing in description:
   ✅ CORRECT: @returns {{void}} Narrows `condition` to truthy via TypeScript's `asserts` keyword.
   ✅ CORRECT: @returns {{void}} Narrows `value` to `string` via `asserts value is string`.
   ❌ NEVER: @returns {{asserts condition}} (not tool-compatible — most JSDoc parsers reject this)

6. ARRAY TYPES:
   ✅ CORRECT: {{string[]}} or {{Array<string>}}
   ❌ NEVER: {{Array}} (bare Array is FORBIDDEN)

DEVELOPER-CONTEXT PATTERNS TO DOCUMENT:
1. ASSERTION / TYPE-NARROWING FUNCTIONS:
   - Use @returns {{void}} — NOT @returns {{asserts condition}} (tooling incompatible).
   - Explain the `asserts` narrowing effect in the DESCRIPTION PARAGRAPH, not in @returns.
   - State the practical effect: "After this call, TypeScript treats `condition`
     as truthy in all subsequent code" (or whatever the narrowing does).
   - Include a concise @example showing the type-narrowing in action.

2. ENVIRONMENT-SPECIFIC BEHAVIOR (process.env.NODE_ENV, etc.):
   - When code branches on environment, describe BOTH paths:
     "In production, throws a stripped error for smaller bundles.
      In development, includes the full diagnostic message."
   - Explain WHY: bundle-size optimization, debugging support, etc.

3. LAZY/DEFERRED PARAMETERS (callbacks for expensive computation):
   - When a parameter accepts `string | (() => string)`, explain the
     lazy evaluation pattern: "Accepts a function to defer expensive
     message computation until the error path is actually reached."
   - State the benefit: avoids unnecessary string concatenation on the
     success path.

4. EXPORTED MODULE ENTRY POINTS:
   - Lead with the module-level purpose and runtime role.
   - For assertion libraries: describe the invariant-checking pattern.

JAVASCRIPT / TYPESCRIPT STRUCTURAL RULES:
- If the function uses `this instanceof` or checks constructor identity,
  note that in the summary.
- If the function modifies `.prototype`, document the prototype augmentation.
- If the function accepts a callback, document the callback signature.
- For exported functions, lead the summary with the module-level purpose.

EXAMPLE 1 - Simple pure function:
Calculates the sum of two numbers.

@param {{number}} x - First number.
@param {{number}} y - Second number.
@returns {{number}} Sum of x and y.

EXAMPLE 2 - Runtime invariant with assertion, env-branching, and lazy message:
Enforces a runtime invariant by asserting that a condition is truthy, enabling
TypeScript to narrow the type of `condition` in subsequent code via the
`asserts condition` return type.

In development, a descriptive error message is thrown when the assertion fails,
aiding debugging. In production, the message is stripped and only a generic
prefix is thrown, minimizing bundle size.

@param {{any}} condition - The value to assert as truthy. After a successful call,
  TypeScript narrows this to a truthy type in the enclosing scope.
@param {{string | (() => string)}} [message] - An optional diagnostic message or
  a function that lazily returns one. Use a function when computing the message
  is expensive, so the cost is only incurred on failure.
@returns {{void}} Narrows `condition` to truthy in all subsequent code via
  TypeScript's `asserts condition` return type.
@throws {{Error}} Throws when `condition` is falsy — with the full message in
  development, or a stripped prefix in production for smaller bundles.
@example
const name: string | null = getName();
invariant(name, 'Name is required');
// TypeScript now knows `name` is `string` (not null)
console.log(name.toUpperCase());

EXAMPLE 3 - Async bundler with object and Promise types:
Bundles TypeScript source with Rollup for the specified environment.

@param {{ mode: 'development' | 'production' }} options - Build configuration
  controlling tree-shaking and minification behavior.
@param {{string}} options.mode - Target environment mode.
@returns {{Promise<string>}} Generated ES module code."""

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
1. Output ONLY the documentation content between <DOCSTRING> and </DOCSTRING>.
2. Do NOT include comment delimiters ({style.comment_prefix}, {style.comment_suffix}).
3. Do NOT include markdown, backticks, analysis, or explanations outside the tags.
4. Do NOT invent behavior not explicitly visible in the source code.
5. Do NOT infer external system behavior.
6. Keep the documentation concise and precise.
7. Only include sections that are directly justified by the code.

STRUCTURAL RULES (CRITICAL):
- Always include a one-sentence summary starting with a strong action verb.
- Include "{style.param_tag}" ONLY if the component has parameters.
- Include "{style.return_tag}" ONLY if the function returns a value or has an explicit return statement.
- Include "{style.raises_tag}" if and ONLY if:
    - The source code contains a literal `throw` (JS/TS/Java) or `raise` (Python) statement.
    - This is MANDATORY when throw/raise is present — NOT optional.
    - Do NOT infer exceptions from indexing, property access, runtime behaviour,
      dictionary lookups, file I/O, JSON parsing, or any implicit operation.
    - Do NOT include {style.raises_tag} for MODULE components (only functions throw).
- Do NOT include empty sections.
- Do NOT include examples unless the code clearly demonstrates usage patterns.
- If behavior is uncertain, omit it rather than guessing.

{format_block}

Summary Precision:
- Begin the summary with a strong, specific action verb (e.g., "Binds",
  "Validates", "Merges", "Wraps", "Delegates", "Returns", "Bundles",
  "Compiles", "Transforms", "Asserts", "Enforces", "Narrows", "Guards").
- NEVER start with generic phrases: "This function is used to...",
  "Helper function that...", "A function that...", "Used to...",
  "Generates code for...", "Generates code based on...", "Provides...".
- For runtime assertions: "Enforces a runtime invariant by asserting..." not just "Asserts X".
- For type guards: "Narrows type to X via..." not "Checks if X".
- For build/bundle: "Bundles TypeScript source with Rollup" not "Generates code".
- Capture the *what*, *why*, and *TypeScript type-system effect* in the summary.

Developer-Context Depth:
- For SIMPLE functions (pure transforms, getters, single return): summary + @param/@returns only.
- For COMPLEX functions (assertions, env-branching, lazy patterns, error handling):
  add a short prose paragraph (2-4 sentences) BETWEEN the summary and the tags
  explaining developer-relevant behavior: type narrowing effects, environment
  differences, lazy evaluation rationale, or error contract.
- NEVER pad simple functions with unnecessary prose.
- ALWAYS add context prose when the function has:
  (a) `asserts` return type — explain type narrowing effect on callers
  (b) environment checks (process.env, NODE_ENV) — describe both paths and WHY
  (c) callback/function parameters for deferred evaluation — explain the lazy pattern
  (d) multiple throw paths with different messages — describe the error contract

Brevity Requirement:
- Simple functions: 3-6 lines (summary + tags).
- Complex functions: 8-18 lines (summary + context paragraph + tags).
- Avoid repeating parameter names in the summary.
- Prefer direct, technical language.

Evidence Constraint:
Every documented behavior must be traceable to visible code.
If you cannot point to a specific statement in the source code that supports a claim, do not include it.
A missing section is always preferable to an invented one.

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
- Module-level side effects if any.
- Do NOT include @throws, @param, or @returns — modules don't have these."""

        if t in (ComponentType.GLOBAL_VARIABLE, ComponentType.STATIC_FIELD,
                 ComponentType.VARIABLE, ComponentType.FIELD):
            return """DOCUMENTING A VARIABLE / CONSTANT:
- Summary ONLY: one sentence describing what the variable represents.
- Do NOT include @param, @returns, @throws, @summary, @description, or @example.
- Do NOT describe function behavior — this is a VARIABLE, not a function.
- If the variable's value is derived from an expression (e.g., process.env),
  describe what the variable holds, NOT what some other function does.
- Keep to 1-2 lines maximum. Variables need minimal documentation."""

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
- Document path parameters, query parameters, request body ONLY if they appear in the function signature.
- Document the return value based on what the function actually returns.
- Include Raises ONLY if the function body explicitly raises an exception (e.g., 'raise HTTPException').
- Do NOT infer exceptions from imports, decorators, or framework conventions.
- Do NOT document status codes unless they are explicitly set in the code.
- Note authentication requirements ONLY if visible in the function body."""

        # FUNCTION / METHOD (default)
        lang = component.language.lower()
        js_extra = ""
        if lang in ("javascript", "typescript", "js", "ts"):
            js_extra = """
- If the function uses `instanceof` checks or guards constructor invocation,
  state that in the summary (e.g., "Ensures invocation as a constructor.").
- If the function modifies `.prototype`, describe the augmentation.
- For exported module entry points, lead with the module-level purpose."""

        return f"""DOCUMENTING A FUNCTION / METHOD:
- Summary: Begin with a strong action verb describing the primary operation.
- Document parameters if present.
- Document return value if present or explicitly returned.
- Include @throws / Raises ONLY if the body contains a literal throw/raise.
- Mention side effects only if the code performs I/O, state mutation, or external calls.
- Keep documentation minimal and precise.{js_extra}"""

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

        # --- Static analysis hints ---
        hints = self._compute_static_hints(component.source_code, component.language)
        is_trivial = self._is_trivial_function(component.source_code, component.language)

        hint_lines = ["STATIC ANALYSIS HINTS (pre-computed from source):"]
        hint_lines.append(f"  detects_throw   = {hints['detects_throw']}")
        hint_lines.append(f"  uses_instanceof = {hints['uses_instanceof']}")
        hint_lines.append(f"  modifies_prototype = {hints['modifies_prototype']}")
        hint_lines.append(f"  is_exported     = {hints['is_exported']}")
        hint_lines.append(f"  uses_await      = {hints['uses_await']}")
        hint_lines.append(f"  accepts_callback = {hints['accepts_callback']}")
        hint_lines.append(f"  is_trivial      = {is_trivial}")
        hint_block = "\n".join(hint_lines)

        # Conditional guidance based on hints
        hint_guidance_parts: List[str] = []
        if component.type == ComponentType.MODULE:
            hint_guidance_parts.append(
                f">> COMPONENT IS A MODULE — do NOT include {style.raises_tag}, "
                f"@param, or {style.return_tag} sections. Modules don't throw or return."
            )
        elif not hints["detects_throw"]:
            hint_guidance_parts.append(
                f">> detects_throw is FALSE — do NOT include a "
                f"{style.raises_tag} section."
            )
        else:
            hint_guidance_parts.append(
                f">> CRITICAL: detects_throw is TRUE — you MUST include a {style.raises_tag} "
                f"section. This is MANDATORY, not optional. Document only the exceptions "
                f"that are literally thrown in the source code."
            )
        if hints["uses_instanceof"]:
            hint_guidance_parts.append(
                ">> uses_instanceof is TRUE — mention constructor-invocation "
                "guarding in the summary if applicable."
            )
        if hints["modifies_prototype"]:
            hint_guidance_parts.append(
                ">> modifies_prototype is TRUE — describe the prototype "
                "augmentation in the summary."
            )
        if hints["is_exported"]:
            hint_guidance_parts.append(
                ">> is_exported is TRUE — lead the summary with the "
                "module-level purpose."
            )
        if hints["accepts_callback"]:
            hint_guidance_parts.append(
                ">> accepts_callback is TRUE — document the expected "
                "callback signature if inferable."
            )
        if is_trivial:
            hint_guidance_parts.append(
                ">> is_trivial is TRUE — keep documentation to a single "
                "summary line plus @param/@returns. No extra prose."
            )
        hint_guidance = "\n".join(hint_guidance_parts)

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

        # Return type metadata (important for TypeScript assertion signatures)
        return_info = ""
        if component.return_type:
            return_info = f"Return type: {component.return_type}"
            if "asserts" in component.return_type.lower():
                return_info += "\n  >> ASSERTION SIGNATURE: Use @returns {void} — NOT @returns {asserts ...} (tooling incompatible)."
                return_info += "\n  >> Explain the type-narrowing effect in the DESCRIPTION PARAGRAPH."
                return_info += "\n  >> In @returns, write: @returns {void} Narrows `X` to truthy/type via `asserts`."
                return_info += "\n  >> Include a concise @example showing type narrowing in action."
            if "promise" in component.return_type.lower():
                return_info += "\n  >> CRITICAL: This returns a Promise — you MUST include the generic type parameter in @returns."
                return_info += "\n     Example: {Promise<string>}, NEVER bare {Promise}."
        
        # Detect environment-branching patterns
        env_hint = ""
        if component.source_code:
            src = component.source_code
            if re.search(r'process\.env\.NODE_ENV|process\.env\[', src) or \
               re.search(r"\bisProduction\b|\bisDev\b|\b__DEV__\b", src):
                env_hint = ("\n>> ENVIRONMENT-BRANCHING DETECTED: This code behaves differently in "
                           "development vs production. You MUST describe both paths and explain "
                           "WHY (e.g., bundle-size optimization, debugging support).")
        
        # Detect lazy evaluation parameters
        lazy_hint = ""
        if component.source_code and component.parameters:
            src = component.source_code
            if re.search(r'typeof\s+\w+\s*===?\s*[\'"]function[\'"]', src):
                lazy_hint = ("\n>> LAZY EVALUATION PATTERN DETECTED: A parameter is checked with typeof === 'function'. "
                           "Explain WHY a callback is accepted — deferred/lazy computation so the cost "
                           "is only incurred when the value is actually needed (e.g., on error paths).")
        
        # Detect object types in signature
        signature_hint = ""
        if component.parameters and component.signature:
            sig_text = component.signature or ""
            if "{" in sig_text and "}" in sig_text:
                signature_hint = "\n>> DETECTED OBJECT TYPE IN SIGNATURE — use the exact structure in @param, NEVER {Object}."
        
        # Combine all extra hints
        extra_hints = env_hint + lazy_hint + signature_hint

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
{return_info}{extra_hints}

{hint_block}

{hint_guidance}

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
4. Only document what is visible in the code.
5. If detects_throw is TRUE, you MUST include {style.raises_tag} — this is MANDATORY.
6. Do NOT infer exceptions from imports, type hints, decorators, or framework behavior.
7. For Promise return types, ALWAYS include the generic parameter: {{Promise<string>}}, NEVER bare {{Promise}}.
8. For object parameters, use the exact TypeScript type from the signature, NEVER {{Object}}.
9. Start the summary with a strong action verb — no generic preambles.
10. For MODULE or VARIABLE components, do NOT include @throws, @param, or @returns.
11. Write from the CALLER's perspective — explain developer intent, not implementation details.
12. For `asserts` return types: use @returns {{void}} and explain narrowing in the description paragraph.
13. If code branches on NODE_ENV or environment, describe BOTH paths and WHY they differ.
14. If a parameter accepts `string | (() => string)`, explain the lazy evaluation benefit.
15. For assertion/type-narrowing functions, include @example showing the narrowing in action.
16. NEVER output @summary or @description tags — these are FORBIDDEN and cause duplication.
17. Do NOT duplicate inline comments that already exist in the source code parameters.
18. For VARIABLE/CONSTANT components: output a 1-line summary ONLY, no tags."""

    # ------------------------------------------------------------------
    # Post-processing: strip forbidden tags from LLM output
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_docstring(raw: str) -> str:
        """Remove forbidden/redundant tags the LLM may emit despite instructions.

        Strips @summary, @description, and their content lines to prevent
        duplication with the summary line and prose paragraph.
        """
        lines = raw.split('\n')
        cleaned: List[str] = []
        skip_block = False
        for line in lines:
            stripped = line.strip()
            # Detect @summary or @description lines and skip them
            if re.match(r'^@summary\b', stripped) or re.match(r'^@description\b', stripped):
                skip_block = True
                continue
            # If we were skipping a block, stop when we hit the next @ tag or blank line
            if skip_block:
                if stripped == '' or (stripped.startswith('@') and not stripped.startswith('@summary') and not stripped.startswith('@description')):
                    skip_block = False
                    # Keep this line (it's the next valid section)
                    # But if it's a blank line following the removed block, also skip to avoid double-blanks
                    if stripped == '' and cleaned and cleaned[-1].strip() == '':
                        continue
                else:
                    continue
            cleaned.append(line)
        return '\n'.join(cleaned)

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

            # Post-process: strip forbidden tags (@summary, @description)
            response = self._sanitize_docstring(response)

            # Wrap in Documentation object
            documentation = self._create_documentation(component, response, style)
            self._save_output(component, documentation)

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

            # Post-process: strip forbidden tags (@summary, @description)
            response = self._sanitize_docstring(response)

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
