"""
Writer Agent
Generates comprehensive documentation using all gathered context
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from backend.agents.base_agent import BaseAgent, AgentContext, AgentResult, AgentStatus
from backend.agents.reader_agent import ReaderOutput
from backend.agents.searcher_agent import SearcherOutput
from backend.models.code_component import CodeComponent, ComponentType
from backend.models.documentation import Documentation, Example
from backend.agents.writer.templates.function import FunctionTemplate
from backend.agents.writer.templates.class_template import ClassTemplate
from backend.agents.writer.templates.module import ModuleTemplate
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class WriterAgent(BaseAgent):
    """
    Writer Agent generates documentation by:
    1. Combining analysis from Reader
    2. Integrating context from Searcher
    3. Using templates for structure
    4. Generating natural language with LLM
    """
    
    def __init__(self):
        super().__init__("writer")
        
        # Load configuration
        self.docstring_style = self.agent_config.get('docstring_style', 'google')
        self.include_examples = self.agent_config.get('include_examples', True)
        self.include_type_hints = self.agent_config.get('include_type_hints', True)
        self.min_description_length = self.agent_config.get('min_description_length', 50)
        
        # Templates
        self.function_template = FunctionTemplate()
        self.class_template = ClassTemplate()
        self.module_template = ModuleTemplate()
    
    def process(self, context: AgentContext) -> AgentResult:
        """
        Generate documentation for component
        
        Args:
            context: Agent context with Reader and Searcher outputs
            
        Returns:
            AgentResult with Documentation
        """
        try:
            component = context.component
            reader_output = context.get_result('reader')
            searcher_output = context.get_result('searcher')
            
            if not reader_output:
                return AgentResult(
                    agent_name=self.agent_name,
                    status=AgentStatus.FAILED,
                    output=None,
                    error="No Reader output available"
                )
            
            self.logger.info(f"Generating documentation for: {component.name}")
            
            # Generate documentation based on component type
            if component.type == ComponentType.FUNCTION or component.type == ComponentType.METHOD:
                doc = self._generate_function_documentation(
                    component, reader_output, searcher_output
                )
            elif component.type == ComponentType.CLASS:
                doc = self._generate_class_documentation(
                    component, reader_output, searcher_output
                )
            elif component.type == ComponentType.MODULE:
                doc = self._generate_module_documentation(
                    component, reader_output, searcher_output
                )
            else:
                doc = self._generate_generic_documentation(
                    component, reader_output, searcher_output
                )
            
            if not doc:
                return AgentResult(
                    agent_name=self.agent_name,
                    status=AgentStatus.FAILED,
                    output=None,
                    error="Failed to generate documentation"
                )
            
            # Format docstring
            doc.docstring = doc.format_docstring(self.docstring_style)
            
            self.logger.info(
                f"Documentation generated: {len(doc.docstring)} chars, "
                f"{len(doc.examples)} examples"
            )
            
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.SUCCESS,
                output=doc
            )
            
        except Exception as e:
            self.logger.error(f"Writer agent error: {e}", exc_info=True)
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILED,
                output=None,
                error=str(e)
            )
    
    def _generate_function_documentation(
        self,
        component: CodeComponent,
        reader_output: ReaderOutput,
        searcher_output: Optional[SearcherOutput]
    ) -> Documentation:
        """Generate documentation for a function"""
        
        # Build context for LLM
        context = self._build_context(component, reader_output, searcher_output)
        
        # Generate main description
        description = self._generate_description(component, context)
        
        # Generate summary (first line)
        summary = self._generate_summary(description)
        
        # Document parameters
        parameters_doc = self._document_parameters(component, context)
        
        # Document return value
        returns_doc = self._document_return_value(component, context)
        
        # Document exceptions
        raises_doc = self._document_exceptions(component, context)
        
        # Generate examples
        examples = []
        if self.include_examples:
            examples = self._generate_examples(component, context)
        
        # Extract notes and warnings
        notes, warnings = self._extract_notes_warnings(component, context)
        
        doc = Documentation(
            component_id=component.id,
            component_name=component.name,
            component_type=component.type.value,
            summary=summary,
            description=description,
            parameters_doc=parameters_doc,
            returns_doc=returns_doc,
            raises_doc=raises_doc,
            examples=examples,
            notes=notes,
            warnings=warnings,
            style=self.docstring_style
        )
        
        return doc
    
    def _generate_description(
        self,
        component: CodeComponent,
        context: Dict[str, Any]
    ) -> str:
        """Generate detailed description using LLM"""
        
        prompt = self._create_description_prompt(component, context)
        
        system_prompt = """You are an expert technical writer creating clear, comprehensive code documentation.

