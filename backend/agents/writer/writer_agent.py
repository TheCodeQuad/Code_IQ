"""
Writer Agent - Simplified Architecture (Meta-inspired)
Generates high-quality docstrings using clear prompts and XML tag extraction
"""
import re
from typing import Dict, Any, Optional

from backend.agents.base_agent import BaseAgent, AgentContext, AgentResult, AgentStatus
from backend.models.code_component import CodeComponent, ComponentType
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class WriterAgent(BaseAgent):
    """
    Writer Agent that generates docstrings (Meta-inspired architecture).
    
    Architecture:
    1. Receive source code + searcher context
    2. Select appropriate prompt based on component type
    3. Single LLM call with context
    4. Extract docstring from XML tags
    5. Return just the docstring string for direct insertion
    
    Benefits: Simple, maintainable, language-agnostic
    """

    def __init__(self):
        super().__init__("writer")
        
        # Base prompt that applies to all documentation
        self.base_prompt = """You are a Writer agent responsible for generating high-quality 
docstrings that are both complete and helpful. Accessible context is provided to you for 
generating the docstring.

General Guidelines:
1. Make docstrings actionable and specific:
   - Focus on practical usage
   - Highlight important considerations
   - Include warnings or gotchas

2. Use clear, concise language:
   - Avoid jargon unless necessary
   - Use active voice
   - Be direct and specific

3. Type Information:
   - Include precise type hints
   - Note any type constraints
   - Document generic type parameters

4. Context and Integration:
   - Explain component relationships
   - Note any dependencies
   - Describe side effects

5. Follow Google docstring format:
   - Use consistent indentation
   - Maintain clear section separation
   - Keep related information grouped"""

        # Class-specific prompt
        self.class_prompt = """You are documenting a CLASS. Focus on describing the object it represents 
and its role in the system.

Required sections:
1. Summary: 
   - One-line description focusing on WHAT the class represents
   - Avoid repeating the class name or obvious terms
   - Focus on the core purpose or responsibility

2. Description: 
   - WHY: Explain the motivation and purpose behind this class
   - WHEN: Describe scenarios or conditions where this class should be used
   - WHERE: Explain how it fits into the larger system architecture
   - HOW: Provide a high-level overview of how it achieves its purpose

3. Example: 
   - Show a practical, real-world usage scenario
   - Include initialization and common method calls
   - Demonstrate typical workflow

Conditional sections:
1. Attributes (if class has attributes):
   - Explain the purpose and significance of each attribute
   - Include type information and valid values
   - Note any dependencies between attributes

2. Args (if class's __init__ has parameters):
   - Focus on explaining the significance of each parameter
   - Include valid value ranges or constraints
   - Explain parameter relationships if they exist"""

        # Function/Method-specific prompt
        self.function_prompt = """You are documenting a FUNCTION or METHOD. Focus on describing 
the action it performs and its effects.

Required sections:
1. Summary:
   - One-line description focusing on WHAT the function does
   - Avoid repeating the function name
   - Emphasize the outcome or effect

2. Description:
   - WHY: Explain the purpose and use cases
   - WHEN: Describe when to use this function
   - WHERE: Explain how it fits into the workflow
   - HOW: Provide high-level implementation approach

Conditional sections:
1. Args (if present):
   - Explain the significance of each parameter
   - Include valid value ranges or constraints
   - Note any parameter interdependencies

2. Returns (if not None):
   - Explain what the return value represents
   - Include possible return values or ranges
   - Note any conditions affecting the return value

3. Raises (if exceptions are raised):
   - List specific conditions triggering each exception
   - Explain how to prevent or handle exceptions

4. Examples (if public and not abstract):
   - Show practical usage scenarios
   - Include common parameter combinations
   - Demonstrate error handling if relevant"""

        # Global variable prompt
        self.global_prompt = """You are documenting a GLOBAL VARIABLE or CONSTANT.

Required sections:
1. Summary:
   - One-line description of what this variable represents
   - Focus on its PURPOSE, not its value

2. Description:
   - Explain the impact of this variable on the system
   - Note any constraints or valid value ranges
   - Describe what depends on this variable

Note: Do NOT include Args, Returns, or Raises sections for global variables."""

    @staticmethod
    def is_class_component(component: CodeComponent) -> bool:
        """Determine if the given component is a class definition.
        
        Args:
            component: The code component to analyze
            
        Returns:
            bool: True if the component is a class definition
        """
        return component.type == ComponentType.CLASS

    @staticmethod
    def is_global_component(component: CodeComponent) -> bool:
        """Determine if the given component is a global variable.
        
        Args:
            component: The code component to analyze
            
        Returns:
            bool: True if the component is a global variable
        """
        return component.type == ComponentType.GLOBAL_VARIABLE

    def get_custom_prompt(self, component: CodeComponent) -> str:
        """Get the appropriate prompt based on the component type.
        
        Args:
            component: The code component to analyze
            
        Returns:
            str: The appropriate prompt for the component type
        """
        if self.is_global_component(component):
            return self.global_prompt
        elif self.is_class_component(component):
            return self.class_prompt
        else:
            return self.function_prompt

    def extract_docstring(self, response: str) -> str:
        """Extract the docstring from the LLM response.
        
        Args:
            response: The full response from the LLM containing the docstring between XML tags
            
        Returns:
            str: The extracted docstring, or empty string if extraction fails
        """
        # Log full response at INFO level for debugging
        self.logger.info(f"LLM Response length: {len(response)} chars")
        self.logger.info(f"LLM Response preview: {response[:500]}...")
        
        # Try both uppercase and lowercase tags
        for start_tag, end_tag in [
            ("<DOCSTRING>", "</DOCSTRING>"),
            ("<docstring>", "</docstring>"),
            ("<Docstring>", "</Docstring>"),
        ]:
            try:
                # Case-insensitive search
                response_lower = response.lower()
                start_tag_lower = start_tag.lower()
                end_tag_lower = end_tag.lower()
                
                start_idx = response_lower.index(start_tag_lower) + len(start_tag_lower)
                end_idx = response_lower.index(end_tag_lower)
                
                # Extract using original response (preserving case in content)
                docstring = response[start_idx:end_idx].strip()
                
                self.logger.info(f"Extracted docstring ({len(docstring)} chars): {docstring[:200]}...")
                
                # Validate we got something meaningful (at least 5 words)
                word_count = len(docstring.split())
                if word_count < 5:
                    self.logger.warning(
                        f"Extracted docstring is too short ({word_count} words): '{docstring}'"
                    )
                    # Try to find if there's actual content after the tag
                    self.logger.info(f"Content after end tag: {response[end_idx+len(end_tag):end_idx+len(end_tag)+200]}")
                    return ""
                
                return docstring
                
            except (ValueError, IndexError):
                continue
        
        # No tags found - log the full response for debugging
        self.logger.warning(f"No XML tags found. Full response:\n{response}")
        return ""

    def _build_context_string(
        self,
        component: CodeComponent,
        searcher_output: Optional[Any] = None
    ) -> str:
        """Build a context string from component and searcher output.
        
        Args:
            component: The code component being documented
            searcher_output: Optional SearcherOutput object from the Searcher agent
            
        Returns:
            str: Formatted context string for the LLM
        """
        context_parts = []
        
        # Component metadata
        context_parts.append(f"Component Type: {component.type.value}")
        context_parts.append(f"Language: {component.language}")
        
        if component.signature:
            context_parts.append(f"Signature: {component.signature}")
        
        if component.return_type:
            context_parts.append(f"Return Type: {component.return_type}")
        
        if component.parameters:
            params_str = ", ".join([
                f"{p.name}: {p.type_hint or 'Any'}" + (f" = {p.default_value}" if p.default_value else "")
                for p in component.parameters
            ])
            context_parts.append(f"Parameters: {params_str}")
        
        if component.decorators:
            context_parts.append(f"Decorators: {', '.join(component.decorators)}")
        
        if component.is_async:
            context_parts.append("Note: This is an async function")
        
        if component.is_generator:
            context_parts.append("Note: This is a generator function")
        
        # Class-specific context
        if component.type == ComponentType.CLASS:
            if component.parent_classes:
                context_parts.append(f"Inherits from: {', '.join(component.parent_classes)}")
            if component.attributes:
                attrs_str = ", ".join([
                    f"{a.get('name')}: {a.get('type', 'Any')}"
                    for a in component.attributes[:10]
                ])
                context_parts.append(f"Attributes: {attrs_str}")
            if component.methods:
                context_parts.append(f"Methods: {', '.join(component.methods[:10])}")
        
        # Dependencies context from Searcher (handle SearcherOutput dataclass)
        if searcher_output:
            # Handle SearcherOutput dataclass
            if hasattr(searcher_output, 'dependency_contexts'):
                # Process dependency contexts
                if searcher_output.dependency_contexts:
                    context_parts.append("\n--- Dependencies ---")
                    for dep in searcher_output.dependency_contexts[:5]:  # Limit to 5
                        context_parts.append(f"\n{dep.component_name}:")
                        if dep.signature:
                            context_parts.append(f"  Signature: {dep.signature}")
                        if dep.summary:
                            context_parts.append(f"  Summary: {dep.summary}")
                        if dep.source_code_snippet:
                            code_snippet = dep.source_code_snippet[:500]
                            if len(dep.source_code_snippet) > 500:
                                code_snippet += "..."
                            context_parts.append(f"  Code:\n```\n{code_snippet}\n```")
                
                # Process reference contexts (usage examples)
                if searcher_output.reference_contexts:
                    context_parts.append("\n--- Usage Examples ---")
                    for ref in searcher_output.reference_contexts[:3]:  # Limit to 3
                        context_parts.append(f"\nUsed by: {ref.component_name}")
                        if ref.usage_summary:
                            context_parts.append(f"  {ref.usage_summary}")
                        for example in ref.usage_examples[:2]:  # Limit examples
                            context_parts.append(f"  Example: {example[:200]}")
                
                # Process external contexts
                if searcher_output.external_contexts:
                    context_parts.append("\n--- External Context ---")
                    for ext in searcher_output.external_contexts[:2]:  # Limit to 2
                        context_parts.append(f"\n{ext.knowledge_type}: {ext.summary}")
                        if ext.details:
                            context_parts.append(f"  {ext.details[:300]}")
            
            # Handle dictionary format (for backwards compatibility)
            elif isinstance(searcher_output, dict):
                internal = searcher_output.get('internal', {})
                calls = internal.get('calls', {})
                
                for category in ['class', 'function', 'method']:
                    deps = calls.get(category, {})
                    if deps:
                        context_parts.append(f"\n--- Called {category.upper()}s ---")
                        for name, code in list(deps.items())[:3]:
                            code_snippet = code[:500] + "..." if len(code) > 500 else code
                            context_parts.append(f"\n{name}:\n```\n{code_snippet}\n```")
                
                external = searcher_output.get('external', {})
                if external:
                    context_parts.append(f"\n--- External Context ---\n{external}")
        
        return "\n".join(context_parts)

    def _clean_thinking_tokens(self, text: str) -> str:
        """Remove thinking tokens and other LLM artifacts from the response.
        
        Args:
            text: Raw text that may contain <think>...</think> blocks
            
        Returns:
            str: Cleaned text with thinking tokens removed
        """
        # Remove <think>...</think> blocks (greedy, handles multiline)
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove any remaining XML-like artifacts that aren't docstring tags
        cleaned = re.sub(r'</?(?!DOCSTRING|docstring)[a-zA-Z_]+>', '', cleaned)
        
        return cleaned.strip()

    def _clean_docstring_artifacts(self, docstring: str) -> str:
        """Clean artifacts and formatting issues from extracted docstring.
        
        Args:
            docstring: Raw extracted docstring
            
        Returns:
            str: Cleaned docstring ready for insertion
        """
        # Remove any remaining thinking tokens
        cleaned = self._clean_thinking_tokens(docstring)
        
        # Remove triple quotes if LLM included them (insertion will add proper quotes)
        cleaned = re.sub(r'^[\s]*["\'][\s]*["\'][\s]*["\']\s*', '', cleaned)  # Start
        cleaned = re.sub(r'\s*["\'][\s]*["\'][\s]*["\'][\s]*$', '', cleaned)  # End
        
        # Normalize whitespace
        lines = cleaned.split('\n')
        # Remove completely empty lines at start and end
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        
        return '\n'.join(lines)

    def process(self, context: AgentContext) -> AgentResult:
        """Generate a docstring for the given code component.
        
        Meta-inspired architecture: Returns just the docstring string for direct insertion.
        Uses memory-based LLM interaction for cleaner conversation flow.
        
        Args:
            context: AgentContext containing the component and prior agent results
            
        Returns:
            AgentResult with output=docstring (string) for direct source code insertion
        """
        try:
            component = context.component
            searcher_output = context.get_result('searcher')
            
            self.logger.info(f"Generating docstring for: {component.name}")
            
            # Build context string from component and searcher output
            context_string = self._build_context_string(component, searcher_output)
            
            # Get appropriate prompt for component type
            custom_prompt = self.get_custom_prompt(component)
            
            # Build task description (user message)
            task_description = f"""{custom_prompt}

Available context from codebase analysis:
{context_string}

<FOCAL_CODE_COMPONENT>
{component.source_code}
</FOCAL_CODE_COMPONENT>

Write a complete, accurate docstring for this {component.type.value} named "{component.name}".

IMPORTANT FORMATTING RULES:
1. Start your response with exactly: <DOCSTRING>
2. Write the complete docstring content (NO triple quotes - they will be added during insertion)
3. End with exactly: </DOCSTRING>
4. Do NOT include any text outside these tags
5. Do NOT include ```python or ``` markers
6. Use Google docstring format

Example of correct format:
<DOCSTRING>
Brief one-line summary of what this does.

Longer description explaining the purpose, behavior, and any important details.

Args:
    param1: Description of first parameter.
    param2: Description of second parameter.

Returns:
    Description of return value.
</DOCSTRING>
"""
            
            # Memory-based LLM interaction (Meta-inspired)
            self.clear_memory()
            self.add_to_memory("system", self.base_prompt)
            self.add_to_memory("user", task_description)
            
            # Generate response using memory
            response = self.generate_response(
                temperature=0.3,
                max_tokens=2000
            )
            
            # Clean thinking tokens from raw response
            cleaned_response = self._clean_thinking_tokens(response)
            
            # Log for debugging
            self.logger.debug(f"Cleaned LLM Response for {component.name}: {cleaned_response[:500]}")
            
            # Extract docstring from response
            docstring = self.extract_docstring(cleaned_response)
            
            # If extraction failed, log warning and return failure
            if not docstring:
                self.logger.warning(
                    f"Failed to extract docstring for {component.name}. "
                    f"LLM response was not properly formatted with XML tags."
                )
                return AgentResult(
                    agent_name=self.agent_name,
                    status=AgentStatus.FAILED,
                    output=None,
                    error="Could not extract docstring - XML tags not found in LLM response"
                )
            
            # Clean the extracted docstring
            docstring = self._clean_docstring_artifacts(docstring)
            
            # Validate the docstring has meaningful content
            word_count = len(docstring.split())
            if word_count < 5:
                self.logger.warning(f"Docstring too short ({word_count} words): '{docstring}'")
                return AgentResult(
                    agent_name=self.agent_name,
                    status=AgentStatus.FAILED,
                    output=None,
                    error=f"Generated docstring too short ({word_count} words)"
                )
            
            self.logger.info(
                f"Docstring generated for {component.name}: {len(docstring)} chars, {word_count} words"
            )
            
            # Return just the docstring string (Meta architecture)
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.SUCCESS,
                output=docstring  # Just the string, ready for insertion!
            )
            
        except Exception as e:
            self.logger.error(f"Writer agent error: {e}", exc_info=True)
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILED,
                output=None,
                error=str(e)
            )
