"""
Enhanced Searcher Agent with full repository access
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json
from pathlib import Path
import networkx as nx

from backend.agents.base_agent import BaseAgent, AgentContext, AgentResult, AgentStatus
from backend.agents.reader_agent import ReaderOutput, InternalRequest, ExternalRequest
from backend.models.code_component import CodeComponent
from backend.utils.logger import get_logger
from backend.utils.file_handler import FileHandler

logger = get_logger(__name__)

@dataclass
class DependencyContext:
    """Context about a dependency"""
    component_id: str
    component_name: str
    summary: str
    signature: str
    docstring: Optional[str] = None
    usage_pattern: Optional[str] = None
    source_code_snippet: Optional[str] = None

@dataclass
class ReferenceContext:
    """Context about how a component is used"""
    component_id: str
    component_name: str
    usage_examples: List[str] = field(default_factory=list)
    call_sites: List[Dict[str, Any]] = field(default_factory=list)
    usage_summary: str = ""

@dataclass
class ExternalContext:
    """External knowledge context"""
    query: str
    knowledge_type: str
    summary: str
    details: str = ""
    references: List[str] = field(default_factory=list)

@dataclass
class SearcherOutput:
    """Output from Searcher Agent"""
    component_id: str
    dependency_contexts: List[DependencyContext] = field(default_factory=list)
    reference_contexts: List[ReferenceContext] = field(default_factory=list)
    external_contexts: List[ExternalContext] = field(default_factory=list)
    search_summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

class SearcherAgent(BaseAgent):
    """
    Searcher Agent retrieves relevant context from:
    1. Internal codebase (dependencies and references)
    2. Knowledge base (cached information)
    3. External sources (via LLM for algorithms/concepts)
    """
    
    def __init__(self):
        super().__init__("searcher")
    
        self.knowledge_base_path = Path(
            self.config.get('system.paths.knowledge_base', 'data/knowledge_base')
        )
        self.file_handler = FileHandler()
    
        # Load knowledge base
        self.functions_kb = self._load_knowledge_base('functions.json')
        self.classes_kb = self._load_knowledge_base('classes.json')
        self.modules_kb = self._load_knowledge_base('modules.json')
    
        # Cache for component lookup
        self.component_cache = {}
    
        # FIX 3: Add summary cache
        self.summary_cache = {}

    def set_repository_data(
        self,
        all_components: List[CodeComponent],
        dependency_graph: Optional[nx.DiGraph] = None
    ):
        """
        Set full repository data for searching
        
        Args:
            all_components: All components from Navigator
            dependency_graph: Dependency graph from Navigator
        """
        self.all_components = all_components
        self.component_map = {comp.id: comp for comp in all_components}
        self.dependency_graph = dependency_graph
        
        # Build reverse call graph (who calls this component)
        self.reverse_call_graph = {}
        for component in all_components:
            for called_id in component.calls:
                if called_id not in self.reverse_call_graph:
                    self.reverse_call_graph[called_id] = []
                self.reverse_call_graph[called_id].append(component.id)
        
        self.logger.info(
            f"Repository data loaded: {len(all_components)} components, "
            f"{len(self.reverse_call_graph)} call relationships"
        )

    
    def process(self, context: AgentContext) -> AgentResult:
        """
        Process search requests from Reader
        """
        try:
            component = context.component
            reader_output = context.get_result('reader')
            accumulated_context = context.metadata.get('accumulated_context', {})
            
            if not reader_output or not isinstance(reader_output, ReaderOutput):
                self.logger.warning("No Reader output found in context")
                return AgentResult(
                    agent_name=self.agent_name,
                    status=AgentStatus.FAILED,
                    output=None,
                    error="No Reader output available"
                )
            
            self.logger.info(
                f"Searching for context: {component.name} - "
                f"{len(reader_output.internal_requests)} internal, "
                f"{len(reader_output.external_requests)} external requests"
            )
            
            # Skip already-found dependencies
            already_found_ids = {item['id'] for item in accumulated_context.get('internal', [])}
            already_found_queries = {item['query'] for item in accumulated_context.get('external', [])}
            
            # Process internal requests
            dependency_contexts = []
            reference_contexts = []
            
            for request in reader_output.internal_requests:
                # Skip if already found
                if request.component_id in already_found_ids:
                    self.logger.debug(f"Skipping already-found dependency: {request.component_id}")
                    continue
                
                if request.request_type == "dependency":
                    dep_context = self._search_dependency(request, context)
                    if dep_context:
                        dependency_contexts.append(dep_context)
                
                elif request.request_type == "reference":
                    ref_context = self._search_references(request, context)
                    if ref_context:
                        reference_contexts.append(ref_context)
            
            # Process external requests
            external_contexts = []
            for request in reader_output.external_requests:
                # Skip if already found
                if request.query in already_found_queries:
                    self.logger.debug(f"Skipping already-found external: {request.query}")
                    continue
                
                ext_context = self._search_external(request)
                if ext_context:
                    external_contexts.append(ext_context)
            
            # Create search summary
            summary = self._create_search_summary(
                component,
                dependency_contexts,
                reference_contexts,
                external_contexts
            )
            
            output = SearcherOutput(
                component_id=component.id,
                dependency_contexts=dependency_contexts,
                reference_contexts=reference_contexts,
                external_contexts=external_contexts,
                search_summary=summary,
                metadata={
                    'dependencies_found': len(dependency_contexts),
                    'references_found': len(reference_contexts),
                    'external_found': len(external_contexts)
                }
            )
            
            self.logger.info(
                f"Search complete: "
                f"{len(dependency_contexts)} dependencies, "
                f"{len(reference_contexts)} references, "
                f"{len(external_contexts)} external contexts"
            )
            
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.SUCCESS,
                output=output
            )
            
        except Exception as e:
            self.logger.error(f"Searcher agent error: {e}", exc_info=True)
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILED,
                output=None,
                error=str(e)
            )
    
    def _search_dependency(
        self,
        request: InternalRequest,
        context: AgentContext
    ) -> Optional[DependencyContext]:
        """Search for dependency information"""
        try:
            component = self._find_component(request.component_id, context)
            
            if not component:
                self.logger.warning(f"Dependency not found: {request.component_id}")
                return None
            
            # FIX: Use existing docstring or signature instead of LLM call
            # Local dependencies don't need LLM processing
            if component.existing_docstring:
                summary = component.existing_docstring[:200]
            else:
                # Fallback to signature only, no LLM
                summary = f"{component.name}: {component.signature}"
            
            return DependencyContext(
                component_id=component.id,
                component_name=component.name,
                summary=summary,
                signature=component.signature,
                docstring=component.existing_docstring,
                usage_pattern=self._extract_usage_pattern(component)
            )
            
        except Exception as e:
            self.logger.error(f"Error searching dependency: {e}")
            return None
    
    def _search_references(
        self,
        request: InternalRequest,
        context: AgentContext
    ) -> Optional[ReferenceContext]:
        """
        Search for usage references
        
        Args:
            request: Internal reference request
            context: Agent context
            
        Returns:
            ReferenceContext or None
        """
        try:
            component = context.component
            
            # Find where this component is actually called
            usage_examples = self._find_usage_examples(component, context)
            call_sites = self._find_call_sites(component, context)
            
            if not usage_examples and not call_sites:
                self.logger.warning(f"No actual references found for: {component.name}")
                # This is OK - some components may not be called
                return None
            
            # Generate summary from actual usage
            usage_summary = self._generate_usage_summary_from_data(
                component,
                usage_examples,
                call_sites
            )
            
            return ReferenceContext(
                component_id=component.id,
                component_name=component.name,
                usage_examples=usage_examples,
                call_sites=call_sites,
                usage_summary=usage_summary
            )
            
        except Exception as e:
            self.logger.error(f"Error searching references: {e}")
            return None
    
    def _search_external(
        self,
        request: ExternalRequest
    ) -> Optional[ExternalContext]:
        """
        Search for external knowledge
        
        Args:
            request: External knowledge request
            
        Returns:
            ExternalContext or None
        """
        try:
            # Generate explanation using LLM
            prompt = self._create_external_search_prompt(request)
            
            response = self.generate_with_llm(
                prompt=prompt,
                system_prompt="You are a technical knowledge expert. Provide clear, concise explanations.",
                temperature=0.5,
                max_tokens=1000
            )
            
            # Parse response
            summary, details = self._parse_external_response(response)
            
            return ExternalContext(
                query=request.query,
                knowledge_type=request.request_type,
                summary=summary,
                details=details,
                references=[]
            )
            
        except Exception as e:
            self.logger.error(f"Error searching external: {e}")
            return None
    
    def _generate_dependency_summary(self, component: CodeComponent) -> str:
        """Generate summary of a dependency (with caching)"""
        cache_key = f"dep_summary:{component.id}"
        
        # Check cache first
        if cache_key in self.summary_cache:
            self.logger.debug(f"Using cached summary for {component.name}")
            return self.summary_cache[cache_key]
        
        # Use existing docstring if available
        if component.existing_docstring:
            summary = component.existing_docstring[:200]
            self.summary_cache[cache_key] = summary
            return summary
        
        # Only call LLM if no docstring and not cached
        prompt = f"""Provide a brief summary of what this code component does:

