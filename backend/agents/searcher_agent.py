"""
Enhanced Searcher Agent with full repository access
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import re
from xml.etree import ElementTree as ET
import networkx as nx

from backend.agents.base_agent import BaseAgent, AgentContext, AgentResult, AgentStatus
from backend.agents.reader_agent import ReaderOutput
from backend.models.code_component import CodeComponent
from backend.utils.logger import get_logger

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
    1. Internal codebase (dependencies and references via Navigator graph)
    2. External sources (via LLM for algorithms/concepts)
    
    Optimized to:
    - Use Navigator's dependency graph directly (with NetworkX reverse)
    - Batch external LLM queries for efficiency
    - Avoid redundant LLM calls for local dependencies
    """
    
    def __init__(self):
        super().__init__("searcher")
        
        # Cache for dependency summaries (avoids repeated LLM calls)
        self.summary_cache: Dict[str, str] = {}
        
        # Repository data (set via set_repository_data)
        self.component_map: Dict[str, CodeComponent] = {}
        self.dependency_graph: Optional[nx.DiGraph] = None
        self.reverse_graph: Optional[nx.DiGraph] = None

    def set_repository_data(
        self,
        all_components: List[CodeComponent],
        dependency_graph: Optional[nx.DiGraph] = None
    ):
        """
        Set full repository data for searching.
        Uses Navigator's graph directly with NetworkX reverse for efficiency.
        
        Args:
            all_components: All components from Navigator
            dependency_graph: Dependency graph from Navigator (nx.DiGraph)
        """
        self.component_map = {comp.id: comp for comp in all_components}
        self.dependency_graph = dependency_graph
        
        # Use NetworkX's efficient reverse() instead of manual building
        if dependency_graph is not None:
            self.reverse_graph = dependency_graph.reverse(copy=False)
            edge_count = dependency_graph.number_of_edges()
        else:
            self.reverse_graph = None
            edge_count = 0
        
        self.logger.info(
            f"Repository data loaded: {len(all_components)} components, "
            f"{edge_count} dependency edges"
        )

    
    def _parse_reader_xml_output(self, xml_output: str) -> Dict[str, Any]:
        """
        Parse Reader's XML output into structured data.
        
        Expected format (from refactored Reader Agent):
        <READER_OUTPUT>
            <INFO_NEED>true/false</INFO_NEED>
            <COMPLEXITY>simple/moderate/complex</COMPLEXITY>
            <REQUEST>
                <INTERNAL>
                    <CALLS>
                        <CLASS>class1,class2</CLASS>
                        <FUNCTION>func1,func2</FUNCTION>
                        <METHOD>method1,method2</METHOD>
                    </CALLS>
                    <CALLED_BY>true/false</CALLED_BY>
                </INTERNAL>
                <EXTERNAL>
                    <QUERY>query1,query2</QUERY>
                </EXTERNAL>
            </REQUEST>
        </READER_OUTPUT>
        """
        try:
            root = ET.fromstring(xml_output)
            
            # Extract INFO_NEED
            info_need_elem = root.find('INFO_NEED')
            needs_context = info_need_elem.text == 'true' if info_need_elem is not None else False
            
            # Extract COMPLEXITY (optional, for downstream use)
            complexity_elem = root.find('COMPLEXITY')
            complexity_level = complexity_elem.text if complexity_elem is not None else 'unknown'
            
            # Extract INTERNAL requests
            internal_elem = root.find('.//INTERNAL')
            internal_requests = []
            search_references = False
            
            if internal_elem is not None:
                # Extract CALLS (what this component calls)
                calls_elem = internal_elem.find('CALLS')
                if calls_elem is not None:
                    for child in calls_elem:
                        if child.text:
                            comp_names = child.text.split(',')
                            for comp_name in comp_names:
                                internal_requests.append({
                                    'type': 'dependency',
                                    'name': comp_name.strip(),
                                    'category': child.tag  # CLASS, FUNCTION, METHOD
                                })
                
                # Extract CALLED_BY (should we find who calls this component?)
                called_by_elem = internal_elem.find('CALLED_BY')
                search_references = called_by_elem.text == 'true' if called_by_elem is not None else False
                if search_references:
                    internal_requests.append({
                        'type': 'reference',
                        'name': 'self',  # Search for references to current component
                        'category': 'CALLED_BY'
                    })
            
            # Extract EXTERNAL queries (novel algorithms only)
            external_elem = root.find('.//EXTERNAL')
            external_requests = []
            
            if external_elem is not None:
                query_elem = external_elem.find('QUERY')
                if query_elem is not None and query_elem.text:
                    queries = query_elem.text.split(',')
                    for query in queries:
                        query = query.strip()
                        if query:
                            external_requests.append({
                                'type': 'novel_concept',
                                'query': query
                            })
            
            return {
                'needs_context': needs_context,
                'complexity_level': complexity_level,
                'internal_requests': internal_requests,
                'external_requests': external_requests,
                'search_references': search_references
            }
        except Exception as e:
            self.logger.error(f"Failed to parse Reader XML output: {e}")
            return {
                'needs_context': False,
                'complexity_level': 'unknown',
                'internal_requests': [],
                'external_requests': [],
                'search_references': False
            }
    
    def _search_dependency_from_dict(self, request_dict: Dict, context: AgentContext) -> Optional[DependencyContext]:
        """Search for dependency using dict request (converted from XML)"""
        # Create InternalRequest-like object from dict
        # FIXED: Use 'name' as both id and name since XML only provides name
        class DictRequest:
            def __init__(self, d):
                # Use name for lookup since XML doesn't provide full component ID
                self.component_name = d.get('name', '')
                self.component_id = d.get('id') or d.get('name', '')  # Fallback to name
                self.request_type = d.get('type')
                self.reason = d.get('reason', '')
                self.priority = d.get('priority', 5)
        
        req = DictRequest(request_dict)
        return self._search_dependency(req, context)
    
    def _search_references_from_dict(self, request_dict: Dict, context: AgentContext) -> Optional[ReferenceContext]:
        """Search for references using dict request (converted from XML)"""
        # Create InternalRequest-like object from dict
        # FIXED: Use 'name' as both id and name since XML only provides name
        class DictRequest:
            def __init__(self, d):
                self.component_name = d.get('name', '')
                self.component_id = d.get('id') or d.get('name', '')  # Fallback to name
                self.request_type = d.get('type')
                self.reason = d.get('reason', '')
                self.priority = d.get('priority', 5)
        
        req = DictRequest(request_dict)
        return self._search_references(req, context)
    
    def _search_external_from_dict(self, request_dict: Dict) -> Optional[ExternalContext]:
        """Search for external context using dict request (converted from XML)"""
        # Create ExternalRequest-like object from dict
        class DictRequest:
            def __init__(self, d):
                self.request_type = d.get('type')
                self.query = d.get('query')
                self.context = d.get('context', '')
                self.priority = d.get('priority', 5)
        
        req = DictRequest(request_dict)
        return self._search_external(req)
    
    def process(self, context: AgentContext) -> AgentResult:
        """
        Process search requests from Reader (supports both XML and legacy ReaderOutput)
        """
        try:
            component = context.component
            reader_result = context.get_result('reader')
            accumulated_context = context.metadata.get('accumulated_context', {})
            
            # Parse reader output (XML string or ReaderOutput object)
            if isinstance(reader_result, str):
                # New XML format
                parsed_data = self._parse_reader_xml_output(reader_result)
                needs_context = parsed_data['needs_context']
                internal_req_data = parsed_data['internal_requests']
                external_req_data = parsed_data['external_requests']
            elif isinstance(reader_result, ReaderOutput):
                # Legacy format
                internal_req_data = [{'type': req.request_type, 'name': req.component_name, 'id': req.component_id} 
                                   for req in reader_result.internal_requests]
                external_req_data = [{'type': req.request_type, 'query': req.query} 
                                   for req in reader_result.external_requests]
            else:
                self.logger.warning("No Reader output found in context")
                return AgentResult(
                    agent_name=self.agent_name,
                    status=AgentStatus.FAILED,
                    output=None,
                    error="No Reader output available"
                )
            
            self.logger.info(
                f"Searching for context: {component.name} - "
                f"{len(internal_req_data)} internal, "
                f"{len(external_req_data)} external requests"
            )
            
            # Skip already-found dependencies
            already_found_ids = {item['id'] for item in accumulated_context.get('internal', []) if 'id' in item}
            already_found_queries = {item['query'] for item in accumulated_context.get('external', []) if 'query' in item}
            
            # Process internal requests
            dependency_contexts = []
            reference_contexts = []
            
            for request in internal_req_data:
                # Skip if already found
                if request.get('id') in already_found_ids:
                    self.logger.debug(f"Skipping already-found dependency: {request.get('id')}")
                    continue
                
                if request.get('type') == "dependency":
                    dep_context = self._search_dependency_from_dict(request, context)
                    if dep_context:
                        dependency_contexts.append(dep_context)
                
                elif request.get('type') == "reference":
                    ref_context = self._search_references_from_dict(request, context)
                    if ref_context:
                        reference_contexts.append(ref_context)
            
            # Process external requests in batch for efficiency
            pending_external = [
                req for req in external_req_data 
                if req.get('query') not in already_found_queries
            ]
            
            if pending_external:
                external_contexts = self._batch_search_external(pending_external)
            else:
                external_contexts = []
            
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
        request,
        context: AgentContext
    ) -> Optional[DependencyContext]:
        """
        Search for dependency information.
        
        Args:
            request: DictRequest object with component_name, request_type attributes
            context: Agent context
            
        Returns:
            DependencyContext or None
        """
        try:
            # Get component name from request (use attribute access for DictRequest objects)
            comp_name = request.component_name if hasattr(request, 'component_name') else request.get('name', '')
            
            # Try to find component by name
            component = self._find_component(comp_name, context)
            
            if not component:
                self.logger.debug(f"Dependency not found: {comp_name}")
                return None
            
            # Use existing docstring or signature instead of LLM call
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
        request,
        context: AgentContext
    ) -> Optional[ReferenceContext]:
        """
        Search for usage references (who calls this component).
        
        Args:
            request: DictRequest object with component_name, request_type attributes
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
        request: Dict[str, Any]
    ) -> Optional[ExternalContext]:
        """
        Search for external knowledge (novel algorithms/concepts).
        
        Args:
            request: Dict with 'type' and 'query' keys
            
        Returns:
            ExternalContext or None
        """
        try:
            query = request.get('query', '')
            req_type = request.get('type', 'novel_concept')
            
            # Generate explanation using LLM
            prompt = self._create_external_search_prompt(query, req_type)
            
            response = self.generate_with_llm(
                prompt=prompt,
                system_prompt="You are a technical knowledge expert. Provide clear, concise explanations for novel algorithms and techniques.",
                temperature=0.5,
                max_tokens=500
            )
            
            # Parse response
            summary, details = self._parse_external_response(response)
            
            return ExternalContext(
                query=query,
                knowledge_type=req_type,
                summary=summary,
                details=details,
                references=[]
            )
            
        except Exception as e:
            self.logger.error(f"Error searching external: {e}")
            return None
    
    def _batch_search_external(
        self,
        requests: List[Dict]
    ) -> List[ExternalContext]:
        """
        Batch search for external knowledge - reduces LLM calls.
        Combines multiple queries into a single prompt when possible.
        
        Args:
            requests: List of external request dicts
            
        Returns:
            List of ExternalContext objects
        """
        if not requests:
            return []
        
        # For single request, use direct method
        if len(requests) == 1:
            result = self._search_external_from_dict(requests[0])
            return [result] if result else []
        
        # Batch multiple requests into one LLM call
        try:
            batch_prompt = self._create_batch_external_prompt(requests)
            
            response = self.generate_with_llm(
                prompt=batch_prompt,
                system_prompt="You are a technical knowledge expert. Provide clear, concise explanations for each query.",
                temperature=0.5,
                max_tokens=2000
            )
            
            # Parse batch response
            return self._parse_batch_external_response(response, requests)
            
        except Exception as e:
            self.logger.warning(f"Batch external search failed: {e}, falling back to individual calls")
            # Fallback to individual calls
            results = []
            for req in requests:
                result = self._search_external_from_dict(req)
                if result:
                    results.append(result)
            return results
    
    def _create_batch_external_prompt(self, requests: List[Dict]) -> str:
        """Create a batch prompt for multiple external queries"""
        queries = []
        for i, req in enumerate(requests, 1):
            query_type = req.get('type', 'concept')
            query = req.get('query', '')
            queries.append(f"{i}. [{query_type.upper()}] {query}")
        
        return f"""Please provide brief explanations for the following technical queries.
