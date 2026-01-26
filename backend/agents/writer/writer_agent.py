"""
Optimized Writer Agent - Single LLM Call Architecture
Generates grounded, code-specific documentation with ONE comprehensive LLM call
"""
from typing import Dict, Any, List, Optional
import re
import ast
import json

from backend.agents.base_agent import BaseAgent, AgentContext, AgentResult, AgentStatus
from backend.agents.reader_agent import ReaderOutput
from backend.agents.searcher_agent import SearcherOutput
from backend.models.code_component import CodeComponent, ComponentType
from backend.models.documentation import Documentation, Example
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class WriterAgent(BaseAgent):
    """
    Optimized Writer Agent that generates documentation with a single LLM call.
    
    Architecture:
    1. Extract ALL code facts upfront (no LLM)
    2. Build ONE comprehensive grounded prompt
    3. Single LLM call returns complete documentation
    4. Parse structured response
    
    Performance: 75% reduction in LLM calls, time, and cost
    """

    def __init__(self):
        super().__init__("writer")
        
        # Load configuration
        self.docstring_style = self.agent_config.get('docstring_style', 'google')
        self.include_examples = self.agent_config.get('include_examples', True)
        self.include_type_hints = self.agent_config.get('include_type_hints', True)

    def process(self, context: AgentContext) -> AgentResult:
        """Generate documentation for component"""
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
            
            # Build context
            ctx = self._build_context(component, reader_output, searcher_output)
            
            # Extract code facts (complexity-aware)
            complexity_level = reader_output.complexity_assessment.get('complexity_level', 'simple')
            if complexity_level in ['complex', 'moderate']:
                code_facts = self._extract_all_code_facts(component, ctx)
                # self._classify_component_roles(component, ctx, code_facts)
                # self._generate_invariants(code_facts, component.source_code)
            else:
                code_facts = self._extract_minimal_facts(component)
            
            # ONE comprehensive LLM call
            doc_data = self._generate_documentation_single_call(component, ctx, code_facts)
            
            # Build Documentation object
            doc = Documentation(
                component_id=component.id,
                component_name=component.name,
                component_type=component.type.value,
                summary=doc_data['summary'],
                description=doc_data['description'],
                parameters_doc=doc_data.get('parameters', []),
                returns_doc=doc_data.get('returns'),
                raises_doc=doc_data.get('raises', []),
                examples=doc_data.get('examples', []),
                notes=doc_data.get('notes', []),
                warnings=doc_data.get('warnings', []),
                style=self.docstring_style,
                attributes_doc=doc_data.get('attributes', []), # NEW: Pass to model
            )
            
            # FIX 1: COMPUTE ACTUAL SCORES
            doc.completeness_score = self._compute_completeness_score(doc_data, component)
            doc.clarity_score = self._compute_clarity_score(doc_data, component, code_facts)
            
            doc.docstring = doc.format_docstring(self.docstring_style)
            
            self.logger.info(
                f"Documentation generated: {len(doc.docstring)} chars, "
                f"{len(doc.examples)} examples, 1 LLM call"
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

    # ============================================================================
    # FIX 1: EXTRACTION - Add missing data to code_facts
    # ============================================================================

    def _extract_minimal_facts(self, component: CodeComponent) -> Dict[str, Any]:
        """Extract minimal facts for simple components"""
        control_flow = component.metadata.get('control_flow', {})
        exceptions = component.metadata.get('exceptions', [])
        source = component.source_code
        
        # For classes, use attributes directly from Navigator (no fallback)
        class_attributes = component.attributes if component.type == ComponentType.CLASS else []
        
        # Extract basic parameter usage even for simple components
        parameter_usage = {}
        if component.parameters:
            for param in component.parameters:
                param_name = param.name
                count = source.count(param_name)
                parameter_usage[param_name] = {
                    'usage_type': 'used' if count > 0 else 'unused',
                    'usage_description': f"Used {count} times in function",
                    'type': param.type_hint or 'unknown',
                    'default': param.default_value
                }
    
        return {
            'decorators': component.decorators or [],
            'is_async': component.is_async or control_flow.get('is_async', False),
            'is_generator': component.is_generator,
            'return_type': component.return_type,
            'raises': exceptions,
            'parameters': [
                {'name': p.name, 'type': p.type_hint or 'unknown', 'default': p.default_value}
                for p in (component.parameters or [])
            ],
            'parameter_usage': parameter_usage,
            'modifies_global_state': component.metadata.get('shared_state_dependencies', []),
            'reads_global_state': [],
            'has_loop': control_flow.get('has_loop', False),
            'operations': [],
            'data_structures_used': [],
            'control_flow': ['async'] if component.is_async else [],
            'actual_returns': [],
            'state_mutations': {},
            'invariants': [],
            'roles': [],
            'attributes': class_attributes,  # NEW: Add attributes
        }

    def _extract_all_code_facts(self, component: CodeComponent, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract comprehensive code facts for complex components"""
        source = component.source_code
        clean_source = self._strip_noise(source, component.language)
        
        # Extract parameters WITH usage analysis (matching _extract_minimal_facts)
        parameters = []
        parameter_usage = {}
        for p in (component.parameters or []):
            param_name = p.name
            count = source.count(param_name)
            
            parameters.append({
                'name': p.name,
                'type': p.type_hint or 'any',
                'required': p.is_required,
                'default': p.default_value
            })
            
            # FIX #6: Include usage context
            parameter_usage[param_name] = {
                'usage_type': 'used' if count > 0 else 'unused',
                'usage_description': f"Used {count} times in function",
                'type': p.type_hint or 'unknown',
                'default': p.default_value
            }

        return {
            'decorators': component.decorators or [],
            'is_async': component.is_async,
            'is_generator': component.is_generator,
            'raises': component.metadata.get('exceptions', []),
            'modifies_global_state': component.metadata.get('shared_state_dependencies', []),
            'reads_global_state': [],
            'parameter_usage': parameter_usage,  # FIX #6: Added parameter usage
            'operations': [],
            'data_structures_used': [],
            'control_flow': [],
            'return_type': component.return_type or 'any',
            'actual_returns': self._extract_actual_returns(clean_source, component.language),
            'parameters': parameters,
            'attributes': component.attributes or [],
            'roles': [],
            'invariants': []
        }

    def _strip_noise(self, source: str, language: str) -> str:
        """Remove comments and strings to allow accurate regex matching across languages"""
        # Remove multiline comments
        source = re.sub(r'/\*.*?\*/', '', source, flags=re.DOTALL) # C-style
        source = re.sub(r'"""(.*?)"""', '', source, flags=re.DOTALL) # Python
        # Remove single line comments
        source = re.sub(r'//.*', '', source) # C-style
        source = re.sub(r'#.*', '', source)  # Python
        # Remove string literals
        source = re.sub(r"'(.*?)'|\"(.*?)\"", '', source)
        return source

    def _extract_actual_returns(self, clean_source: str, language: str) -> List[str]:
        """Extract return expressions (Fixes 'return type inconsistencies')"""
        # Look for return keyword and capture until end of expression
        # Works for: return x; (C/JS/Java) and return x (Python)
        pattern = r'\breturn\s+([^;}\n#]+)'
        matches = re.findall(pattern, clean_source)
        return [m.strip() for m in matches if m.strip()][:3]

    def _validate_documentation(self, doc_data: Dict[str, Any], component: CodeComponent) -> Dict[str, Any]:
        """
        Validate and fix documentation based on component type.
        This prevents inappropriate fields (e.g., returns_doc on globals).
        """
        
        # GLOBAL VARIABLES should NOT have returns or parameters
        if component.type == ComponentType.GLOBAL_VARIABLE:
            doc_data['returns'] = None
            doc_data['parameters'] = []
        
        # CLASSES should NOT have returns
        if component.type == ComponentType.CLASS:
            doc_data['returns'] = None
        
        # PROPERTIES should NOT have parameters
        modifiers = component.metadata.get('modifiers', {})
        if modifiers.get('is_property'):
            doc_data['parameters'] = []
        
        # STATIC/CLASS METHODS: parameters doc OK, but no self/cls
        actual_params = {p.name for p in (component.parameters or [])}
        if modifiers.get('is_static') or modifiers.get('is_class_method'):
            if 'self' in actual_params:
                actual_params.discard('self')
            if 'cls' in actual_params:
                actual_params.discard('cls')
            doc_data['parameters'] = [
                p for p in doc_data.get('parameters', [])
                if p.get('name') in actual_params
            ]
        
        return doc_data

    def _generate_documentation_single_call(
        self,
        component: CodeComponent,
        context: Dict[str, Any],
        code_facts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """ONE comprehensive LLM call with validation"""
        prompt = self._build_comprehensive_prompt(component, context, code_facts)
        system_prompt = self._get_system_prompt()
        
        try:
            response = self.generate_with_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=3500
            )
            
            doc_data = self._parse_response(response, component, code_facts)
            
            # ✓ VALIDATE documentation AFTER LLM
            doc_data = self._validate_documentation(doc_data, component)
            
            # Auto-generate notes/warnings from IR metadata
            doc_data['notes'] = self._extract_notes_from_metadata(component, code_facts)
            doc_data['warnings'] = self._extract_warnings_from_metadata(code_facts)
            
            return doc_data
            
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            return self._create_fallback_doc(component, code_facts)

    def _build_comprehensive_prompt(
        self,
        component: CodeComponent,
        context: Dict[str, Any],
        code_facts: Dict[str, Any]
    ) -> str:
        """Build comprehensive prompt - FIXED for role-specific efficiency and missing keys"""
        complexity = context.get('complexity_level', 'simple')
        
        # ========== SPECIAL CASE: GLOBAL VARIABLES (Constants vs State) ==========
        if component.type == ComponentType.GLOBAL_VARIABLE:
            # Check if it's a constant (no mutations found by Navigator)
            is_constant = not code_facts.get('modifies_global_state')
            role_type = "Configuration Constant" if is_constant else "Mutable State"
            
            # Build usage context from existing code_facts
            usage_lines = []
            shared_deps = code_facts.get('modifies_global_state', [])
            if shared_deps:
                deps_str = ', '.join(shared_deps[:3])
                usage_lines.append(f"Modified by: {deps_str}")
            else:
                usage_lines.append("Read-only constant")
            
            usage_context = "\n".join(usage_lines) if usage_lines else "Module-level variable"
            
            return f"""Generate documentation for this {role_type}. 
            
Name: {component.name}
Value/Code: {component.source_code.strip()}

CONTEXT:
{usage_context}

RULES:
1. SUMMARY: Active verb only (e.g., "Defines...", "Tracks...").
2. DESCRIPTION: If constant, explain the IMPACT of changing this value. DO NOT describe the syntax.
3. NO 'parameters' or 'returns' fields.

Output JSON:
{{
  "summary": "High-level purpose (max 100 chars)",
  "description": "Functional impact or synchronization role (2 sentences)",
  "notes": ["Note on initialization/dependency"],
  "warnings": []
}}
"""
        # ========== SPECIAL CASE: CLASSES (Handling empty/data classes) ==========
        if component.type == ComponentType.CLASS:
            is_data_class = not component.methods or len(component.methods) <= 1
            
            # Build attributes section
            attributes_section = ""
            if code_facts.get('attributes'):
                attributes_section = "\n=== CLASS ATTRIBUTES ===\n"
                for attr in code_facts['attributes']:
                    attr_type = attr.get('type', 'any')
                    attr_name = attr.get('name', '')
                    attributes_section += f"- {attr_name}: {attr_type}\n"
            else:
                attributes_section = "\n=== CLASS ATTRIBUTES ===\nNo attributes defined (see source code)\n"
            
            return f"""Generate documentation for this {component.name} ({'Data Model' if is_data_class else 'Service Class'}):

Code:
```{component.language}
{component.source_code}
```

=== DATA FIELDS ===
{', '.join([a.get('name') for a in component.attributes]) or 'Attributes are defined in constructor'}

CRITICAL: 
- If this is a simple data holder, focus the DESCRIPTION on what entities this model represents.
- If it has logic, focus on the primary responsibility.
- Do NOT leave fields empty if no docstring exists; derive from code structure.

{attributes_section}
"""

        # ========== BASE PROMPT CONSTRUCTION ==========
        async_prefix = "[ASYNC] " if code_facts.get('is_async') else ""
        
        # OPTIMIZATION: For simple functions, use minimal prompt
        is_simple = (
            component.lines_of_code <= 15 and
            len(component.parameters or []) <= 3 and
            not code_facts.get('raises') and
            not code_facts.get('modifies_global_state')
        )
        
        # Truncate source code for large functions to reduce prefill time
        source_code = component.source_code
        if len(source_code) > 2000 and not is_simple:
            source_code = source_code[:1500] + "\n# ... (truncated) ...\n" + source_code[-400:]
        
        prompt = f"""Document this {component.type.value}: {component.name}
{async_prefix}
Signature: {component.signature or 'N/A'}

```{component.language}
{source_code}
```
"""

        # ========== SIMPLE FUNCTION: MINIMAL PROMPT ==========
        if is_simple and component.type in [ComponentType.FUNCTION, ComponentType.METHOD]:
            # Compact JSON schema for simple functions
            prompt += f"""
Return: {code_facts.get('return_type', 'any')}
Output JSON: {{"summary": "verb phrase", "description": "how it works", "parameters": [...], "returns": {{"type": "{code_facts.get('return_type', 'any')}", "description": "..."}}}}
"""
            return prompt

        # ========== CLASS SPECIFIC LOGIC ==========
        if component.type == ComponentType.CLASS:
            is_data_class = not component.methods or len(component.methods) <= 1
            prompt += f"\nCategory: {'Data Model' if is_data_class else 'Service/Logic Class'}\n"
            
            # Build attributes section - only if attributes exist
            if code_facts.get('attributes'):
                prompt += "Attributes: "
                prompt += ", ".join([f"{a.get('name')}:{a.get('type', 'any')}" for a in code_facts['attributes'][:5]])
                prompt += "\n"

        # ========== CODE FACTS (ONLY NON-EMPTY) ==========
        facts = []
        if code_facts.get('modifies_global_state'):
            facts.append(f"Modifies: {', '.join(code_facts['modifies_global_state'][:3])}")
        if code_facts.get('operations'):
            facts.append(f"Ops: {', '.join(code_facts['operations'][:3])}")
        if code_facts.get('control_flow') and code_facts['control_flow'] != ['linear']:
            facts.append(f"Flow: {', '.join(code_facts['control_flow'])}")
        
        if facts:
            prompt += "\nFacts: " + " | ".join(facts) + "\n"

        # Add parameter types (compact format)
        if code_facts.get('parameters'):
            param_types = [f"{p['name']}:{p['type']}" for p in code_facts['parameters'][:6]]
            prompt += f"\nParams: {', '.join(param_types)}\n"

        # Add exceptions (only if present)
        if code_facts.get('raises'):
            exc_list = [f"{e['exception']}" for e in code_facts['raises'][:3]]
            prompt += f"Raises: {', '.join(exc_list)}\n"

        # Compact JSON output format
        prompt += f"""
Return type: {code_facts.get('return_type', 'any')}

Output JSON:
{{"summary": "active verb phrase (max 100 chars)", "description": "implementation details", "parameters": [{{"name": "...", "type": "...", "description": "..."}}], "returns": {{"type": "{code_facts.get('return_type', 'any')}", "description": "..."}}, "raises": [], "notes": []}}
"""
        return prompt

    def _get_system_prompt(self) -> str:
        """Concise system prompt for faster processing"""
        return """Technical documentation expert. Output valid JSON only.
Rules: Start summary with active verb. No "This function/class". Summary=What, Description=How."""

    def _parse_response(
        self,
        response: str,
        component: CodeComponent,
        code_facts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse JSON response and FORCE-INJECT truth from Navigator.
        This fixes parameter and return type inconsistencies caused by LLM hallucinations.
        """
        try:
            # 1. Clean and parse JSON
            cleaned = self._clean_json(response)
            data = json.loads(cleaned)
            
            # 2. Extract structured data with safety defaults
            parsed = {
                'summary': data.get('summary', '').strip()[:100],
                'description': data.get('description', '').strip(),
                'attributes': data.get('attributes', []),  # NEW: Extract attributes
                'parameters': data.get('parameters', []),
                'returns': data.get('returns') or {'type': 'any', 'description': ''},
                'raises': data.get('raises', []),
                'examples': self._parse_examples(data.get('examples', [])),
                'notes': data.get('notes', []),
                'warnings': data.get('warnings', [])
            }

            # ========================================================================
            # FIX: FORCE-OVERWRITE LLM Hallucinations with Navigator Truth
            # ========================================================================
            
            # A) Force correct Return Type from Navigator
            nav_return_type = component.return_type or 'any'
            if parsed['returns']:
                # The LLM is only allowed to change the description, NOT the type
                parsed['returns']['type'] = nav_return_type

            # B) Force correct Parameter Types and Names
            nav_params = {p.name: p.type_hint for p in (component.parameters or [])}
            if nav_params:  # Always validate if we have navigator params, regardless of LLM output
                valid_params = []
                for p_doc in parsed['parameters']:
                    name = p_doc.get('name')
                    if name in nav_params:
                        # Overwrite the hallucinated type with the Navigator's discovered type
                        p_doc['type'] = nav_params[name] or 'any'
                        valid_params.append(p_doc)
                
                # If the LLM missed a parameter, add it back as a placeholder to ensure completeness
                doc_param_names = {p.get('name') for p in valid_params}
                for p_name, p_type in nav_params.items():
                    if p_name not in doc_param_names:
                        valid_params.append({
                            'name': p_name,
                            'type': p_type or 'any',
                            'description': 'Parameter description missing from LLM response.'
                        })
                parsed['parameters'] = valid_params

                # AFTER setting parsed['parameters'] = valid_params, add:
                if len(valid_params) != len(nav_params):
                    self.logger.warning(
                        f"Parameter count mismatch for {component.name}: "
                        f"LLM returned {len(valid_params)}, Navigator found {len(nav_params)}"
                    )

            # C) Filter verified exceptions
            parsed['raises'] = self._validate_raises_against_code_facts(
                parsed['raises'],
                code_facts,
                component
            )
            
            return parsed
        
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parse error: {e}")
            return self._create_fallback_doc(component, code_facts)

    def _clean_json(self, response: str) -> str:
        """Extract JSON from response and remove markdown markers"""
        response = re.sub(r'```json\s*', '', response)
        response = re.sub(r'```\s*', '', response)
        
        start = response.find('{')
        end = response.rfind('}')
        
        return response[start:end+1] if start != -1 and end != -1 else response

    def _parse_examples(self, examples_data: List[Dict]) -> List[Example]:
        """Convert raw example dicts from LLM to Example objects"""
        return [
            Example(
                description=ex.get('description', ''),
                code=ex.get('code', ''),
                output=ex.get('output')
            )
            for ex in examples_data if isinstance(ex, dict)
        ]

    def _extract_notes_from_metadata(self, component: CodeComponent, code_facts: Dict[str, Any]) -> List[str]:
        """Generate notes from navigator's extracted metadata"""
        notes = []
        
        if code_facts.get('is_async'):
            notes.append("This is an asynchronous function - must be awaited")
        
        if code_facts.get('is_generator'):
            notes.append("This is a generator function - returns an iterator")
        
        if code_facts.get('decorators'):
            notes.append(f"Decorators: {', '.join(code_facts['decorators'])}")
        
        if code_facts.get('modifies_global_state'):
            notes.append(f"Modifies global state: {', '.join(code_facts['modifies_global_state'][:3])}")
        
        if code_facts.get('has_loop'):
            loop_type = code_facts.get('loop_type', 'infinite')
            notes.append(f"Contains {loop_type} loop")
        
        return notes

    def _extract_warnings_from_metadata(self, code_facts: Dict[str, Any]) -> List[str]:
        """Generate warnings from navigator's extracted metadata"""
        warnings = []
        
        if code_facts.get('has_try_except'):
            warnings.append("Has error handling - check for exceptions that may be raised")
        
        if code_facts.get('modifies_global_state'):
            warnings.append("Modifies shared state - consider thread safety")
        
        if code_facts.get('has_loop') and 'while True' in code_facts.get('source', ''):
            warnings.append("Contains infinite loop - runs continuously")
        
        return warnings

    def _create_fallback_doc(self, component: CodeComponent, code_facts: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback documentation when LLM fails"""
        return {
            'summary': f"{component.name} - {component.type.value}",
            'description': f"Component {component.name} performs: {', '.join(code_facts['operations'][:3]) or 'processing'}",
            'parameters': [
                {
                    'name': p.name,
                    'type': p.type_hint or '',
                    'description': code_facts['parameter_usage'].get(p.name, {}).get('usage_description', 'Parameter'),
                    'default': str(p.default_value) if p.default_value else None
                }
                for p in (component.parameters or [])
            ],
            'returns': {
                'type': component.return_type or 'unknown',
                'description': f"Returns: {code_facts['actual_returns'][0] if code_facts['actual_returns'] else 'value'}"
            } if component.return_type else None,
            'raises': [
                {'exception': exc['exception'], 'description': f"Raised when {exc['condition']}"}
                for exc in code_facts['raises']
            ],
            'examples': [],
            'notes': self._extract_notes_from_metadata(component, code_facts),
            'warnings': self._extract_warnings_from_metadata(code_facts)
        }

    def _build_context(
        self,
        component: CodeComponent,
        reader_output: ReaderOutput,
        searcher_output: Optional[SearcherOutput]
    ) -> Dict[str, Any]:
        """Build comprehensive context"""
        context = {
            'component': component,
            'complexity': reader_output.complexity_assessment,
            'needs_additional_context': reader_output.needs_additional_context,
            'complexity_level': reader_output.complexity_assessment.get('complexity_level', 'unknown'),
            'internal_requests': reader_output.internal_requests,
            'external_requests': reader_output.external_requests,
        }
        
        if searcher_output:
            if searcher_output.dependency_contexts:
                context['dependencies'] = [
                    {
                        'name': dep.component_name,
                        'summary': dep.summary,
                        'signature': dep.signature
                    }
                    for dep in searcher_output.dependency_contexts
                ]
            
            if searcher_output.reference_contexts:
                context['usage_examples'] = []
                for ref in searcher_output.reference_contexts:
                    if ref.usage_examples:
                        context['usage_examples'].extend(ref.usage_examples)
        
        context['domain'] = self._extract_domain_context(component, context)
        
        return context

    def _extract_domain_context(self, component: CodeComponent, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract domain-specific terms from function calls"""
        domain_info = {'domain_terms': set(), 'system_name': None}
        
        # Use actual function calls as domain terms (better than regex extraction)
        if component.calls:
            for call in component.calls[:8]:
                # Extract function name from full call path
                call_name = call.split('.')[-1] if '.' in call else call
                if len(call_name) > 2 and not call_name.startswith('_'):
                    domain_info['domain_terms'].add(call_name)
        
        # Keep top 8
        domain_info['domain_terms'] = set(sorted(list(domain_info['domain_terms']))[:8])
        
        return domain_info
    
    def _compute_completeness_score(self, doc_data: Dict[str, Any], component: CodeComponent) -> float:
        """
        Compute completeness score based on populated fields.
        
        Returns:
            float: 0.0-1.0 representing documentation completeness
        """
        # Define required fields by component type
        if component.type == ComponentType.GLOBAL_VARIABLE:
            required = ['summary', 'description']
        elif component.type == ComponentType.CLASS:
            # FIX: Changed 'attributes_doc' to 'attributes' to match doc_data keys
            required = ['summary', 'description', 'attributes']
        else:  # FUNCTION, METHOD
            required = ['summary', 'description', 'parameters', 'returns']
        
        # Count populated fields
        populated = sum(1 for field in required if doc_data.get(field))
        
        # Additional points for optional fields
        bonus = 0
        if doc_data.get('examples'):
            bonus += 0.1
        if doc_data.get('raises'):
            bonus += 0.05
        if doc_data.get('notes'):
            bonus += 0.05
        
        score = (populated / len(required)) + bonus
        return min(1.0, max(0.0, score))

    def _compute_clarity_score(self, doc_data: Dict[str, Any], component: CodeComponent, code_facts: Dict[str, Any]) -> float:
        """
        Improved clarity scoring that rewards:
        1. No boilerplate (summary ≠ description)
        2. Code-specific language (actual names)
        3. Behavioral description (not structural)
        4. Completeness with appropriate fields
        
        Returns: 0.0-1.0
        """
        
        summary = doc_data.get('summary', '')
        description = doc_data.get('description', '')
        
        if not summary or not description:
            return 0.0
        
        score = 0.0
        max_score = 10.0
        
        # ===== FACTOR 1: DEDUPLICATION (0-2 points) =====
        # Penalize if description just repeats summary
        summary_words = set(summary.lower().split())
        desc_words = set(description.lower().split())
        
        if summary_words and desc_words:
            union_size = len(summary_words | desc_words)
            intersection_size = len(summary_words & desc_words)
            overlap_ratio = intersection_size / union_size if union_size > 0 else 0
            
            # Less overlap = higher score
            # 0% overlap = 2 points (perfect)
            # 50% overlap = 1 point (mediocre)
            # 70%+ overlap = 0 points (boilerplate)
            if overlap_ratio < 0.3:
                score += 2.0
            elif overlap_ratio < 0.5:
                score += 1.5
            elif overlap_ratio < 0.7:
                score += 0.5
            # else: score += 0
        
        # ===== FACTOR 2: CODE-SPECIFICITY (0-3 points) =====
        # Reward using actual component names
        code_keywords = set()
        
        # Add parameter names
        if component.parameters:
            code_keywords.update(p.name.lower() for p in component.parameters)
        
        # Add API-specific keywords
        if component.type == ComponentType.API_ENDPOINT:
            if component.http_method:
                code_keywords.add(component.http_method.lower())
            if component.path_parameters:
                code_keywords.update(p.lower() for p in component.path_parameters)

        # Add global state names
        if code_facts.get('modifies_global_state'):
            code_keywords.update(code_facts['modifies_global_state'])
        
        # Add operation keywords
        if code_facts.get('operations'):
            code_keywords.update(code_facts['operations'])
        
        # Add exception names
        if code_facts.get('raises'):
            code_keywords.update(e.get('exception', '').lower() for e in code_facts['raises'])
        
        if code_keywords:
            mentions = len(code_keywords & set(description.lower().split()))
            specificity_score = (mentions / len(code_keywords)) * 3.0
            score += min(3.0, specificity_score)
        
        # ===== FACTOR 3: BEHAVIORAL VS STRUCTURAL (0-2 points) =====
        # Reward behavioral language, penalize structural
        behavioral_keywords = {
            'creates', 'returns', 'raises', 'modifies', 'updates', 'manages',
            'coordinates', 'transitions', 'handles', 'processes', 'validates',
            'ensures', 'guarantees', 'maintains', 'tracks', 'schedules',
            'initializes', 'cleans', 'removes', 'adds', 'blocks', 'releases'
        }
        
        structural_keywords = {
            'contains', 'has', 'stores', 'represents', 'defines', 'includes',
            'this function', 'this class', 'this variable', 'the code',
            'does something', 'performs', 'handles things', 'manages data'
        }
        
        behavioral_count = len(behavioral_keywords & set(description.lower().split()))
        structural_count = len(structural_keywords & set(description.lower().split()))
        
        behavioral_score = behavioral_count / max(behavioral_count + structural_count, 1)
        score += behavioral_score * 2.0
        
        # ===== FACTOR 4: COMPLETENESS (0-2 points) =====
        completeness = 0.0
        
        # Parameters documented
        if component.parameters and doc_data.get('parameters'):
            actual_params = {p.name for p in component.parameters}
            documented_params = {p.get('name') for p in doc_data.get('parameters', []) if p.get('name')}
            if actual_params & documented_params:
                completeness += min(1.0, len(actual_params & documented_params) / len(actual_params))
        
        # Returns documented (if applicable)
        if component.return_type and component.return_type != 'None':
            if doc_data.get('returns') and doc_data['returns'].get('description'):
                completeness += 0.5
        
        # Exceptions documented (if applicable)
        if code_facts.get('raises'):
            if doc_data.get('raises') and len(doc_data['raises']) > 0:
                completeness += 0.5
        
        score += completeness
        
        # ===== FACTOR 5: LENGTH APPROPRIATENESS (0-1 point) =====
        # Good description: 100-400 chars
        desc_len = len(description)
        if 100 <= desc_len <= 400:
            score += 1.0
        elif 50 <= desc_len < 100 or 400 < desc_len <= 600:
            score += 0.5
        
        # Normalize to 0-1 range
        normalized = score / max_score
        return min(1.0, max(0.0, normalized))

   
    def _validate_raises_against_code_facts(
        self,
        raises_from_llm: List[Dict[str, str]],
        code_facts: Dict[str, Any],
        component: CodeComponent
    ) -> List[Dict[str, str]]:
        """
        FIX: Don't filter out everything if Navigator found 0 exceptions.
        Sometimes the LLM is right and the tool missed it.
        """
        if not raises_from_llm:
            return []
        
        # Get verified exceptions from Navigator
        verified_exceptions = {
            exc.get('exception', '').lower() 
            for exc in code_facts.get('raises', [])
        }
        
        # INEFFICIENCY FIX: If Navigator found 0, trust LLM but warn. 
        # Only filter if Navigator found SOME but not THIS ONE.
        if not verified_exceptions:
            return raises_from_llm[:2] # Limit hallucinations to 2 if unverified
        
        filtered_raises = []
        for llm_raise in raises_from_llm:
            exc_name = llm_raise.get('exception', '').lower()
            if exc_name in verified_exceptions:
                filtered_raises.append(llm_raise)
            else:
                self.logger.debug(
                    f"[EXCEPTION FILTER] {component.name}: "
                    f"Filtering unverified exception '{exc_name}'. "
                    f"Verified: {verified_exceptions}"
                )
        
        return filtered_raises

    def _extract_global_usage(self, component: CodeComponent, context: Dict[str, Any]) -> str:
        """
        Extract usage context for global variables.
        Analyzes where the global is read/modified in the codebase.
        """
        if component.type != ComponentType.GLOBAL_VARIABLE:
            return ""
        
        usage_lines = []
        
        # Check shared state dependencies
        shared_deps = component.metadata.get('shared_state_dependencies', [])
        if shared_deps:
            usage_lines.append(f"Modified by: {', '.join(shared_deps[:3])}")
        
        # Check if it's marked as constant (immutable)
        is_constant = not shared_deps
        if is_constant:
            usage_lines.append("Read-only constant - used for configuration")
        else:
            usage_lines.append("Mutable state - tracked and modified during execution")
        
        # Get type from source code
        source = component.source_code
        if '=' in source:
            rhs = source.split('=', 1)[1].strip()
            usage_lines.append(f"Initialized as: {rhs[:50]}")
        
        return "\n".join(usage_lines) if usage_lines else "Module-level constant or state variable"

    def _analyze_return_values(self, component: CodeComponent, code_facts: Dict[str, Any]) -> str:
        """
        Analyze what return statements actually produce.
        Generates semantic meaning for return types.
        """
        return_type = component.return_type or 'any'
        actual_returns = code_facts.get('actual_returns', [])
        
        if not actual_returns or return_type == 'None':
            return "None; modifies state or side effects only"
        
        if len(actual_returns) == 0:
            return f"Returns {return_type}"
        
        first_return = actual_returns[0]
        
        # Analyze return statement patterns
        if first_return in ('True', 'False'):
            return f"{return_type}: Boolean success/failure indicator"
        
        if first_return == 'None':
            return "None; function completes without returning value"
        
        if '{' in first_return or return_type in ('dict', 'Dict'):
            # Extract dict keys if possible
            key_pattern = r'"(\w+)":|\'(\w+)\':'
            keys = re.findall(key_pattern, first_return)
            if keys:
                key_names = [k[0] or k[1] for k in keys]
                return f"{return_type}: Dictionary with keys {{{', '.join(key_names[:3])}}}"
            return f"{return_type}: Structured dictionary response"
        
        if '[' in first_return or return_type in ('list', 'List'):
            return f"{return_type}: Collection of items"
        
        if '(' in first_return and ')' in first_return:
            # Likely a function call
            func_name = first_return.split('(')[0].strip()
            return f"{return_type}: Result from {func_name}()"
        
        return f"{return_type}: {first_return[:50]}"