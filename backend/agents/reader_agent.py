"""
Reader Agent
Analyzes code components and determines information needs (Language-Agnostic)

Process:
    Step 1: Code Analysis
        - What does this code DO?
        - What does it CALL? (internal dependencies)
        - What CALLS it? (usage patterns - for public components)

    Step 2: Context Sufficiency Check
        - Is current context ENOUGH?
            - Simple/obvious code → NO CONTEXT NEEDED
            - Complex/unclear code → NEED CONTEXT
        - What TYPE of context is missing?
            - INTERNAL: Related code in same repo
            - EXTERNAL: Novel algorithms, new techniques (EXPENSIVE - use sparingly)

    Step 3: Generate Structured XML Request
        - Output clean XML with specific needs for Searcher Agent
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from xml.etree import ElementTree as ET
from xml.dom import minidom
from pathlib import Path

from backend.agents.base_agent import BaseAgent, AgentContext, AgentResult, AgentStatus
from backend.models.code_component import CodeComponent, ComponentType
from backend.utils.logger import get_logger
from backend.utils.file_handler import FileHandler
from backend.utils.paths import DATA_ROOT

logger = get_logger(__name__)


@dataclass
class ReaderOutput:
    """
    Minimal output from Reader Agent.
    Just the XML string - Searcher Agent will parse what it needs.
    """
    component_id: str
    xml_output: str
    needs_context: bool = False


class ReaderAgent(BaseAgent):
    """
    Reader Agent: Analyzes code components and determines information needs.
    
    Language-agnostic design:
        - Uses CodeComponent abstraction (already parsed by Navigator)
        - No language-specific parsing or syntax checks
        - Relies on Navigator's extracted metadata (calls, depends_on, complexity)
    
    Output:
        Clean XML response for Searcher Agent with:
        - INFO_NEED: true/false
        - COMPLEXITY: simple/moderate/complex
        - REQUEST:
            - INTERNAL: CALLS (what this component calls) + CALLED_BY (who calls this)
            - EXTERNAL: QUERY (only for novel/SOTA algorithms)
    """
    
    # Complexity scoring thresholds
    SIMPLE_THRESHOLD = 5
    COMPLEX_THRESHOLD = 15
    
    def __init__(self):
        super().__init__("reader")
        # Initialize output directory for XML persistence
        self.output_dir = DATA_ROOT / "intermediate" / "agent_output" / "reader"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Consolidated XML output tracking
        self.consolidated_outputs = []  # List of (component_id, xml_output) tuples
        # Component map for type lookup
        self.component_map: Dict[str, CodeComponent] = {}
    
    def set_component_map(self, all_components: List[CodeComponent]) -> None:
        """
        Set the component map for accurate type lookup.
        Should be called before processing components.
        
        Args:
            all_components: All components from Navigator
        """
        self.component_map = {comp.id: comp for comp in all_components}
        self.logger.info(f"Reader component map loaded: {len(self.component_map)} components")
    
    def process(self, context: AgentContext) -> AgentResult:
        """
        Process a single component and determine information needs.
        
        Args:
            context: AgentContext containing CodeComponent
            
        Returns:
            AgentResult with XML output string
        """
        try:
            component = context.component
            self.logger.info(f"Reader analyzing: {component.name} ({component.type.value})")
            
            # Step 1: Analyze code structure (from Navigator's data)
            analysis = self._analyze_component(component)
            
            # Step 2: Determine if context is needed (LLM decision with unified response)
            assessment = self._assess_context_sufficiency(component, analysis)
            needs_context = assessment['needs_context']
            
            # Step 3: Generate structured XML request with external classification
            xml_output = self._generate_xml_output(component, analysis, assessment)
            
            # Save XML output for debugging/analysis
            self._save_xml_output(component.id, xml_output)
            
            # Track for consolidated output
            self.consolidated_outputs.append((component.id, xml_output))
            
            self.logger.info(
                f"Reader complete: {component.name} | "
                f"Needs context: {needs_context} | "
                f"External: {assessment['external_classification']} | "
                f"Calls: {len(analysis['calls']['FUNCTION']) + len(analysis['calls']['CLASS']) + len(analysis['calls']['METHOD'])} | "
                f"Complexity: {analysis['complexity_level']}"
            )
            
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.SUCCESS,
                output=xml_output,
                metadata={
                    'component_id': component.id,
                    'needs_context': needs_context,
                    'external_classification': assessment['external_classification'],
                    'external_query': assessment['external_query'],
                    'complexity_level': analysis['complexity_level']
                }
            )
            
        except Exception as e:
            self.logger.error(f"Reader agent error: {e}", exc_info=True)
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILED,
                output=None,
                error=str(e)
            )
    
    def process_batch(self, contexts: List[AgentContext]) -> List[AgentResult]:
        """
        Process multiple components in a single LLM call (batch mode).
        
        Args:
            contexts: List of AgentContext objects
            
        Returns:
            List of AgentResult objects
        """
        try:
            components = [ctx.component for ctx in contexts]
            batch_size = len(components)
            
            self.logger.info(f"Reader batch analyzing: {batch_size} components")
            
            # Step 1: Analyze all components
            analyses = [self._analyze_component(comp) for comp in components]
            
            # Step 2: Assess context for all components in a single LLM call (true batch)
            # This reduces LLM calls from N (one per component) to 1
            assessments = self._batch_assess_context_sufficiency(components, analyses)
            
            # Step 3: Generate XML for each component with unified assessment
            results = []
            for i, (component, analysis, assessment) in enumerate(zip(components, analyses, assessments)):
                xml_output = self._generate_xml_output(component, analysis, assessment)
                
                # Save XML output for debugging/analysis
                self._save_xml_output(component.id, xml_output)
                
                # Track for consolidated output
                self.consolidated_outputs.append((component.id, xml_output))
                
                results.append(AgentResult(
                    agent_name=self.agent_name,
                    status=AgentStatus.SUCCESS,
                    output=xml_output,
                    metadata={
                        'component_id': component.id,
                        'needs_context': assessment['needs_context'],
                        'external_classification': assessment['external_classification'],
                        'external_query': assessment['external_query'],
                        'complexity_level': analysis['complexity_level']
                    }
                ))
            
            context_needed_count = sum(1 for a in assessments if a['needs_context'])
            novel_count = sum(1 for a in assessments if a['external_classification'] in ['novel_algorithm', 'novel_technique'])
            self.logger.info(
                f"Reader batch complete: {batch_size} components | "
                f"Context needed: {context_needed_count} | "
                f"Novel concepts: {novel_count}"
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Reader batch error: {e}", exc_info=True)
            return [
                AgentResult(
                    agent_name=self.agent_name,
                    status=AgentStatus.FAILED,
                    output=None,
                    error=str(e)
                )
                for _ in contexts
            ]
    
    # =========================================================================
    # STEP 1: Code Analysis (Language-Agnostic)
    # =========================================================================
    
    def _analyze_component(self, component: CodeComponent) -> Dict[str, Any]:
        """
        Analyze component structure using Navigator's extracted data.
        No language-specific parsing - uses CodeComponent abstraction.
        
        Returns:
            Dict with: calls, complexity_level, is_public, control_flow
        """
        # Extract what this component CALLS (internal dependencies)
        calls = self._extract_calls(component)
        
        # Determine complexity level
        complexity_level = self._calculate_complexity_level(component)
        
        # Check visibility (language-agnostic via CodeComponent)
        is_public = self._is_public(component)
        
        # Get control flow characteristics (from Navigator)
        control_flow = component.metadata.get('control_flow', {})
        
        return {
            'calls': calls,
            'complexity_level': complexity_level,
            'is_public': is_public,
            'control_flow': control_flow,
            'has_existing_docs': bool(component.existing_docstring),
        }
    
    def _extract_calls(self, component: CodeComponent) -> Dict[str, List[str]]:
        """
        Extract what this component calls, categorized by ACTUAL type.
        Uses component_map to look up real types instead of guessing from names.
        
        Returns:
            Dict with keys: CLASS, FUNCTION, METHOD
        """
        class_calls = []
        function_calls = []
        method_calls = []
        
        # Extract dependencies and categorize by ACTUAL type
        for dep_id in (component.depends_on or []):
            # Look up the actual component to get its real type
            dep_component = self.component_map.get(dep_id)
            
            if dep_component:
                # Use the ACTUAL component type
                dep_type_str = str(dep_component.type).lower()
                
                # Normalize ComponentType enum to string
                if 'componenttype.' in dep_type_str:
                    dep_type_str = dep_type_str.split('.')[-1]
                
                # Categorize by actual type
                if dep_type_str == 'class':
                    class_calls.append(dep_id)
                elif dep_type_str == 'function':
                    function_calls.append(dep_id)
                elif dep_type_str == 'method':
                    method_calls.append(dep_id)
                else:
                    # Fallback for other types (module, etc.) - treat as function
                    function_calls.append(dep_id)
            else:
                # Fallback to name-based heuristic if component not in map
                call_name = self._extract_name_from_id(dep_id)
                
                # Method call pattern: contains '.' (e.g., self.method, obj.method)
                if '.' in call_name and call_name.count('.') >= 2:
                    method_calls.append(dep_id)
                # Class instantiation pattern: starts with uppercase
                elif call_name and call_name[0].isupper():
                    class_calls.append(dep_id)
                # Function call
                else:
                    function_calls.append(dep_id)
        
        return {
            'CLASS': list(set(class_calls)),
            'FUNCTION': list(set(function_calls)),
            'METHOD': list(set(method_calls)),
        }
    
    def _calculate_complexity_level(self, component: CodeComponent) -> str:
        """
        Calculate complexity using HYBRID APPROACH for precision:
        - Method 1: Cognitive Complexity (nested control flow)
        - Method 2: Nesting Depth Analysis (max nesting level)
        - Method 3: Coupling Metrics (dependencies + dependents)
        
        Returns:
            'simple', 'moderate', or 'complex'
        """
        # Method 1: Cognitive Complexity (weighted most heavily)
        cognitive_score = self._calculate_cognitive_complexity(component)
        
        # Method 2: Nesting Depth (max nesting level)
        max_nesting = self._extract_max_nesting_depth(component)
        
        # Method 3: Coupling (dependencies + dependents)
        coupling_score = self._calculate_coupling_score(component)
        
        # Weighted combination for precision
        total_score = (
            cognitive_score * 0.5 +      # Most important: readability
            max_nesting * 2.0 +          # Critical: nesting multiplier
            coupling_score * 0.3         # Supporting: maintainability
        )
        
        if total_score <= self.SIMPLE_THRESHOLD:
            return 'simple'
        elif total_score <= self.COMPLEX_THRESHOLD:
            return 'moderate'
        else:
            return 'complex'
    
    def _calculate_cognitive_complexity(self, component: CodeComponent) -> float:
        """
        Calculate Cognitive Complexity (focus on human understanding).
        Higher for nested control structures and complex branching.
        
        Returns:
            Float score (0-100)
        """
        control_flow = component.metadata.get('control_flow', {})
        
        # Base score from cyclomatic complexity
        cyclomatic = component.complexity or 1
        score = cyclomatic * 1.5
        
        # Penalty for nested constructs (exponential)
        num_branches = control_flow.get('num_branches', 0)
        has_loops = control_flow.get('has_loop', False)
        has_try_except = control_flow.get('has_try_except', False)
        
        # Nested branches compound complexity (not linear)
        if num_branches > 0:
            score += num_branches * 2
        
        # Loops in combination with branches = harder
        if has_loops and num_branches > 0:
            score += 5  # Extra penalty for complexity interaction
        elif has_loops:
            score += 2
        
        # Exception handling adds cognitive load
        if has_try_except:
            score += 3
        
        # Async operations harder to reason about
        if control_flow.get('has_async_operations', False):
            score += 4
        
        # Infinite loops are anti-pattern (high cognitive cost)
        if control_flow.get('has_infinite_loop', False):
            score += 8
        
        return min(score, 100)  # Cap at 100
    
    def _extract_max_nesting_depth(self, component: CodeComponent) -> int:
        """
        Calculate maximum nesting depth from source code.
        Scans source for indentation levels (language-agnostic).
        
        Returns:
            Integer: max nesting depth (0-10+)
        """
        source = component.source_code or ""
        if not source:
            return 0
        
        lines = source.split('\n')
        max_depth = 0
        
        for line in lines:
            if not line.strip():  # Skip empty lines
                continue
            
            # Count leading whitespace as proxy for nesting
            # Each indent level (4 spaces or 1 tab) = 1 nesting level
            indent_length = len(line) - len(line.lstrip())
            indent_str = line[:indent_length]
            
            # Handle tabs (1 tab = 1 level)
            if '\t' in indent_str:
                depth = indent_str.count('\t')
            else:
                # Convert spaces to indent levels (assume 4 spaces = 1 level)
                depth = indent_length // 4
            
            max_depth = max(max_depth, depth)
        
        # Normalize: depths > 6 are extremely rare and problematic
        # Use square root to compress very deep nesting
        if max_depth > 6:
            return int((max_depth ** 0.7) * 2)  # Penalize deep nesting
        
        return max_depth
    
    def _calculate_coupling_score(self, component: CodeComponent) -> float:
        """
        Calculate coupling complexity (how much this depends on others).
        Higher coupling = harder to understand in isolation.
        
        Returns:
            Float score (0-20)
        """
        # Count what this component depends on (efferent coupling)
        dependencies = len(component.depends_on or [])
        
        # Multiple parameters also indicate high coupling
        params = len(component.parameters or [])
        
        # Combine: dependencies are more critical than params
        score = (
            min(dependencies, 10) * 1.2 +  # Weight external deps
            min(params, 8) * 0.8             # Weight parameters
        )
        
        return min(score, 20)  # Cap at 20 for weighting balance
    
    def _is_public(self, component: CodeComponent) -> bool:
        """
        Check if component is public (language-agnostic).
        Uses CodeComponent.is_public if available, otherwise heuristics.
        """
        # Use Navigator's extracted visibility if available
        if hasattr(component, 'is_public') and component.is_public is not None:
            return component.is_public
        
        # Fallback: check name patterns (works for Python, JS, etc.)
        name = component.name or ''
        
        # Common private patterns: _name, __name, #name (JS private)
        if name.startswith('_') or name.startswith('#'):
            return False
        
        return True
    
    def _extract_name_from_id(self, component_id: str) -> str:
        """Extract component name from ID (format: file_path:component_name)"""
        if ':' in component_id:
            return component_id.split(':')[-1]
        return component_id
    
    # =========================================================================
    # STEP 2: Context Sufficiency Check (LLM-based)
    # =========================================================================
    
    def _assess_context_sufficiency(
        self,
        component: CodeComponent,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use LLM to determine if additional context is needed.
        Returns unified result with both internal and external needs.
        
        Decision criteria:
            YES (need context) when:
                - Complex/non-obvious algorithms
                - Concurrency/threading patterns
                - Critical dependencies affecting behavior
                - Domain-specific knowledge required
                
            NO (self-explanatory) when:
                - Code is straightforward
                - Name describes behavior clearly
                - Dependencies are simple utilities
        
        Returns:
            Dict with:
                - needs_context: bool
                - llm_response: str (raw LLM output)
                - external_classification: str
                - external_query: str (empty if not needed)
        """
        # Quick skip for truly simple components
        if analysis['complexity_level'] == 'simple' and not analysis['calls']['FUNCTION']:
            self.logger.debug(f"Skipping LLM for simple component: {component.name}")
            return {
                'needs_context': False,
                'llm_response': '',
                'external_classification': 'standard_pattern',
                'external_query': ''
            }
        
        prompt = self._build_context_assessment_prompt(component, analysis)
        system_prompt = self._get_context_assessment_system_prompt()
        
        try:
            response = self.generate_with_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=500  # Increased for structured XML response
            )
            
            # Parse structured response
            result = self._parse_unified_llm_response(response, component.name)
            self.logger.debug(f"LLM decision for {component.name}: needs_context={result['needs_context']}, external={result['external_classification']}")
            return result
            
        except Exception as e:
            self.logger.warning(f"LLM assessment failed for {component.name}: {e}")
            # Fallback: request context for non-simple components
            return {
                'needs_context': analysis['complexity_level'] != 'simple',
                'llm_response': '',
                'external_classification': 'standard_pattern',
                'external_query': ''
            }
    
    def _parse_unified_llm_response(self, response: str, component_name: str) -> Dict[str, Any]:
        """
        Parse unified LLM response containing INFO_NEED, COMPLEXITY, and REQUEST sections.
        
        Args:
            response: Raw LLM response text
            component_name: For logging
            
        Returns:
            Dict with parsed fields
        """
        result = {
            'needs_context': False,
            'llm_response': response,
            'external_classification': 'standard_pattern',
            'external_query': ''
        }
        
        try:
            # Parse INFO_NEED
            if '<INFO_NEED>true</INFO_NEED>' in response.lower():
                result['needs_context'] = True
            elif '<INFO_NEED>false</INFO_NEED>' in response.lower():
                result['needs_context'] = False
            else:
                # Fallback: check for YES/NO pattern
                if response.strip().upper().startswith('YES'):
                    result['needs_context'] = True
            
            # Parse EXTERNAL CLASSIFICATION
            classification_patterns = [
                'novel_algorithm', 'novel_technique', 
                'standard_library', 'standard_pattern'
            ]
            for pattern in classification_patterns:
                if f'<CLASSIFICATION>{pattern}</CLASSIFICATION>' in response.lower():
                    result['external_classification'] = pattern
                    break
            
            # Parse EXTERNAL QUERY (only if novel)
            if result['external_classification'] in ['novel_algorithm', 'novel_technique']:
                import re
                query_match = re.search(r'<QUERY>([^<]+)</QUERY>', response, re.IGNORECASE)
                if query_match:
                    query = query_match.group(1).strip()
                    if query and query.lower() not in ['', 'none', 'empty']:
                        result['external_query'] = query
            
            return result
            
        except Exception as e:
            self.logger.warning(f"Failed to parse LLM response for {component_name}: {e}")
            return result
    
    def _batch_assess_context_sufficiency(
        self,
        components: List[CodeComponent],
        analyses: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Batch LLM call to assess context sufficiency for multiple components.
        This makes a SINGLE LLM call for all components instead of N calls.
        
        Returns:
            List of assessment dicts with: needs_context, llm_response, external_classification, external_query
        """
        # Quick skip for simple components that don't need LLM
        assessments = []
        components_needing_llm = []
        component_indices = []  # Track which components need LLM
        
        for idx, (comp, analysis) in enumerate(zip(components, analyses)):
            # Simple components without function calls can skip LLM
            if analysis['complexity_level'] == 'simple' and not analysis['calls']['FUNCTION']:
                self.logger.debug(f"Skipping LLM for simple component: {comp.name}")
                assessments.append({
                    'needs_context': False,
                    'llm_response': '',
                    'external_classification': 'standard_pattern',
                    'external_query': ''
                })
            else:
                components_needing_llm.append(comp)
                component_indices.append(idx)
                # Placeholder to be filled later
                assessments.append(None)
        
        # If no components need LLM, return early
        if not components_needing_llm:
            return assessments
        
        # Build batch prompt for components that need LLM
        prompt = self._build_batch_context_prompt(components_needing_llm, [analyses[i] for i in component_indices])
        system_prompt = self._get_context_assessment_system_prompt()
        
        try:
            response = self.generate_with_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=100 * len(components_needing_llm)  # More tokens for batch
            )
            
            # Parse response and fill in the LLM-based assessments
            llm_decisions = self._parse_batch_decisions_with_assessments(
                response, components_needing_llm, [analyses[i] for i in component_indices]
            )
            
            # Put the LLM decisions back in the right places
            for llm_idx, original_idx in enumerate(component_indices):
                assessments[original_idx] = llm_decisions[llm_idx]
            
            self.logger.info(f"Batch assessment: {len(components_needing_llm)}/{len(components)} components analyzed by LLM")
            return assessments
            
        except Exception as e:
            self.logger.warning(f"Batch LLM assessment failed: {e}")
            # Fallback: fill in remaining assessments based on complexity
            for idx, original_idx in enumerate(component_indices):
                assessments[original_idx] = {
                    'needs_context': analyses[original_idx]['complexity_level'] != 'simple',
                    'llm_response': '',
                    'external_classification': 'standard_pattern',
                    'external_query': ''
                }
            return assessments
    
    def _build_context_assessment_prompt(
        self,
        component: CodeComponent,
        analysis: Dict[str, Any]
    ) -> str:
        """Build prompt for single component context assessment with unified internal/external handling."""
        control_flow = analysis['control_flow']
        calls = analysis['calls']
        
        # Format calls for display
        calls_summary = []
        if calls['CLASS']:
            calls_summary.append(f"Classes: {', '.join(calls['CLASS'][:5])}")
        if calls['FUNCTION']:
            calls_summary.append(f"Functions: {', '.join(calls['FUNCTION'][:5])}")
        if calls['METHOD']:
            calls_summary.append(f"Methods: {', '.join(calls['METHOD'][:5])}")
        calls_str = '\n    '.join(calls_summary) if calls_summary else 'None'
        
        return f"""Analyze this code component and determine what additional context is needed.

## Component Information
- **Name:** {component.name}
- **Type:** {component.type.value}
- **Visibility:** {"Public" if analysis['is_public'] else "Private"}
- **Estimated Complexity:** {analysis['complexity_level']}
- **Lines of Code:** {component.lines_of_code or 0}

## Detected Calls
    {calls_str}

## Control Flow Characteristics
- Async Operations: {control_flow.get('is_async', False)}
- Contains Loops: {control_flow.get('has_loop', False)}
- Concurrency Patterns: {control_flow.get('has_concurrency', False)}
- Number of Branches: {control_flow.get('num_branches', 0)}
- Exception Handling: {control_flow.get('has_try_except', False)}

## Source Code
```
{component.source_code}
```

Analyze and respond with:
1. Brief analysis (1-2 sentences)
2. What additional information is needed (if any)
3. Structured XML response with INFO_NEED, COMPLEXITY, and REQUEST sections

Remember:
- EXTERNAL queries are EXPENSIVE - only for novel algorithms/techniques
- Most standard library code needs NO external retrieval
- Focus on what's truly needed for documentation"""
    
    def _build_batch_context_prompt(
        self,
        components: List[CodeComponent],
        analyses: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for batch context assessment."""
        prompt = "Analyze these components and determine if each needs additional context.\n\n"
        
        for i, (comp, analysis) in enumerate(zip(components, analyses), 1):
            prompt += f"""=== COMPONENT {i}: {comp.name} ===
Type: {comp.type.value} | Complexity: {analysis['complexity_level']} | Lines: {comp.lines_of_code or 0}
Calls: {len(comp.calls or [])} | Async: {analysis['control_flow'].get('is_async', False)}
Code:
```
{comp.source_code[:300]}{'...' if len(comp.source_code or '') > 300 else ''}
```

"""
        
        prompt += """Respond EXACTLY in this format:
COMPONENT 1: YES/NO - reason
COMPONENT 2: YES/NO - reason
..."""
        
        return prompt
    
    def _get_context_assessment_system_prompt(self) -> str:
        """System prompt for unified context assessment (internal + external)."""
        return """You are a Reader Agent responsible for determining if more context is needed to generate a high-quality docstring. You should analyze the code component and current context to make this determination.

You have access to two types of information sources:

1. Internal Codebase Information (from local code repository):
    For Functions:
    - Code components called within the function body
    - Places where this function is called

    For Methods:
    - Code components called within the method body
    - Places where this method is called
    - The class this method belongs to

    For Classes:
    - Code components called in the __init__ method
    - Places where this class is instantiated
    - Complete class implementation beyond __init__

2. External Open Internet Retrieval Information:
    - External Retrieval is EXTREMELY EXPENSIVE. Only request external open internet
      retrieval information if the component involves a novel, state-of-the-art,
      recently-proposed algorithms or techniques.
    
    REQUEST EXTERNAL ONLY FOR:
    - Novel loss functions (NDCG Loss, Alignment and Uniformity Loss, Focal Loss, etc)
    - State-of-the-art techniques (Transformers, Vision Transformers, Diffusion Models, etc)
    - Recently proposed methods or specialized metrics (Cohen's Kappa, BLEU, ROUGE, etc)
    - Cutting-edge research implementations
    - Proprietary or experimental algorithms
    
    DO NOT REQUEST EXTERNAL FOR:
    - Standard libraries (React, Redux, Vue, Angular, numpy, pandas, tensorflow, pytorch, etc)
    - Common patterns (CRUD, API calls, state management, routing, authentication)
    - Basic operations (loops, conditionals, arithmetic, string manipulation)
    - Well-known frameworks and their standard usage
    - Database operations (SQL queries, ORM patterns)
    - HTTP/REST API implementations

Your response should:
1. First provide a brief analysis of the current code and context
2. Explain what additional information might be needed (if any)
3. Include an <INFO_NEED>true</INFO_NEED> tag if more information is needed,
   or <INFO_NEED>false</INFO_NEED> if current context is sufficient
4. Include a <COMPLEXITY>simple|moderate|complex</COMPLEXITY> tag
5. If more information is needed, end your response with a structured XML request:

<REQUEST>
    <INTERNAL>
        <CALLS>
            <CLASS>class1,class2</CLASS>
            <FUNCTION>func1,func2</FUNCTION>
            <METHOD>self.method1,instance.method2</METHOD>
        </CALLS>
        <CALLED_BY>true/false</CALLED_BY>
    </INTERNAL>
    <EXTERNAL>
        <CLASSIFICATION>novel_algorithm|novel_technique|standard_library|standard_pattern</CLASSIFICATION>
        <QUERY>Clear natural language question for external retrieval (empty if standard)</QUERY>
    </EXTERNAL>
</REQUEST>

Important rules for structured request:

INTERNAL SECTION:
1. For CALLS sections, only include names that are explicitly needed
2. If no items exist for a category, use empty tags (e.g., <CLASS></CLASS>)
3. CALLED_BY should be "true" only if you need to know what calls/uses a component
4. For METHODS, keep dot notation in the same format as the input
5. Only first-level calls of the focal code component are accessible

EXTERNAL SECTION:
1. CLASSIFICATION: Determine if component falls into:
   - novel_algorithm: Novel loss functions, custom metrics, research implementations
   - novel_technique: State-of-the-art methods, cutting-edge approaches
   - standard_library: Common libraries (React, numpy, pandas, etc)
   - standard_pattern: Common patterns (CRUD, auth, state management)
2. QUERY: Only include a question if CLASSIFICATION is novel_algorithm or novel_technique
   - Each query should be a clear, natural language question
   - If standard_library or standard_pattern, leave QUERY empty

Critical rules:
1. Only request internal codebase information that is necessary for docstring generation
2. External Open-Internet retrieval is EXTREMELY expensive - only for truly novel concepts
3. For most standard library/framework components, you do NOT need additional information
4. You are NOT generating docstrings - only determining if more information is needed"""
    

    def _parse_batch_decisions_with_assessments(
        self,
        response: str,
        components: List[CodeComponent],
        analyses: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Parse batch LLM response into individual assessment dicts.
        
        Returns:
            List of dicts with: needs_context, llm_response, external_classification, external_query
        """
        assessments = []
        lines = response.strip().split('\n')
        
        for i, (comp, analysis) in enumerate(zip(components, analyses)):
            component_num = i + 1
            # Find line starting with "COMPONENT N:"
            matching = [l for l in lines if l.strip().startswith(f'COMPONENT {component_num}:')]
            
            needs_context = False
            external_classification = 'standard_pattern'
            external_query = ''
            
            if matching:
                line = matching[0]
                # Parse: "COMPONENT 1: YES/NO - reason"
                parts = line.split(':', 1)
                if len(parts) > 1:
                    decision = parts[1].strip().upper()
                    needs_context = decision.startswith('YES')
            else:
                # Fallback: use complexity
                needs_context = analysis['complexity_level'] != 'simple'
            
            assessments.append({
                'needs_context': needs_context,
                'llm_response': response,
                'external_classification': external_classification,
                'external_query': external_query
            })
        
        return assessments
    
    # =========================================================================
    # STEP 3: Generate Structured XML Output
    # =========================================================================
    
    def _generate_xml_output(
        self,
        component: CodeComponent,
        analysis: Dict[str, Any],
        assessment: Dict[str, Any]
    ) -> str:
        """
        Generate clean XML output for Searcher Agent.
        
        Args:
            component: The code component being analyzed
            analysis: Analysis results from _analyze_component
            assessment: LLM assessment result with needs_context, external_classification, external_query
        
        Format:
            <READER_OUTPUT>
                <INFO_NEED>true/false</INFO_NEED>
                <COMPLEXITY>simple/moderate/complex</COMPLEXITY>
                <REQUEST>
                    <INTERNAL>
                        <CALLS>
                            <CLASS>Class1,Class2</CLASS>
                            <FUNCTION>func1,func2</FUNCTION>
                            <METHOD>self.method1,obj.method2</METHOD>
                        </CALLS>
                        <CALLED_BY>true/false</CALLED_BY>
                    </INTERNAL>
                    <EXTERNAL>
                        <CLASSIFICATION>novel_algorithm|novel_technique|standard_library|standard_pattern</CLASSIFICATION>
                        <QUERY>Clear natural language question (empty if standard)</QUERY>
                    </EXTERNAL>
                </REQUEST>
            </READER_OUTPUT>
        """
        needs_context = assessment.get('needs_context', False)
        
        root = ET.Element('READER_OUTPUT')
        
        # INFO_NEED: Does this component need additional context?
        info_need = ET.SubElement(root, 'INFO_NEED')
        info_need.text = 'true' if needs_context else 'false'
        
        # COMPLEXITY: For downstream agents
        complexity = ET.SubElement(root, 'COMPLEXITY')
        complexity.text = analysis['complexity_level']
        
        # REQUEST: What context is needed?
        request = ET.SubElement(root, 'REQUEST')
        
        # INTERNAL: Code from same repository
        internal = ET.SubElement(request, 'INTERNAL')
        
        # CALLS: What this component calls (dependencies)
        calls_elem = ET.SubElement(internal, 'CALLS')
        calls = analysis['calls']
        
        if calls['CLASS']:
            class_elem = ET.SubElement(calls_elem, 'CLASS')
            class_elem.text = ','.join(calls['CLASS'])
        
        if calls['FUNCTION']:
            func_elem = ET.SubElement(calls_elem, 'FUNCTION')
            func_elem.text = ','.join(calls['FUNCTION'])
        
        if calls['METHOD']:
            method_elem = ET.SubElement(calls_elem, 'METHOD')
            method_elem.text = ','.join(calls['METHOD'])
        
        # CALLED_BY: Should Searcher find usage examples?
        # Only for public, non-simple components that need context
        called_by = ET.SubElement(internal, 'CALLED_BY')
        should_find_callers = (
            needs_context and
            analysis['is_public'] and
            analysis['complexity_level'] != 'simple' and
            component.type in [ComponentType.FUNCTION, ComponentType.METHOD, ComponentType.CLASS]
        )
        called_by.text = 'true' if should_find_callers else 'false'
        
        # EXTERNAL: Novel algorithms/techniques with LLM-determined classification
        external = ET.SubElement(request, 'EXTERNAL')
        
        # Classification from LLM (novel_algorithm, novel_technique, standard_library, standard_pattern)
        classification = assessment.get('external_classification', 'standard_pattern')
        classification_elem = ET.SubElement(external, 'CLASSIFICATION')
        classification_elem.text = classification
        
        # Query: Only populated for novel_algorithm or novel_technique
        query = assessment.get('external_query', '')
        
        # If LLM didn't provide a query but classification suggests novel, use fallback detection
        if not query and classification in ['novel_algorithm', 'novel_technique']:
            fallback_queries = self._detect_novel_concepts(component)
            query = fallback_queries[0] if fallback_queries else ''
        
        query_elem = ET.SubElement(external, 'QUERY')
        query_elem.text = query if query else ''
        
        # Convert to pretty XML string
        xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
        # Remove XML declaration and empty lines
        xml_str = '\n'.join([
            line for line in xml_str.split('\n')
            if line.strip() and '<?xml' not in line
        ])
        
        return xml_str
    
    def _detect_novel_concepts(self, component: CodeComponent) -> List[str]:
        """
        Detect truly novel/SOTA concepts that need external retrieval.
        
        IMPORTANT: External retrieval is EXPENSIVE. Only flag for:
            - Novel loss functions (NDCG Loss, Contrastive Loss, etc.)
            - Novel metrics (Cohen's Kappa, BLEU, etc.)
            - State-of-the-art algorithms mentioned in comments
            - Recently proposed techniques
        
        DO NOT flag for:
            - Standard libraries (numpy, pandas, sklearn, etc.)
            - Framework APIs (Django, FastAPI, PyTorch basics)
            - Built-in functions
            - Common algorithms (sorting, searching, etc.)
        """
        novel_concepts = []
        source = component.source_code or ''
        name = component.name or ''
        
        # Pattern 1: Comments mentioning "novel", "paper", "SOTA"
        novel_keywords = ['novel', 'paper', 'sota', 'state-of-the-art', 'proposed']
        for line in source.split('\n'):
            # Check comments
            if any(kw in line.lower() for kw in novel_keywords):
                # Extract from comment
                for marker in ['#', '//', '/*', '*']:
                    if marker in line:
                        comment = line.split(marker, 1)[-1].strip()
                        if len(comment) > 10 and len(comment) < 100:
                            novel_concepts.append(f"Novel concept: {comment[:80]}")
                            break
        
        # Pattern 2: Custom loss/metric implementations (not standard ones)
        STANDARD_LOSSES = {'CrossEntropyLoss', 'MSELoss', 'BCELoss', 'L1Loss', 'NLLLoss'}
        STANDARD_METRICS = {'accuracy', 'precision', 'recall', 'f1_score', 'auc'}
        
        if 'loss' in name.lower():
            # Check if it's a custom loss
            if not any(std in source for std in STANDARD_LOSSES):
                novel_concepts.append(f"Custom loss function: {name}")
        
        if 'metric' in name.lower() or 'score' in name.lower():
            # Check if it's a custom metric
            if not any(std in source.lower() for std in STANDARD_METRICS):
                novel_concepts.append(f"Custom metric: {name}")
        
        # Limit to top 3 most relevant
        return novel_concepts[:3]
    
    def _save_xml_output(self, component_id: str, xml_output: str) -> None:
        """
        Save Reader Agent XML output to disk for debugging/analysis.
        
        Args:
            component_id: The component identifier
            xml_output: The generated XML string
        """
        try:
            # Create filename from component_id, replacing special chars
            safe_id = component_id.replace(".", "_").replace("/", "_")
            output_file = self.output_dir / f"{safe_id}_reader_xml_output.xml"
            
            # Write XML to file
            with open(output_file, 'w', encoding='utf-8') as f:
                # Pretty-print XML for readability
                try:
                    root = ET.fromstring(xml_output)
                    pretty_xml = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
                    # Remove XML declaration and extra blank lines
                    pretty_xml = '\n'.join(line for line in pretty_xml.split('\n') 
                                          if line.strip() and not line.startswith('<?xml'))
                    f.write(pretty_xml)
                except ET.ParseError:
                    # Fallback: write raw XML if parsing fails
                    f.write(xml_output)
            
            self.logger.debug(f"Reader XML saved to: {output_file}")
            
        except Exception as e:
            self.logger.warning(f"Failed to save Reader XML output for {component_id}: {e}")
    
    def save_consolidated_output(self, filename: str = "consolidated_reader_output.xml") -> Path:
        """
        Save all collected XML outputs to a single consolidated XML file.
        
        Args:
            filename: Name of the consolidated output file
            
        Returns:
            Path to the consolidated output file
        """
        try:
            if not self.consolidated_outputs:
                self.logger.warning("No consolidated outputs to save")
                return None
            
            # Create root element
            root = ET.Element("CONSOLIDATED_READER_OUTPUT")
            root.set("timestamp", datetime.now().isoformat())
            root.set("total_components", str(len(self.consolidated_outputs)))
            
            # Add each component's output
            for component_id, xml_output in self.consolidated_outputs:
                try:
                    # Parse individual XML output
                    component_root = ET.fromstring(xml_output)
                    
                    # Create wrapper element for this component
                    component_elem = ET.SubElement(root, "COMPONENT")
                    component_elem.set("id", component_id)
                    component_elem.set("name", self._extract_name_from_id(component_id))
                    
                    # Copy the READER_OUTPUT content
                    for child in component_root:
                        component_elem.append(child)
                        
                except ET.ParseError as e:
                    self.logger.warning(f"Failed to parse XML for {component_id}: {e}")
                    continue
            
            # Write consolidated XML to file
            output_file = self.output_dir / filename
            tree = ET.ElementTree(root)
            
            # Pretty-print for readability
            pretty_xml = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
            # Remove XML declaration
            pretty_xml = '\n'.join(line for line in pretty_xml.split('\n') 
                                  if line.strip() and not line.startswith('<?xml'))
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write(pretty_xml)
            
            self.logger.info(f"Consolidated reader output saved to: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"Failed to save consolidated output: {e}", exc_info=True)
            return None
    
    def clear_consolidated_outputs(self) -> None:
        """Clear the consolidated outputs list."""
        self.consolidated_outputs = []