Guidelines:
- Write in present tense
- Be specific and technical
- Explain the "what" and "why", not just "how"
- Use clear, professional language
- Include relevant context from dependencies and usage
- Keep descriptions concise but complete"""
        
        description = self.generate_with_llm(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.6,
            max_tokens=1000
        )
        
        return description.strip()
    
    def _create_description_prompt(
        self,
        component: CodeComponent,
        context: Dict[str, Any]
    ) -> str:
        """Create prompt for generating description"""
        
        prompt = f"""Generate a detailed description for this {component.type.value}:

Name: {component.name}
Signature: {component.signature}

Code:
```{component.language}
{component.source_code}
```

"""
        
        # Add complexity analysis
        if context.get('complexity'):
            prompt += f"\nComplexity: {context['complexity']['complexity_level']}\n"
        
        # Add dependency context
        if context.get('dependencies'):
            prompt += "\nDependencies:\n"
            for dep in context['dependencies'][:3]:
                prompt += f"- {dep['name']}: {dep['summary']}\n"
        
        # Add usage context
        if context.get('usage'):
            prompt += f"\nUsage Context:\n{context['usage']}\n"
        
        # Add external context
        if context.get('external'):
            prompt += "\nRelevant Concepts:\n"
            for ext in context['external'][:2]:
                prompt += f"- {ext['query']}: {ext['summary']}\n"
        
        prompt += """