For each query, provide:
- A 2-3 sentence summary
- Key details relevant to the context

Format your response as:
[1] Summary: ...
Details: ...

[2] Summary: ...
Details: ...

Queries:
{chr(10).join(queries)}"""
    
    def _parse_batch_external_response(
        self,
        response: str,
        requests: List[Dict]
    ) -> List[ExternalContext]:
        """Parse batch response into individual ExternalContext objects"""
        contexts = []
        
        # Split by numbered sections
        sections = re.split(r'\[(\d+)\]', response)
        
        # Build mapping of index to content
        parsed_sections = {}
        for i in range(1, len(sections), 2):
            if i + 1 < len(sections):
                idx = int(sections[i])
                content = sections[i + 1].strip()
                parsed_sections[idx] = content
        
        # Create ExternalContext for each request
        for i, req in enumerate(requests, 1):
            content = parsed_sections.get(i, "")
            
            # Extract summary and details
            summary = ""
            details = ""
            
            if "Summary:" in content:
                parts = content.split("Details:", 1)
                summary = parts[0].replace("Summary:", "").strip()
                if len(parts) > 1:
                    details = parts[1].strip()
            else:
                # First line is summary
                lines = content.split('\n', 1)
                summary = lines[0].strip()
                details = lines[1].strip() if len(lines) > 1 else ""
            
            contexts.append(ExternalContext(
                query=req.get('query', ''),
                knowledge_type=req.get('type', 'concept'),
                summary=summary,
                details=details,
                references=[]
            ))
        
        return contexts
    
    def _create_external_search_prompt(self, query: str, req_type: str = 'novel_concept') -> str:
        """
        Create prompt for external knowledge search.
        
        Args:
            query: The query/concept to explain
            req_type: Type of request (novel_concept, algorithm, etc.)
            
        Returns:
            Formatted prompt string
        """
        # For novel concepts from Reader Agent
        if req_type == 'novel_concept':
            return f"""Explain this novel/state-of-the-art concept: {query}

