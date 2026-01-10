"""
Reader Agent
Analyzes code components and determines information needs
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import ast
import re

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
    
    def process(self, context: AgentContext) -> AgentResult:
        """
        Process component and determine information needs
        """
        try:
            component = context.component
            
            self.logger.info(f"Analyzing component: {component.name}")
            
            # Step 1: Analyze complexity
            complexity = self._analyze_complexity(component)
            
            component.creates_threads = self._detect_threading(component)

            # Step 2: Assess if additional context is needed
            needs_context = self._needs_additional_context(component, complexity)
            
            # Step 3: Generate internal requests
            internal_requests = []
            if needs_context:
                internal_requests = self._generate_internal_requests(component)
            
            # Step 4: Get project_dag from metadata and generate external requests
            project_dag = context.metadata.get('project_dag')
            external_requests = self._generate_external_requests(component, project_dag)
            
            # Step 5: Create analysis summary
            summary = self._create_analysis_summary(
                component,
                complexity,
                needs_context,
                internal_requests,
                external_requests
            )
            
            output = ReaderOutput(
                component_id=component.id,
                complexity_assessment=complexity,
                needs_additional_context=needs_context,
                internal_requests=internal_requests,
                external_requests=external_requests,
                analysis_summary=summary,
                metadata={
                    'component_type': component.type,
                    'is_public': self._is_public(component),
                    'has_docstring': bool(component.existing_docstring)
                }
            )
            
            self.logger.info(
                f"Reader analysis complete: "
                f"Needs context: {needs_context}, "
                f"Internal requests: {len(internal_requests)}, "
                f"External requests: {len(external_requests)}"
            )
            
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.SUCCESS,
                output=output
            )
            
        except Exception as e:
            self.logger.error(f"Reader agent error: {e}", exc_info=True)
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILED,
                output=None,
                error=str(e)
            )
    
    def _analyze_complexity(self, component: CodeComponent) -> Dict[str, Any]:
        """
        Analyze component complexity
        
        Returns:
            Dictionary with complexity metrics
        """
        complexity = {
            'cyclomatic_complexity': component.complexity or 1,
            'lines_of_code': component.lines_of_code,
            'num_parameters': len(component.parameters),
            'num_dependencies': len(component.depends_on),
            'num_calls': len(component.calls),
            'is_async': component.is_async,
            'is_generator': component.is_generator,
            'has_decorators': len(component.decorators) > 0,
            'complexity_level': 'moderate'
        }
        
        # Calculate overall complexity score
        score = 0
        score += complexity['cyclomatic_complexity']
        score += min(complexity['num_parameters'], 5)  # Cap at 5
        score += min(complexity['num_dependencies'], 5)
        score += complexity['lines_of_code'] // 10  # 1 point per 10 lines
        
        if complexity['is_async'] or complexity['is_generator']:
            score += 3
        
        complexity['complexity_score'] = score
        
        # Categorize complexity
        if score <= self.simple_complexity_threshold:
            complexity['complexity_level'] = 'simple'
        elif score <= self.complex_complexity_threshold:
            complexity['complexity_level'] = 'moderate'
        else:
            complexity['complexity_level'] = 'complex'
        
        return complexity
    
    def _needs_additional_context(
        self,
        component: CodeComponent,
        complexity: Dict[str, Any]
    ) -> bool:
        """Determine if component needs additional context"""
        
        # Skip global variables entirely - they don't need context
        if component.type == ComponentType.GLOBAL_VARIABLE:
            return False
        
        # NEW RULE: Always need context for async, threading, error handling
        # BUT NOT just for accessing shared state
        if (
            component.is_async
            or self._detect_threading(component)
            or self._detect_error_handling(component)
        ):
            return True
        
        # Simple self-contained components don't need context
        if complexity['complexity_level'] == 'simple':
            # Only return True if the component is public AND has dependencies or calls
            if self._is_public(component) and component.type.value in ['function', 'method']:
                if len(component.depends_on) > 0 or len(component.calls) > 0:
                    return True
                else:
                    return False

            # Otherwise, simple components don't need context
            return False
        
        # Only complex components truly need context
        if complexity['complexity_level'] != 'complex':
            # Moderate components: only if they have external dependencies or many internal dependencies
            if len(component.depends_on) > 5:
                return True
            
            # Check for external libraries (pandas, numpy, requests, etc.)
            if self._has_external_dependencies(component):
                return True
            
            return False
        
        # Complex components always need context
        return True
    
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

        for concept in self._detect_external_concepts(component):
            # 1. Not in project DAG
            if concept in dag_ids:
                continue
            
            # 2. Explicitly referenced (already filtered by _detect_external_concepts)
            if not any(concept in ref for ref in explicit_refs):
                continue
            
            # 3. Non-obvious runtime effect (check if in whitelist)
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
    
    def _create_analysis_summary(
        self,
        component: CodeComponent,
        complexity: Dict[str, Any],
        needs_context: bool,
        internal_requests: List[InternalRequest],
        external_requests: List[ExternalRequest]
    ) -> str:
        """
        Create a summary of the analysis using LLM
        
        Args:
            component: Code component
            complexity: Complexity assessment
            needs_context: Whether additional context is needed
            internal_requests: List of internal requests
            external_requests: List of external requests
            
        Returns:
            Analysis summary
        """
        prompt = f"""Analyze this code component and provide a brief summary:

Component: {component.name}
Type: {component.type.value}
Visibility: {"Public" if self._is_public(component) else "Private"}

Complexity Assessment:
- Cyclomatic Complexity: {complexity['cyclomatic_complexity']}
- Lines of Code: {complexity['lines_of_code']}
- Number of Parameters: {complexity['num_parameters']}
- Number of Dependencies: {complexity['num_dependencies']}
- Complexity Level: {complexity['complexity_level']}

Code:
```{component.language}
{component.source_code[:500]}{'...' if len(component.source_code) > 500 else ''}
```

Information Needs:
- Needs Additional Context: {needs_context}
- Internal Requests: {len(internal_requests)} (dependencies: {sum(1 for r in internal_requests if r.request_type == 'dependency')}, references: {sum(1 for r in internal_requests if r.request_type == 'reference')})
- External Requests: {len(external_requests)}

Provide a 2-3 sentence analysis summary explaining:
1. What this component does
2. Its complexity level and why
3. What information would be most helpful for documenting it
"""
        
        system_prompt = """You are a code analysis expert. Provide concise, technical analysis summaries."""
        
        try:
            summary = self.generate_with_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=300
            )
            return summary.strip()
        except Exception as e:
            self.logger.warning(f"Failed to generate LLM summary: {e}")
            return f"Analysis of {component.name}: {complexity['complexity_level']} complexity, {len(internal_requests)} internal and {len(external_requests)} external information needs identified."
    
    # Helper methods
    
    def _is_public(self, component: CodeComponent) -> bool:
        """Check if component is public"""
        # In Python, names starting with _ are private
        if component.language == "python":
            return not component.name.startswith('_')
        
        # For other languages, check for public modifiers
        return True
    
    def _has_external_dependencies(self, component: CodeComponent) -> bool:
        """Check if component has external dependencies"""
        external_patterns = [
            'import ',
            'from ',
            'require(',
            'include ',
        ]
        
        for pattern in external_patterns:
            if pattern in component.source_code:
                return True
        
        return False
    
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
            f"The component '{component.name}' depends on '{dep_name}'. "
            f"Understanding this dependency will help document how {component.name} works."
        )
    
    def _extract_component_name(self, component_id: str) -> str:
        """Extract component name from ID"""
        # Format: file_path:component_name
        if ':' in component_id:
            return component_id.split(':')[-1]
        return component_id
    
    def _identify_library(self, import_statement: str) -> Optional[str]:
        """Identify library from import statement"""
        # Extract library name from import
        # e.g., "import numpy as np" -> "numpy"
        # e.g., "from sklearn.model_selection import train_test_split" -> "sklearn"
        
        patterns = [
            r'import\s+(\w+)',
            r'from\s+(\w+)',
            r'require\(["\'](\w+)["\']\)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, import_statement)
            if match:
                return match.group(1)
        
        return None
    
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
    
    def _detect_external_concepts(self, component: CodeComponent) -> List[str]:
        """
        Detect external concepts, APIs, annotations, or DSLs referenced by the component.
        Returns a list of concept names/identifiers.
        """
        concepts = set()

        # 1. Add decorators and annotations (often used for non-obvious behavior)
        for deco in getattr(component, "decorators", []):
            if "." in deco:
                concepts.add(deco)
        
        # 2. Add explicit imports that look like external APIs or DSLs
        for imp in getattr(component, "imports", []):
            # Only consider imports with a dot (e.g., 'javax.persistence.Entity')
            if "." in imp:
                concepts.add(imp)
        
        # 3. Optionally, scan source code for known external API patterns
        known_patterns = [
            r"javax\.persistence\.\w+",
            r"lombok\.\w+",
            r"spring\.transactional",
            r"@Entity",
            r"@Data",
            r"@Transactional"
        ]
        for pattern in known_patterns:
            matches = re.findall(pattern, component.source_code)
            for match in matches:
                concepts.add(match.replace("@", ""))
        
        return list(concepts)
    
    def _detect_threading(self, component: CodeComponent) -> bool:
        """Detect if component creates threads or uses concurrency"""
        threading_patterns = [
            'new Thread(',
            'threading.Thread(',
            '.start()',
            'executor',
            'ExecutorService',
            'async def',
            'await ',
            '.wait()',
            '.notify(',
            'Lock(',
            'Semaphore(',
            'synchronized',
        ]
        
        source = component.source_code.lower()
        return any(pattern.lower() in source for pattern in threading_patterns)

    def _detect_error_handling(self, component: CodeComponent) -> bool:
        """Detect if component has error handling logic"""
        error_patterns = ['try', 'except', 'finally', 'throw', 'catch']
        source = component.source_code.lower()
        return any(pattern in source for pattern in error_patterns)

    # def _detect_shared_state(self, component: CodeComponent) -> bool:
    #     """Detect if component manages shared state"""
    #     state_patterns = ['global', 'static', 'class variable', '__shared']
    #     source = component.source_code.lower()
    #     return any(pattern in source for pattern in state_patterns)