Component: {component.name}
Type: {component.type.value}
Signature: {component.signature}

Code:
```{component.language}
{component.source_code[:300]}...
```

Provide a 1-2 sentence summary focusing on its purpose and main functionality."""
        
        try:
            summary = self.generate_with_llm(
                prompt=prompt,
                temperature=0.3,
                max_tokens=200
            )
            summary = summary.strip()
            self.summary_cache[cache_key] = summary
            return summary
        except Exception as e:
            self.logger.warning(f"Failed to generate dependency summary: {e}")
            fallback = f"{component.name}: {component.signature}"
            self.summary_cache[cache_key] = fallback
            return fallback
    
    def _generate_usage_summary(
        self,
        component: CodeComponent,
        usage_examples: List[str],
        call_sites: List[Dict[str, Any]]
    ) -> str:
        """Generate summary of how component is used"""
        prompt = f"""Analyze how this component is used and provide a summary:

Component: {component.name}
Type: {component.type.value}

Usage Examples:
{chr(10).join(f"- {ex[:100]}..." for ex in usage_examples[:3])}

Call Sites Found: {len(call_sites)}

Provide a 2-3 sentence summary explaining:
1. Common usage patterns
2. Typical contexts where it's called
3. What it helps accomplish"""
        
        try:
            summary = self.generate_with_llm(
                prompt=prompt,
                temperature=0.4,
                max_tokens=300
            )
            return summary.strip()
        except Exception as e:
            self.logger.warning(f"Failed to generate usage summary: {e}")
            return f"Used in {len(call_sites)} locations throughout the codebase."
    
    def _create_external_search_prompt(self, request: ExternalRequest) -> str:
        """Create prompt for external knowledge search"""
        prompts = {
            'algorithm': f"""Explain the {request.query} in the context of: {request.context}