Provide:
1. A clear explanation (2-3 sentences)
2. Why this is considered novel or state-of-the-art
3. Key implementation considerations
4. Common use cases or applications"""
        
        prompts = {
            'algorithm': f"""Explain the algorithm: {query}

Provide:
1. A brief explanation (2-3 sentences)
2. Time/space complexity if applicable
3. When it's commonly used
4. Key considerations for implementation""",
            
            'concept': f"""Explain the concept: {query}

Provide:
1. Clear definition (2-3 sentences)
2. Why it's important
3. How it's typically implemented
4. Common patterns or best practices""",
        }
        
        return prompts.get(req_type, prompts['concept'])
    
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
    
    def _find_component(
        self,
        component_id: str,
        context: AgentContext
    ) -> Optional[CodeComponent]:
        """
        Find component by ID or name from component map.
        
        Supports:
        1. Exact match by full ID (e.g., 'main.keyInfo')
        2. Match by component name only (e.g., 'keyInfo')
        3. Match with common module prefixes stripped
        
        Args:
            component_id: Component identifier (full ID or just name)
            context: Agent context (unused but kept for interface compatibility)
            
        Returns:
            CodeComponent if found, None otherwise
        """
        if not component_id:
            return None
        
        # 1. Try exact match first
        if component_id in self.component_map:
            return self.component_map.get(component_id)
        
        # 2. Try matching by name only (component_id might be just the function name)
        for comp_id, comp in self.component_map.items():
            if comp.name == component_id:
                return comp
        
        # 3. Try with common module prefix patterns
        # e.g., 'keyInfo' -> 'main.keyInfo' or 'module.keyInfo'
        for comp_id, comp in self.component_map.items():
            # Extract the name part from full ID (e.g., 'main.keyInfo' -> 'keyInfo')
            if comp_id.endswith('.' + component_id):
                return comp
        
        # 4. Try fuzzy match - component_id might have module prefix we need to strip
        # e.g., 'main._now' -> search for '_now' in all components
        if '.' in component_id:
            name_part = component_id.split('.')[-1]
            for comp_id, comp in self.component_map.items():
                if comp.name == name_part:
                    return comp
        
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
        """Find actual call sites using NetworkX reverse graph"""
        call_sites = []
        
        # Use NetworkX reverse graph for efficient lookup
        if self.reverse_graph is None or component.id not in self.reverse_graph:
            return []
        
        # Get all components that call this one (predecessors in reverse = successors in original)
        calling_components = list(self.reverse_graph.successors(component.id))
        
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
        """Find actual usage examples from codebase using reverse graph"""
        examples = []
        
        if self.reverse_graph is None or component.id not in self.reverse_graph:
            return []
        
        # Get callers from NetworkX reverse graph
        calling_components = list(self.reverse_graph.successors(component.id))
        
        for caller_id in calling_components[:3]:  # Top 3 callers
            caller = self.component_map.get(caller_id)
            if not caller:
                continue
            
            # Extract actual call from source
            for line in caller.source_code.split('\n'):
                if component.name in line and '(' in line:
                    # Extract just the function call
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