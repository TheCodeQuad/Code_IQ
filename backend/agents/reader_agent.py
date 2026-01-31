"""
Reader Agent
Analyzes code components and determines information needs
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import ast
import re
from xml.etree import ElementTree as ET
from xml.dom import minidom

from backend.agents.base_agent import BaseAgent, AgentContext, AgentResult, AgentStatus
from backend.models.code_component import CodeComponent, ComponentType
from backend.utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class InternalRequest:
    """Request for internal code information"""
    request_type: str  # "dependency" or "reference"
    component_id: str
    component_name: str
    reason: str
    priority: int = 5  # 1-10, higher = more important

@dataclass
class ExternalRequest:
    """Request for external knowledge"""
    request_type: str  # "algorithm", "library", "concept", "domain"
    query: str
    context: str
    priority: int = 5

@dataclass
class ReaderOutput:
    """Output from Reader Agent"""
    component_id: str
    complexity_assessment: Dict[str, Any]
    needs_additional_context: bool
    internal_requests: List[InternalRequest] = field(default_factory=list)
    external_requests: List[ExternalRequest] = field(default_factory=list)
    analysis_summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

class ReaderAgent(BaseAgent):
    """
    Reader Agent analyzes code components and determines information needs
    
    Process:
    1. Analyze component complexity
    2. Assess visibility (public/private)
    3. Identify dependencies that need context
    4. Identify references (usage examples)
    5. Detect external concepts/algorithms
    6. Generate structured information requests
    """
    
    def __init__(self):
        super().__init__("reader")
        
        # Complexity thresholds
        self.simple_complexity_threshold = 3
        self.complex_complexity_threshold = 20
        
        # Known libraries/frameworks that need explanation
        self.external_libraries = self._load_external_libraries()
        self.algorithms = self._load_known_algorithms()
    
    def _generate_xml_output(
        self,
        component: CodeComponent,
        needs_context: bool,
        internal_requests: List[InternalRequest],
        external_requests: List[ExternalRequest],
        control_flow: Dict[str, Any],
        complexity_assessment: Dict[str, Any] = None
    ) -> str:
        """
        Generate XML output in the format:
        <INFO_NEED>true/false</INFO_NEED>
        <COMPLEXITY>simple/moderate/complex</COMPLEXITY>
        <REQUEST>
            <INTERNAL>
                <CALLS>
                    <CLASS>class1,class2</CLASS>
                    <FUNCTION>func1,func2</FUNCTION>
                    <METHOD>self.method1,instance.method2</METHOD>
                </CALLS>
                <CALL_BY>true/false</CALL_BY>
            </INTERNAL>
            <RETRIEVAL>
                <QUERY>query1,query2</QUERY>
            </RETRIEVAL>
        </REQUEST>
        """
        root = ET.Element('READER_OUTPUT')
        
        # INFO_NEED element
        info_need = ET.SubElement(root, 'INFO_NEED')
        info_need.text = 'true' if needs_context else 'false'
        
        # COMPLEXITY element - for quick writer access
        if complexity_assessment:
            complexity = ET.SubElement(root, 'COMPLEXITY')
            complexity.text = complexity_assessment.get('complexity_level', 'unknown')
        
        # REQUEST element
        request = ET.SubElement(root, 'REQUEST')
        
        # INTERNAL element
        internal = ET.SubElement(request, 'INTERNAL')
        
        # CALLS element - group by component type
        calls = ET.SubElement(internal, 'CALLS')
        
        class_calls = []
        function_calls = []
        method_calls = []
        
        for req in internal_requests:
            if req.request_type == 'dependency':
                comp = self._extract_component_name(req.component_id)
                # Categorize by type (simple heuristic)
                if '.' in comp and not comp.startswith('_'):
                    method_calls.append(comp)
                else:
                    function_calls.append(comp)
        
        if class_calls:
            class_elem = ET.SubElement(calls, 'CLASS')
            class_elem.text = ','.join(class_calls)
        
        if function_calls:
            func_elem = ET.SubElement(calls, 'FUNCTION')
            func_elem.text = ','.join(function_calls)
        
        if method_calls:
            method_elem = ET.SubElement(calls, 'METHOD')
            method_elem.text = ','.join(method_calls)
        
        # CALL_BY element - whether to search for references
        call_by = ET.SubElement(internal, 'CALL_BY')
        has_reference_requests = any(req.request_type == 'reference' for req in internal_requests)
        call_by.text = 'true' if has_reference_requests else 'false'
        
        # RETRIEVAL element
        retrieval = ET.SubElement(request, 'RETRIEVAL')
        
        # QUERY element - gather all external queries
        if external_requests:
            queries = [f"{req.request_type}:{req.query}" for req in external_requests]
            query_elem = ET.SubElement(retrieval, 'QUERY')
            query_elem.text = ','.join(queries)
        
        # Convert to pretty string
        xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
        # Remove XML declaration and empty lines
        xml_str = '\n'.join([line for line in xml_str.split('\n') if line.strip() and '<?xml' not in line])
        
        return xml_str
    
    def process(self, context: AgentContext) -> AgentResult:
        """
        Process component and determine information needs.
        Returns XML output with custom format.
        """
        try:
            component = context.component
            
            self.logger.info(f"Reader analyzing: {component.name}")
            
            # Get Navigator's extracted control flow and metadata
            control_flow = component.metadata.get('control_flow', {})
            
            # Assess if additional context is needed
            needs_context = self._assess_information_needs(component, control_flow)
            
            # Generate requests based on identified needs
            internal_requests = []
            external_requests = []
            
            if needs_context:
                internal_requests = self._generate_internal_requests(component)
            
            project_dag = context.metadata.get('project_dag')
            external_requests = self._generate_external_requests(component, project_dag)
            
            # Build complexity assessment
            complexity_assessment = {
                'complexity_level': self._get_complexity_level(component),
                'lines_of_code': component.lines_of_code,
                'is_async': control_flow.get('is_async', False),
                'has_loops': control_flow.get('has_loop', False),
                'num_dependencies': len(component.depends_on),
                'num_calls': len(component.calls),
            }
            
            # Generate XML output (includes complexity)
            xml_output = self._generate_xml_output(
                component,
                needs_context,
                internal_requests,
                external_requests,
                control_flow,
                complexity_assessment
            )
            
            # Also store metadata for writer/searcher with full complexity_assessment
            metadata = {
                'component_id': component.id,
                'component_type': component.type,
                'is_public': self._is_public(component),
                'has_docstring': bool(component.existing_docstring),
                'is_async': control_flow.get('is_async', False),
                'has_threading': control_flow.get('has_concurrency', False),
                'complexity_level': complexity_assessment['complexity_level'],
                'complexity_assessment': complexity_assessment,  # Full assessment for Writer
                'needs_additional_context': needs_context,
                'lines_of_code': component.lines_of_code,
                'num_dependencies': len(component.depends_on),
                'num_calls': len(component.calls),
                'internal_requests': internal_requests,
                'external_requests': external_requests,
            }
            
            self.logger.info(
                f"Reader complete: "
                f"Needs context: {needs_context}, "
                f"Internal requests: {len(internal_requests)}, "
                f"External requests: {len(external_requests)}"
            )
            
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.SUCCESS,
                output=xml_output,
                metadata=metadata
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
        Process multiple components in a single LLM call (batch processing).
        Reduces token usage and latency by ~80%.
        
        Args:
            contexts: List of AgentContext objects (typically 5 per batch)
            
        Returns:
            List of AgentResults with individual ReaderOutputs
        """
        try:
            components = [ctx.component for ctx in contexts]
            batch_size = len(components)
            
            self.logger.info(f"Reader batch analyzing: {batch_size} components")
            
            # Create compact batch prompt
            prompt = self._create_batch_prompt(components)
            
            system_prompt = """You are a Reader Agent responsible for determining if additional context is needed to generate high-quality docstrings for code components.

For batch analysis, evaluate each component independently and provide clear YES/NO decisions."""
            
            # Single LLM call for entire batch
            response = self.generate_with_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=500
            )
            
            # Parse response to extract decisions for each component
            decisions = self._parse_batch_response(response, components)
            
            # Build individual AgentResults for each component
            results = []
            for i, component in enumerate(components):
                control_flow = component.metadata.get('control_flow', {})
                needs_context = decisions[i]['needs_context']
                reason = decisions[i]['reason']
                
                self.logger.info(f"Batch decision for {component.name}: {reason}")
                
                # Generate requests based on decision
                internal_requests = []
                if needs_context:
                    internal_requests = self._generate_internal_requests(component)
                
                project_dag = contexts[i].metadata.get('project_dag')
                external_requests = self._generate_external_requests(component, project_dag)
                
                # Generate XML output for batch processing too
                xml_output = self._generate_xml_output(
                    component,
                    needs_context,
                    internal_requests,
                    external_requests,
                    control_flow
                )
                
                # Store metadata alongside XML
                metadata = {
                    'component_id': component.id,
                    'component_type': component.type,
                    'is_public': self._is_public(component),
                    'has_docstring': bool(component.existing_docstring),
                    'is_async': control_flow.get('is_async', False),
                    'has_threading': control_flow.get('has_concurrency', False),
                    'complexity_level': self._get_complexity_level(component),
                    'lines_of_code': component.lines_of_code,
                    'num_dependencies': len(component.depends_on),
                    'num_calls': len(component.calls),
                    'internal_requests': internal_requests,
                    'external_requests': external_requests,
                }
                
                results.append(AgentResult(
                    agent_name=self.agent_name,
                    status=AgentStatus.SUCCESS,
                    output=xml_output,
                    metadata=metadata
                ))
            
            self.logger.info(
                f"Reader batch complete: {batch_size} components processed, "
                f"Context needed: {sum(1 for d in decisions if d['needs_context'])}"
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Reader batch error: {e}", exc_info=True)
            # Return failed results for entire batch
            return [
                AgentResult(
                    agent_name=self.agent_name,
                    status=AgentStatus.FAILED,
                    output=None,
                    error=str(e)
                )
                for _ in contexts
            ]
    
    def _get_complexity_level(self, component: CodeComponent) -> str:
        """Determine complexity level based on Navigator's metadata."""
        # Use Navigator's complexity if available, otherwise estimate
        cyclomatic = component.complexity or 1
        dependencies = len(component.depends_on)
        loc = component.lines_of_code
        params = len(component.parameters) if component.parameters else 0
        
        # Simple scoring based on Navigator's facts
        score = cyclomatic + min(dependencies, 5) + min(params, 3) + (loc // 15)
        
        if score <= self.simple_complexity_threshold:
            return 'simple'
        elif score <= self.complex_complexity_threshold:
            return 'moderate'
        else:
            return 'complex'
    
    def _assess_information_needs(
        self,
        component: CodeComponent,
        control_flow: Dict[str, Any]
    ) -> bool:
        """
        Use LLM to determine if component needs additional context for documentation.
        
        The LLM evaluates:
        - Code complexity and algorithmic patterns (recursion, complex control flow)
        - Dependencies and their criticality
        - Concurrency/threading patterns (explicit or implicit)
        - Exception handling complexity
        - Domain-specific knowledge requirements
        - Whether the code is self-explanatory or needs external context
        
        Returns:
            bool: True if additional context needed, False otherwise
        """
        complexity_level = self._get_complexity_level(component)
        
        prompt = f"""Analyze this code component and determine if additional context is needed to generate comprehensive documentation.

## Component Information
- **Name:** {component.name}
- **Type:** {component.type.value}
- **Visibility:** {"Public" if self._is_public(component) else "Private"}
- **Complexity Level:** {complexity_level}
- **Lines of Code:** {component.lines_of_code}
- **Dependencies:** {len(component.depends_on)} ({', '.join(component.depends_on[:5])}{'...' if len(component.depends_on) > 5 else ''})
- **Calls:** {len(component.calls)} functions/methods
- **Parameters:** {len(component.parameters) if component.parameters else 0}

## Control Flow Characteristics
- Is Async: {control_flow.get('is_async', False)}
- Has Loops: {control_flow.get('has_loop', False)}
- Has Infinite Loop: {control_flow.get('has_infinite_loop', False)}
- Has Concurrency/Threading: {control_flow.get('has_concurrency', False)}
- Has Try/Except: {control_flow.get('has_try_except', False)}
- Number of Branches: {control_flow.get('num_branches', 0)}

## Existing Documentation
{f'Has docstring: {component.existing_docstring[:200]}...' if component.existing_docstring else 'No existing docstring'}

## Source Code
```{component.language}
{component.source_code}
```

## Decision Criteria
Answer YES if ANY of these apply:
1. **Algorithmic complexity**: Uses recursion, complex branching, or non-obvious algorithms
2. **Concurrency patterns**: Uses locks, mutexes, threading, async/await, or has race condition risks
3. **Critical dependencies**: Depends on components whose behavior significantly affects this component
4. **Exception handling**: Has complex error handling that needs explanation
5. **Domain knowledge**: Requires understanding of external APIs, protocols, or domain-specific concepts
6. **State management**: Manages or coordinates shared state
7. **Non-obvious behavior**: The code does something that isn't immediately clear from reading it

Answer NO if ALL of these apply:
1. The code is straightforward and self-explanatory
2. No complex algorithms or patterns
3. Dependencies are simple/obvious (like basic utilities)
4. A developer can understand it completely just by reading the code

## Your Response
Respond with ONLY one of these exact formats:
- "YES: <brief reason>" if additional context is needed
- "NO: <brief reason>" if the code is self-explanatory"""

        system_prompt = """You are a Reader Agent responsible for determining if additional context is needed to generate high-quality docstrings for code components.

## Your Role
You analyze code components and make critical decisions about whether to gather external context (dependencies, usage examples, external APIs, algorithms) before documentation generation. Your goal is to ensure comprehensive, accurate documentation.

## Responsibilities
1. **Assess Complexity**: Evaluate the true complexity of the code, including hidden patterns (recursion, state management, concurrency)
2. **Identify Context Gaps**: Determine what information is missing that would help document the code better
3. **Make Binary Decisions**: Clearly decide YES or NO based on whether additional context is needed
4. **Provide Reasoning**: Explain your decision briefly so the system understands your logic

## Decision Framework
You should recommend YES (need additional context) when:
- The code uses non-obvious algorithms or patterns (recursion, dynamic programming, graph algorithms)
- There are hidden concurrency/threading patterns that aren't explicit
- The component depends on critical internal dependencies whose behavior affects documentation
- Complex exception handling requires explaining error scenarios
- External APIs or frameworks are used that need explanation
- The code manages shared state or coordinates across multiple components
- The behavior isn't immediately obvious from reading the source code
- Documentation requires usage examples to clarify behavior

You should recommend NO (self-explanatory) only when:
- The code is straightforward and does exactly what the name suggests
- All dependencies are obvious (built-in functions, simple utilities)
- No hidden complexity or non-obvious patterns exist
- A skilled developer can fully understand the code just by reading it
- The existing docstring (if any) already covers what needs explaining

## Important Guidelines
- **Err on the side of caution**: If unsure, recommend YES to ensure better documentation
- **Be practical**: Don't request context for genuinely simple utility functions
- **Look for hidden complexity**: Recursion, locks, async patterns, complex branching
- **Consider the reader**: Would someone unfamiliar with the codebase understand this component?
- **Focus on documentation quality**: The goal is comprehensive, maintainable documentation"""

        try:
            response = self.generate_with_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.1,  # Low temperature for consistent decisions
                max_tokens=100
            )
            
            response_upper = response.strip().upper()
            needs_context = response_upper.startswith("YES")
            
            # Log the decision for debugging
            self.logger.info(f"LLM context decision for {component.name}: {response.strip()}")
            
            return needs_context
            
        except Exception as e:
            self.logger.warning(f"LLM assessment failed for {component.name}: {e}")
            # Fallback: err on the side of getting context for non-simple components
            return complexity_level != 'simple'
    
    def _generate_internal_requests(
        self,
        component: CodeComponent
    ) -> List[InternalRequest]:
        """
        Generate requests for internal code information
        
        Args:
            component: Code component
            
        Returns:
            List of internal requests
        """
        requests = []
        
        # 1. Dependency requests
        # Request context for components that this component calls
        dependency_requests = self._generate_dependency_requests(component)
        requests.extend(dependency_requests)
        
        # 2. Reference requests
        # Request usage examples (where this component is called)
        reference_requests = self._generate_reference_requests(component)
        requests.extend(reference_requests)
        
        return requests
    
    def _generate_dependency_requests(
        self,
        component: CodeComponent
    ) -> List[InternalRequest]:
        """
        Generate requests for dependency information
        
        Args:
            component: Code component
            
        Returns:
            List of dependency requests
        """
        requests = []
        
        # Analyze each dependency
        for dep_id in component.depends_on:
            # Determine if this dependency needs context
            priority = self._calculate_dependency_priority(component, dep_id)
            
            if priority >= 3:  # Only request if priority is 3 or higher
                reason = self._explain_dependency_need(component, dep_id)
                
                requests.append(InternalRequest(
                    request_type="dependency",
                    component_id=dep_id,
                    component_name=self._extract_component_name(dep_id),
                    reason=reason,
                    priority=priority
                ))
        
        return requests
    
    def _generate_reference_requests(
        self,
        component: CodeComponent
    ) -> List[InternalRequest]:
        """Generate requests for reference/usage information"""
        requests = []
        
        # Only request usage examples for PUBLIC + COMPLEX or PUBLIC + AMBIGUOUS components
        if self._is_public(component) and component.type in [ComponentType.FUNCTION, ComponentType.METHOD, ComponentType.CLASS]:
            # Skip if already has good docstring
            if component.existing_docstring and len(component.existing_docstring) > 50:
                self.logger.debug(f"Skipping reference request for {component.name} - has good docstring")
                return requests
            
            # Skip if it's simple and self-contained
            if (len(component.parameters) <= 2 and 
                len(component.calls) <= 1 and 
                component.lines_of_code <= 10):
                self.logger.debug(f"Skipping reference request for {component.name} - simple and self-contained")
                return requests
            
            # Only request for actually complex or ambiguous functions
            reason = (
                f"This is a public {component.type.value}. "
                f"Usage examples will help clarify its behavior."
            )
            
            priority = 8 if component.type == ComponentType.FUNCTION else 7
            
            requests.append(InternalRequest(
                request_type="reference",
                component_id=component.id,
                component_name=component.name,
                reason=reason,
                priority=priority
            ))
        
        return requests
    
    def _generate_external_requests(
        self,
        component: CodeComponent,
        project_dag=None
    ) -> List[ExternalRequest]:
        """
        Generate external knowledge requests for a component.
        Only create ExternalRequest if:
        - concept is not in project DAG
        - concept is explicitly referenced by API/annotation/DSL
        - concept affects runtime behavior non-obviously
        """
        requests = []
        
        # Get project DAG from parameter or use empty set as fallback
        dag_ids = set(project_dag) if project_dag else set()

        # Known APIs/annotations/DSLs with non-obvious effects
        NON_OBVIOUS_APIS = {
            "javax.persistence.Entity",
            "javax.persistence.Column",
            "lombok.Data",
            "lombok.Getter",
            "lombok.Setter",
            "spring.transactional",
            "spring.component",
            "spring.service",
            "spring.repository",
            "spring.controller"
        }

        # Check imports, decorators, or other explicit references
        explicit_refs = set(getattr(component, "imports", [])) | set(getattr(component, "decorators", []))

        for concept in explicit_refs:
            # 1. Not in project DAG
            if concept in dag_ids:
                continue
            
            # 2. Check if it's in the whitelist
            if concept not in NON_OBVIOUS_APIS:
                continue

            # If all checks pass, create the request
            requests.append(ExternalRequest(
                request_type="concept",
                query=concept,
                context=f"Referenced in {component.name}",
                priority=6
            ))
        
        return requests
    
    
    def _is_public(self, component: CodeComponent) -> bool:
        """Check if component is public"""
        # In Python, names starting with _ are private
        if component.language == "python":
            return not component.name.startswith('_')
        
        # For other languages, check for public modifiers
        return True
    
    def _calculate_dependency_priority(
        self,
        component: CodeComponent,
        dep_id: str
    ) -> int:
        """
        Calculate priority for a dependency request
        
        Returns:
            Priority score 1-10
        """
        # Base priority
        priority = 5
        
        # Higher priority if component is complex
        if component.complexity and component.complexity > self.complex_complexity_threshold:
            priority += 2
        
        # Higher priority if dependency appears multiple times
        call_count = component.calls.count(dep_id)
        if call_count > 3:
            priority += 2
        elif call_count > 1:
            priority += 1
        
        return min(priority, 10)
    
    def _explain_dependency_need(
        self,
        component: CodeComponent,
        dep_id: str
    ) -> str:
        """Explain why dependency context is needed"""
        dep_name = self._extract_component_name(dep_id)
        
        return (
            f"The component '{component.name}' depends on '{dep_name}' "
            f"to maintain coordinated state. This dependency participates in "
            f"lifecycle transitions or availability guarantees."
        )

    
    def _extract_component_name(self, component_id: str) -> str:
        """Extract component name from ID"""
        # Format: file_path:component_name
        if ':' in component_id:
            return component_id.split(':')[-1]
        return component_id
    
    # def _identify_library(self, import_statement: str) -> Optional[str]:
    #     """Identify library from import statement"""
    #     # Extract library name from import
    #     # e.g., "import numpy as np" -> "numpy"
    #     # e.g., "from sklearn.model_selection import train_test_split" -> "sklearn"
        
    #     patterns = [
    #         r'import\s+(\w+)',
    #         r'from\s+(\w+)',
    #         r'require\(["\'](\w+)["\']\)',
    #     ]
        
    #     for pattern in patterns:
    #         match = re.search(pattern, import_statement)
    #         if match:
    #             return match.group(1)
        
    #     return None
    
    def _load_external_libraries(self) -> List[str]:
        """Load list of external libraries that need explanation"""
        return [
            'numpy', 'pandas', 'matplotlib', 'seaborn', 'scipy',
            'sklearn', 'tensorflow', 'torch', 'keras',
            'requests', 'flask', 'django', 'fastapi',
            'sqlalchemy', 'redis', 'celery',
            'opencv', 'pillow', 'beautifulsoup',
        ]
    
    def _load_known_algorithms(self) -> List[str]:
        """Load list of known algorithms"""
        return [
            'binary search', 'quicksort', 'mergesort', 'heapsort',
            'depth-first search', 'breadth-first search',
            'dijkstra', 'bellman-ford', 'floyd-warshall',
            'kruskal', 'prim', 'knuth-morris-pratt',
            'rabin-karp', 'boyer-moore', 'dynamic programming',
            'greedy', 'backtracking', 'divide and conquer',
        ]
    
    def _create_batch_prompt(self, components: List[CodeComponent]) -> str:
        """
        Create a compact prompt for batch processing multiple components.
        
        Args:
            components: List of CodeComponent objects (typically 5)
            
        Returns:
            Formatted prompt for batch LLM analysis
        """
        prompt = "Analyze these code components and determine if each needs additional context for documentation.\n\n"
        
        for i, comp in enumerate(components, 1):
            complexity = self._get_complexity_level(comp)
            control_flow = comp.metadata.get('control_flow', {})
            
            # Compact component summary
            prompt += f"""=== COMPONENT {i}: {comp.name} ===
Type: {comp.type.value}
Visibility: {"Public" if self._is_public(comp) else "Private"}
Complexity: {complexity}
Lines: {comp.lines_of_code}
Dependencies: {len(comp.depends_on)}
Async: {control_flow.get('is_async', False)}
Has Loops: {control_flow.get('has_loop', False)}
Has Try/Except: {control_flow.get('has_try_except', False)}
Code:
```{comp.language}
{comp.source_code[:250]}{'...' if len(comp.source_code) > 250 else ''}
```

"""
        
        prompt += """For each component, provide:
- YES: if additional context (dependencies, APIs, usage examples) is needed
- NO: if the code is self-explanatory and needs no context

Respond EXACTLY in this format (one line per component):
COMPONENT 1: YES/NO - brief reason
COMPONENT 2: YES/NO - brief reason
COMPONENT 3: YES/NO - brief reason
[continue for all components]

Examples:
COMPONENT 1: YES - Uses recursive algorithm that needs explanation
COMPONENT 2: NO - Simple utility function, self-explanatory
COMPONENT 3: YES - Complex state management with threading patterns"""
        
        return prompt
    
    def _parse_batch_response(self, response: str, components: List[CodeComponent]) -> List[Dict[str, Any]]:
        """
        Parse LLM batch response to extract individual decisions.
        
        Args:
            response: LLM response containing decisions for all components
            components: Original list of components
            
        Returns:
            List of dicts with 'needs_context' (bool) and 'reason' (str)
        """
        decisions = []
        lines = response.strip().split('\n')
        
        # Extract lines that start with "COMPONENT i:"
        component_lines = [l for l in lines if l.strip().startswith('COMPONENT')]
        
        for i, comp in enumerate(components):
            component_num = i + 1
            
            # Find matching line for this component
            matching_lines = [
                l for l in component_lines 
                if l.strip().startswith(f'COMPONENT {component_num}:')
            ]
            
            if matching_lines:
                line = matching_lines[0]
                # Parse "COMPONENT i: YES/NO - reason"
                parts = line.split(':', 1)
                if len(parts) > 1:
                    decision_part = parts[1].strip()
                    
                    # Extract YES/NO and reason
                    if decision_part.upper().startswith('YES'):
                        needs_context = True
                        reason = decision_part[3:].strip(' -').strip()
                    elif decision_part.upper().startswith('NO'):
                        needs_context = False
                        reason = decision_part[2:].strip(' -').strip()
                    else:
                        # Fallback if parsing fails
                        needs_context = True
                        reason = decision_part[:50]
                    
                    decisions.append({
                        'needs_context': needs_context,
                        'reason': reason
                    })
                    continue
            
            # Fallback: if we can't parse, default to safe choice
            self.logger.warning(
                f"Failed to parse decision for component {component_num} ({comp.name}), "
                f"defaulting to needs_context=True"
            )
            decisions.append({
                'needs_context': True,
                'reason': 'Parsing failed, defaulting to gather context'
            })
        
        return decisions
    
    # def _detect_external_concepts(self, component: CodeComponent) -> List[str]:
    #     """
    #     Detect external concepts, APIs, annotations, or DSLs referenced by the component.
    #     Returns a list of concept names/identifiers.
    #     """
    #     concepts = set()

    #     # 1. Add decorators and annotations (often used for non-obvious behavior)
    #     for deco in getattr(component, "decorators", []):
    #         if "." in deco:
    #             concepts.add(deco)
        
    #     # 2. Add explicit imports that look like external APIs or DSLs
    #     for imp in getattr(component, "imports", []):
    #         # Only consider imports with a dot (e.g., 'javax.persistence.Entity')
    #         if "." in imp:
    #             concepts.add(imp)
        
    #     # 3. Optionally, scan source code for known external API patterns
    #     known_patterns = [
    #         r"javax\.persistence\.\w+",
    #         r"lombok\.\w+",
    #         r"spring\.transactional",
    #         r"@Entity",
    #         r"@Data",
    #         r"@Transactional"
    #     ]
    #     for pattern in known_patterns:
    #         matches = re.findall(pattern, component.source_code)
    #         for match in matches:
    #             concepts.add(match.replace("@", ""))
        
    #     return list(concepts)