Provide:
1. A brief explanation (2-3 sentences)
2. Time/space complexity if applicable
3. When it's commonly used
4. Key considerations for implementation""",
            
            'library': f"""Explain the library/framework: {request.query}

Context: {request.context}

Provide:
1. What the library is for (2 sentences)
2. Key features relevant to this usage
3. Common use cases
4. Basic usage pattern""",
            
            'concept': f"""Explain the concept: {request.query}

Context: {request.context}

Provide:
1. Clear definition (2-3 sentences)
2. Why it's important
3. How it's typically implemented
4. Common patterns or best practices""",
            
            'domain': f"""Explain the domain-specific knowledge: {request.query}

Context: {request.context}

Provide:
1. What it means in this domain (2-3 sentences)
2. Key principles
3. Common applications
4. Important considerations"""
        }
        
        return prompts.get(request.request_type, prompts['concept'])
    
    def _parse_external_response(self, response: str) -> tuple:
        """Parse external knowledge response into summary and details"""
        lines = response.strip().split('\n')
        
        # First paragraph is summary
        summary_lines = []
        detail_lines = []
        
        in_summary = True
        for line in lines:
            if line.strip():
                if in_summary and len(summary_lines) < 3:
                    summary_lines.append(line.strip())
                else:
                    in_summary = False
                    detail_lines.append(line.strip())
        
        summary = ' '.join(summary_lines)
        details = '\n'.join(detail_lines)
        
        return summary, details
    
    def _create_search_summary(
        self,
        component: CodeComponent,
        dependency_contexts: List[DependencyContext],
        reference_contexts: List[ReferenceContext],
        external_contexts: List[ExternalContext]
    ) -> str:
        """Create overall search summary"""
        parts = [f"Search results for {component.name}:"]
        
        if dependency_contexts:
            parts.append(f"Found {len(dependency_contexts)} dependency contexts")
        
        if reference_contexts:
            parts.append(f"Found {len(reference_contexts)} usage references")
        
        if external_contexts:
            parts.append(f"Retrieved {len(external_contexts)} external knowledge contexts")
        
        return ". ".join(parts) + "."
    
    # Helper methods
    
    def _load_knowledge_base(self, filename: str) -> Dict[str, Any]:
        """Load knowledge base file"""
        kb_file = self.knowledge_base_path / filename
        
        if kb_file.exists():
            try:
                return self.file_handler.read_json(kb_file)
            except Exception as e:
                self.logger.warning(f"Failed to load KB {filename}: {e}")
        
        return {}
    
    def _find_component(
        self,
        component_id: str,
        context: AgentContext
    ) -> Optional[CodeComponent]:
        """Find component by ID"""
        # Check cache first
        if component_id in self.component_cache:
            return self.component_cache[component_id]
        
        # Try to find in component map (from repository data)
        if hasattr(self, 'component_map') and component_id in self.component_map:
            component = self.component_map[component_id]
            self.component_cache[component_id] = component
            return component
        
        return None
    
    def _extract_usage_pattern(self, component: CodeComponent) -> str:
        """Extract usage pattern from signature"""
        # Just use the signature directly - it's already good!
        if component.signature:
            return component.signature
        
        # Fallback
        params = ', '.join(p.name for p in (component.parameters or [])[:3])
        if len(component.parameters or []) > 3:
            params += ', ...'
        return f"{component.name}({params})"
    
    def _find_call_sites(
        self,
        component: CodeComponent,
        context: AgentContext
    ) -> List[Dict[str, Any]]:
        """Find actual call sites using reverse call graph"""
        call_sites = []
        
        # Use searcher's reverse_call_graph (built from component.calls)
        if not hasattr(self, 'reverse_call_graph'):
            return []
        
        # Get all components that call this one
        calling_components = self.reverse_call_graph.get(component.id, [])
        
        for caller_id in calling_components:
            caller = self.component_map.get(caller_id)
            if not caller:
                continue
            
            # Find the actual call line in source code
            source = caller.source_code
            call_lines = []
            
            for i, line in enumerate(source.split('\n')):
                if component.name in line and '(' in line:
                    call_lines.append({
                        'line_num': i + 1,
                        'source': line.strip(),
                        'context': f"Called in {caller.name}()"
                    })
            
            if call_lines:
                call_sites.append({
                    'caller_id': caller_id,
                    'caller_name': caller.name,
                    'call_count': len(call_lines),
                    'call_lines': call_lines[:2],  # Top 2 examples
                    'call_context': caller.signature
                })
        
        return call_sites[:5]  # Top 5 call sites
    
    def _find_usage_examples(
        self,
        component: CodeComponent,
        context: AgentContext
    ) -> List[str]:
        """Find actual usage examples from codebase"""
        examples = []
        
        if not hasattr(self, 'reverse_call_graph'):
            return []
        
        # Get callers
        calling_components = self.reverse_call_graph.get(component.id, [])
        
        for caller_id in calling_components[:3]:  # Top 3 callers
            caller = self.component_map.get(caller_id)
            if not caller:
                continue
            
            # Extract actual call from source
            for line in caller.source_code.split('\n'):
                if component.name in line and '(' in line:
                    # Extract just the function call
                    import re
                    match = re.search(rf'{re.escape(component.name)}\([^)]*\)', line)
                    if match:
                        examples.append(match.group(0))
        
        # If no real examples found, generate synthetic one
        if not examples:
            params = ', '.join(f'arg{i}' for i in range(len(component.parameters or [])))
            examples.append(f"{component.name}({params})")
        
        return examples[:3]
    
    def _generate_usage_summary_from_data(
        self,
        component: CodeComponent,
        usage_examples: List[str],
        call_sites: List[Dict[str, Any]]
    ) -> str:
        """Generate usage summary from actual codebase data"""
        if not usage_examples and not call_sites:
            return f"No usage information found for {component.name}"
        
        summary = f"{component.name} is called {len(call_sites)} times in the codebase"
        
        if call_sites:
            callers = [cs['caller_name'] for cs in call_sites]
            summary += f" by: {', '.join(callers[:3])}"
            if len(callers) > 3:
                summary += f" and {len(callers) - 3} other components"
        
        return summary + "."