Generate a comprehensive description (3-5 sentences) that:
1. Explains what this component does
2. Describes its purpose and use cases
3. Mentions key dependencies or concepts if relevant
4. Highlights any important behavior or edge cases"""
        
        return prompt
    
    def _generate_summary(self, description: str) -> str:
        """Generate one-line summary from description"""
        # Extract first sentence
        sentences = description.split('.')
        if sentences:
            summary = sentences[0].strip() + '.'
            return summary
        return description[:100]
    
    def _document_parameters(
        self,
        component: CodeComponent,
        context: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Document function parameters"""
        if not component.parameters:
            return []
        
        prompt = f"""Document the parameters for this function:

Function: {component.name}
Signature: {component.signature}

Code context:
```{component.language}
{component.source_code[:500]}
```

Parameters to document:
{chr(10).join(f"- {p.name} ({p.type_hint or 'unknown type'})" for p in component.parameters)}

For each parameter, provide:
1. A clear description of what it represents
2. Expected format/values if applicable
3. Default behavior if it has a default value

Format as:
param_name: description here"""
        
        try:
            response = self.generate_with_llm(
                prompt=prompt,
                temperature=0.5,
                max_tokens=800
            )
            
            # Parse response
            params_doc = []
            lines = response.strip().split('\n')
            
            for line in lines:
                if ':' in line:
                    param_name, desc = line.split(':', 1)
                    param_name = param_name.strip()
                    desc = desc.strip()
                    
                    # Find matching parameter
                    for p in component.parameters:
                        if p.name == param_name:
                            params_doc.append({
                                'name': param_name,
                                'type': p.type_hint or '',
                                'description': desc
                            })
                            break
            
            return params_doc
            
        except Exception as e:
            self.logger.warning(f"Failed to document parameters: {e}")
            # Fallback: basic documentation
            return [
                {
                    'name': p.name,
                    'type': p.type_hint or '',
                    'description': f"The {p.name} parameter"
                }
                for p in component.parameters
            ]
    
    def _document_return_value(
        self,
        component: CodeComponent,
        context: Dict[str, Any]
    ) -> Optional[Dict[str, str]]:
        """Document return value"""
        if not component.return_type or component.return_type == 'None':
            return None
        
        prompt = f"""Describe what this function returns:

Function: {component.name}
Return type: {component.return_type}

Code:
```{component.language}
{component.source_code}
```

Provide a clear description of:
1. What is returned
2. The format/structure of the return value
3. When it might return different values (if applicable)

Description:"""
        
        try:
            description = self.generate_with_llm(
                prompt=prompt,
                temperature=0.5,
                max_tokens=300
            )
            
            return {
                'type': component.return_type,
                'description': description.strip()
            }
            
        except Exception as e:
            self.logger.warning(f"Failed to document return value: {e}")
            return {
                'type': component.return_type,
                'description': f"Returns {component.return_type}"
            }
    
    def _document_exceptions(
        self,
        component: CodeComponent,
        context: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Document potential exceptions"""
        # Look for raise statements in code
        import re
        raise_pattern = r'raise\s+(\w+)'
        raises = re.findall(raise_pattern, component.source_code)
        
        if not raises:
            return []
        
        raises_doc = []
        for exception in set(raises):
            # Generate description for each exception
            prompt = f"""Explain when this exception is raised:

Function: {component.name}
Exception: {exception}

Code context:
```{component.language}
{component.source_code}
```

Brief description of when this exception occurs:"""
            
            try:
                description = self.generate_with_llm(
                    prompt=prompt,
                    temperature=0.4,
                    max_tokens=200
                )
                
                raises_doc.append({
                    'exception': exception,
                    'description': description.strip()
                })
            except Exception as e:
                self.logger.warning(f"Failed to document exception {exception}: {e}")
        
        return raises_doc
    
    def _generate_examples(
        self,
        component: CodeComponent,
        context: Dict[str, Any]
    ) -> List[Example]:
        """Generate usage examples"""
        # Use usage context from searcher if available
        usage_examples = context.get('usage_examples', [])
        
        prompt = f"""Generate 1-2 clear usage examples for this function:

Function: {component.name}
Signature: {component.signature}

"""
        
        if usage_examples:
            prompt += f"Real usage patterns found:\n"
            for ex in usage_examples[:2]:
                prompt += f"```\n{ex}\n```\n"
        
        prompt += f"""
Code:
```{component.language}
{component.source_code[:400]}
```

Generate practical examples showing:
1. Basic usage
2. Common use case (if different from basic)

Format as:
Example: <description>
```python
<code>
```
Output: <expected output if applicable>
"""
        
        try:
            response = self.generate_with_llm(
                prompt=prompt,
                temperature=0.6,
                max_tokens=600
            )
            
            # Parse examples
            examples = self._parse_examples(response)
            return examples
            
        except Exception as e:
            self.logger.warning(f"Failed to generate examples: {e}")
            return []
    
    def _parse_examples(self, response: str) -> List[Example]:
        """Parse examples from LLM response"""
        examples = []
        
        # Simple parsing - look for code blocks
        import re
        
        # Find all descriptions and code blocks
        pattern = r'Example:\s*(.+?)\n```(?:python|javascript|java)?\n(.+?)\n```(?:\nOutput:\s*(.+?))?(?=\n\n|$)'
        matches = re.findall(pattern, response, re.DOTALL)
        
        for match in matches:
            description, code, output = match
            examples.append(Example(
                description=description.strip(),
                code=code.strip(),
                output=output.strip() if output else None
            ))
        
        return examples[:2]  # Limit to 2 examples
    
    def _extract_notes_warnings(
        self,
        component: CodeComponent,
        context: Dict[str, Any]
    ) -> tuple:
        """Extract important notes and warnings"""
        notes = []
        warnings = []
        
        # Check for common warning indicators
        if component.is_async:
            notes.append("This is an asynchronous function.")
        
        if component.is_generator:
            notes.append("This is a generator function.")
        
        if component.decorators:
            notes.append(f"Decorators applied: {', '.join(component.decorators)}")
        
        # Check for deprecated
        if component.metadata.get('deprecated'):
            warnings.append("This function is deprecated.")
        
        # Check complexity
        if context.get('complexity', {}).get('complexity_level')== 'complex':
            notes.append("This is a complex function with multiple responsibilities.")

        return notes, warnings

    def _generate_class_documentation(
        self,
        component: CodeComponent,
        reader_output: ReaderOutput,
        searcher_output: Optional[SearcherOutput]
    ) -> Documentation:
        """Generate documentation for a class"""
        # Similar structure to function but adapted for classes
        context = self._build_context(component, reader_output, searcher_output)
        
        description = self._generate_description(component, context)
        summary = self._generate_summary(description)
        
        # Document attributes
        attributes_doc = [
            {
                'name': attr.get('name', 'unknown'),
                'type': attr.get('type', ''),
                'description': attr.get('description', '')
            }
            for attr in component.attributes
        ]
        
        doc = Documentation(
            component_id=component.id,
            component_name=component.name,
            component_type=component.type.value,
            summary=summary,
            description=description,
            attributes_doc=attributes_doc,
            methods_doc=component.methods,
            style=self.docstring_style
        )
        
        return doc

    def _generate_module_documentation(
        self,
        component: CodeComponent,
        reader_output: ReaderOutput,
        searcher_output: Optional[SearcherOutput]
    ) -> Documentation:
        """Generate documentation for a module"""
        context = self._build_context(component, reader_output, searcher_output)
        
        description = self._generate_description(component, context)
        summary = self._generate_summary(description)
        
        doc = Documentation(
            component_id=component.id,
            component_name=component.name,
            component_type=component.type.value,
            summary=summary,
            description=description,
            style=self.docstring_style
        )
        
        return doc

    def _generate_generic_documentation(
        self,
        component: CodeComponent,
        reader_output: ReaderOutput,
        searcher_output: Optional[SearcherOutput]
    ) -> Documentation:
        """Generate generic documentation"""
        return self._generate_function_documentation(
            component, reader_output, searcher_output
        )

    def _build_context(
        self,
        component: CodeComponent,
        reader_output: ReaderOutput,
        searcher_output: Optional[SearcherOutput]
    ) -> Dict[str, Any]:
        """Build comprehensive context dictionary"""
        context = {
            'component': component,
            'complexity': reader_output.complexity_assessment,
        }
        
        if searcher_output:
            # Add dependency context
            if searcher_output.dependency_contexts:
                context['dependencies'] = [
                    {
                        'name': dep.component_name,
                        'summary': dep.summary,
                        'signature': dep.signature
                    }
                    for dep in searcher_output.dependency_contexts
                ]
            
            # Add usage context
            if searcher_output.reference_contexts:
                usage_parts = []
                for ref in searcher_output.reference_contexts:
                    if ref.usage_summary:
                        usage_parts.append(ref.usage_summary)
                context['usage'] = '\n'.join(usage_parts)
                context['usage_examples'] = []
                for ref in searcher_output.reference_contexts:
                    context['usage_examples'].extend(ref.usage_examples)
            
            # Add external context
            if searcher_output.external_contexts:
                context['external'] = [
                    {
                        'query': ext.query,
                        'summary': ext.summary,
                        'details': ext.details
                    }
                    for ext in searcher_output.external_contexts
                ]
        
        return context
    