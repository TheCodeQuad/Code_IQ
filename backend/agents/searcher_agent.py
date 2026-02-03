"""
Enhanced Searcher Agent with full repository access
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import re
from xml.etree import ElementTree as ET
import networkx as nx
import json
import os
from datetime import datetime
from pathlib import Path

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
        
        # Consolidated outputs storage
        self.consolidated_outputs: List[Dict[str, Any]] = []
        self.output_dir = Path("data/intermediate/agent_output/searcher")
        self.output_dir.mkdir(parents=True, exist_ok=True)

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
    
    def process(self, context: AgentContext) -> AgentResult:
        """
        Main processing: Fetch evidence based on Reader's request.
        
        Args:
            context: Contains focal component and Reader's output
            
        Returns:
            AgentResult with structured evidence dictionary
        """
        try:
            focal_component = context.component
            logger.info(f"Processing search for component: {focal_component.id}")
            
            # Parse Reader's request
            reader_output = context.get_result('reader')
            reader_request = self._parse_reader_request(reader_output, context)
            
            if not reader_request:
                logger.warning("No valid reader request found, returning empty results")
                return self._create_empty_result()
            
            # Check for accumulated context to avoid duplicates
            accumulated = context.metadata.get('accumulated_context', {})
            
            # Initialize output structure
            output = {
                'internal': {
                    'calls': {
                        'class': {},
                        'function': {},
                        'method': {}
                    },
                    'called_by': []
                },
                'external': {}
            }
            
            # Step 1: Get dependencies of focal component
            dependencies = self._get_dependencies(focal_component.id)
            logger.debug(f"Found {len(dependencies)} dependencies for {focal_component.id}")
            
            # Step 2: Build lookup map (name -> component) scoped to dependencies
            dep_lookup = self._build_dependency_lookup(dependencies)
            
            # Step 3: Fetch internal calls (class, function, method)
            internal_requests = reader_request.get('internal', {})
            calls = internal_requests.get('calls', {})
            
            # Fetch classes
            for class_name in calls.get('CLASS', []):
                if class_name and class_name not in output['internal']['calls']['class']:
                    source = self._fetch_component_source(class_name, 'class', dep_lookup)
                    if source:
                        output['internal']['calls']['class'][class_name] = source
                        logger.debug(f"Fetched class: {class_name}")
            
            # Fetch functions
            for func_name in calls.get('FUNCTION', []):
                if func_name and func_name not in output['internal']['calls']['function']:
                    source = self._fetch_component_source(func_name, 'function', dep_lookup)
                    if source:
                        output['internal']['calls']['function'][func_name] = source
                        logger.debug(f"Fetched function: {func_name}")
            
            # Fetch methods
            for method_name in calls.get('METHOD', []):
                if method_name and method_name not in output['internal']['calls']['method']:
                    source = self._fetch_component_source(method_name, 'method', dep_lookup)
                    if source:
                        output['internal']['calls']['method'][method_name] = source
                        logger.debug(f"Fetched method: {method_name}")
            
            # Step 4: Fetch reverse dependencies (who calls this component)
            if internal_requests.get('called_by', False):
                callers = self._get_callers(focal_component.id)
                for caller_id in callers:
                    caller_source = self._fetch_caller_source(caller_id)
                    if caller_source:
                        output['internal']['called_by'].append(caller_source)
                logger.debug(f"Fetched {len(output['internal']['called_by'])} callers")
            
            # Step 5: Fetch external queries
            external_requests = reader_request.get('external', {})
            queries = external_requests.get('queries', [])
            
            for query in queries:
                if query and query.strip():
                    # Check if already fetched in accumulated context
                    already_fetched = False
                    for ext_ctx in accumulated.get('external', []):
                        if ext_ctx.get('query') == query:
                            already_fetched = True
                            output['external'][query] = ext_ctx.get('response', '')
                            break
                    
                    if not already_fetched:
                        response = self._fetch_external_query(query)
                        output['external'][query] = response
                        logger.debug(f"Fetched external query: {query}")
            
            # Log summary
            total_internal = (len(output['internal']['calls']['class']) + 
                            len(output['internal']['calls']['function']) + 
                            len(output['internal']['calls']['method']) + 
                            len(output['internal']['called_by']))
            total_external = len(output['external'])
            logger.info(f"Search complete: {total_internal} internal, {total_external} external")
            
            # Save individual output to file
            self._save_output_to_file(focal_component.id, output)
            
            # Add to consolidated outputs
            self.consolidated_outputs.append({
                'component_id': focal_component.id,
                'processed_at': datetime.now().isoformat(),
                'output': output
            })
            
            # Convert dict output to SearcherOutput object for orchestrator compatibility
            dependency_contexts = []
            for comp_type in ['class', 'function', 'method']:
                for name, source in output['internal']['calls'][comp_type].items():
                    dependency_contexts.append(DependencyContext(
                        component_id=name,
                        component_name=name,
                        summary=source[:200] if source else "",
                        signature=name,
                        docstring=None,
                        usage_pattern=None,
                        source_code_snippet=source
                    ))
            
            reference_contexts = []
            for caller_source in output['internal']['called_by']:
                reference_contexts.append(ReferenceContext(
                    component_id="caller",
                    component_name="caller",
                    usage_examples=[caller_source[:200] if caller_source else ""],
                    call_sites=[],
                    usage_summary=""
                ))
            
            external_contexts = []
            for query, response in output['external'].items():
                external_contexts.append(ExternalContext(
                    query=query,
                    knowledge_type='novel_concept',
                    summary=response[:200] if response else "",
                    details=response if response else "",
                    references=[]
                ))
            
            searcher_output = SearcherOutput(
                component_id=focal_component.id,
                dependency_contexts=dependency_contexts,
                reference_contexts=reference_contexts,
                external_contexts=external_contexts,
                search_summary=f"Found {len(dependency_contexts)} dependencies, {len(reference_contexts)} references, {len(external_contexts)} external",
                metadata={
                    'raw_output': output,
                    'focal_component_id': focal_component.id,
                    'dependencies_count': len(dependencies),
                    'internal_results': total_internal,
                    'external_results': total_external
                }
            )
            
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.SUCCESS,
                output=searcher_output,
                metadata={
                    'focal_component_id': focal_component.id,
                    'dependencies_count': len(dependencies),
                    'internal_results': total_internal,
                    'external_results': total_external
                }
            )
            
        except Exception as e:
            logger.error(f"Error in SearcherAgent: {e}", exc_info=True)
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILURE,
                error=str(e),
                output=SearcherOutput(
                    component_id=focal_component.id if focal_component else "unknown",
                    dependency_contexts=[],
                    reference_contexts=[],
                    external_contexts=[],
                    search_summary="Search failed",
                    metadata={'error': str(e)}
                )
            )
    
    def _parse_reader_request(self, reader_output: Any, context: AgentContext) -> Optional[Dict[str, Any]]:
        """
        Parse Reader's output into a structured request.
        Supports both XML string and ReaderOutput object.
        """
        # Try XML format first
        if isinstance(reader_output, str):
            return self._parse_reader_xml(reader_output)
        
        # Try ReaderOutput object format
        if hasattr(reader_output, 'internal_requests') and hasattr(reader_output, 'external_requests'):
            return self._parse_reader_output_object(reader_output)
        
        logger.error(f"Unknown reader output format: {type(reader_output)}")
        return None
    
    def _parse_reader_xml(self, xml_string: str) -> Optional[Dict[str, Any]]:
        """
        Parse Reader's XML output into structured request.
        
        Expected XML:
        <READER_OUTPUT>
            <REQUEST>
                <INTERNAL>
                    <CALLS>
                        <CLASS>ClassName1,ClassName2</CLASS>
                        <FUNCTION>func1,func2</FUNCTION>
                        <METHOD>method1,method2</METHOD>
                    </CALLS>
                    <CALLED_BY>true</CALLED_BY>
                </INTERNAL>
                <EXTERNAL>
                    <QUERY>query1,query2</QUERY>
                </EXTERNAL>
            </REQUEST>
        </READER_OUTPUT>
        """
        try:
            from xml.etree import ElementTree as ET
            
            root = ET.fromstring(xml_string)
            request = root.find('.//REQUEST')
            
            if request is None:
                logger.warning("No REQUEST element in XML")
                return None
            
            result = {
                'internal': {
                    'calls': {
                        'CLASS': [],
                        'FUNCTION': [],
                        'METHOD': []
                    },
                    'called_by': False
                },
                'external': {
                    'queries': []
                }
            }
            
            # Parse INTERNAL
            internal = request.find('INTERNAL')
            if internal is not None:
                calls = internal.find('CALLS')
                if calls is not None:
                    # Parse CLASS
                    class_elem = calls.find('CLASS')
                    if class_elem is not None and class_elem.text:
                        result['internal']['calls']['CLASS'] = [
                            c.strip() for c in class_elem.text.split(',') if c.strip()
                        ]
                    
                    # Parse FUNCTION
                    func_elem = calls.find('FUNCTION')
                    if func_elem is not None and func_elem.text:
                        result['internal']['calls']['FUNCTION'] = [
                            f.strip() for f in func_elem.text.split(',') if f.strip()
                        ]
                    
                    # Parse METHOD
                    method_elem = calls.find('METHOD')
                    if method_elem is not None and method_elem.text:
                        result['internal']['calls']['METHOD'] = [
                            m.strip() for m in method_elem.text.split(',') if m.strip()
                        ]
                
                # Parse CALLED_BY
                called_by_elem = internal.find('CALLED_BY')
                if called_by_elem is not None and called_by_elem.text:
                    result['internal']['called_by'] = called_by_elem.text.strip().lower() == 'true'
            
            # Parse EXTERNAL
            external = request.find('EXTERNAL')
            if external is not None:
                query_elem = external.find('QUERY')
                if query_elem is not None and query_elem.text:
                    result['external']['queries'] = [
                        q.strip() for q in query_elem.text.split(',') if q.strip()
                    ]
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing Reader XML: {e}", exc_info=True)
            return None
    
    def _parse_reader_output_object(self, reader_output) -> Dict[str, Any]:
        """
        Parse ReaderOutput object into structured request.
        """
        result = {
            'internal': {
                'calls': {
                    'CLASS': [],
                    'FUNCTION': [],
                    'METHOD': []
                },
                'called_by': False
            },
            'external': {
                'queries': []
            }
        }
        
        # Parse internal requests
        for req in getattr(reader_output, 'internal_requests', []):
            comp_name = getattr(req, 'component_name', '')
            req_type = getattr(req, 'request_type', '')
            
            if req_type == 'dependency':
                # Try to determine if class/function/method
                # Default to FUNCTION if unknown
                result['internal']['calls']['FUNCTION'].append(comp_name)
            elif req_type == 'reference':
                result['internal']['called_by'] = True
        
        # Parse external requests
        for req in getattr(reader_output, 'external_requests', []):
            query = getattr(req, 'query', '')
            if query:
                result['external']['queries'].append(query)
        
        return result
    
    def _get_dependencies(self, component_id: str) -> List[str]:
        """
        Get list of component IDs that focal component depends on.
        """
        if not self.dependency_graph:
            logger.warning("No dependency graph available")
            return []
        
        try:
            # Get successors (nodes that component_id points to)
            deps = list(self.dependency_graph.successors(component_id))
            return deps
        except nx.NetworkXError:
            logger.warning(f"Component {component_id} not in dependency graph")
            return []
    
    def _get_callers(self, component_id: str) -> List[str]:
        """
        Get list of component IDs that call the focal component.
        """
        if not self.reverse_graph:
            logger.warning("No reverse graph available")
            return []
        
        try:
            # Get successors in reverse graph (nodes that point to component_id)
            callers = list(self.reverse_graph.successors(component_id))
            return callers
        except nx.NetworkXError:
            logger.warning(f"Component {component_id} not in reverse graph")
            return []
    
    def _build_dependency_lookup(self, dependency_ids: List[str]) -> Dict[str, CodeComponent]:
        """
        Build name -> component lookup scoped to dependencies only.
        Supports lookup by: full ID, short name, and last segment of ID.
        
        Args:
            dependency_ids: List of component IDs that are dependencies
            
        Returns:
            Dictionary mapping component names to CodeComponent objects
        """
        lookup = {}
        
        for dep_id in dependency_ids:
            comp = self.component_map.get(dep_id)
            if comp:
                # Map by full component ID (e.g., "src.component.Display.Display")
                lookup[dep_id] = comp
                
                # Map by component name (e.g., "Display")
                lookup[comp.name] = comp
                
                # Map by last segment of ID (e.g., "Display" from "src.component.Display.Display")
                last_segment = dep_id.split(".")[-1]
                if last_segment not in lookup:  # Don't override if already exists
                    lookup[last_segment] = comp
                    
                logger.debug(f"Mapped dependency: {dep_id} -> {comp.name} (type: {comp.type})")
        
        logger.debug(f"Built lookup with {len(lookup)} mappings for {len(dependency_ids)} dependencies")
        return lookup
    
    def _fetch_component_source(
        self,
        name: str,
        comp_type: str,
        dep_lookup: Dict[str, CodeComponent]
    ) -> Optional[str]:
        """
        Fetch source code for a component by name and type.
        Tries multiple lookup strategies and flexible type matching.
        
        Args:
            name: Component name to search for (can be full ID or short name)
            comp_type: Expected type ('class', 'function', 'method')
            dep_lookup: Name -> component lookup (scoped to dependencies)
            
        Returns:
            Source code string or None if not found
        """
        # Try direct lookup first
        comp = dep_lookup.get(name)
        
        if not comp:
            logger.debug(f"Component '{name}' not found in dependency lookup (tried {len(dep_lookup)} entries)")
            return None
        
        # Normalize type for comparison (convert ComponentType enum to string)
        comp_type_str = str(comp.type).lower() if hasattr(comp.type, 'value') else str(comp.type).lower()
        expected_type_str = comp_type.lower()
        
        # Remove 'componenttype.' prefix if present
        if 'componenttype.' in comp_type_str:
            comp_type_str = comp_type_str.split('.')[-1]
        
        # Type check with flexible matching
        if comp_type_str != expected_type_str:
            # Allow 'class' to match React components that might be marked as 'method'
            # This handles Reader misclassification issues
            logger.warning(
                f"Component '{name}' type mismatch: expected {expected_type_str}, got {comp_type_str}. "
                f"Returning source anyway to handle Reader misclassification."
            )
            # Still return the source - let the writer decide what to do with it
        
        logger.debug(f"Found component '{name}' with type {comp_type_str}")
        # Return source code (or empty string if None)
        return comp.source_code or ""
    
    def _fetch_caller_source(self, caller_id: str) -> Optional[str]:
        """
        Fetch source code for a caller component.
        
        Args:
            caller_id: Component ID that calls the focal component
            
        Returns:
            Source code string or None if not found
        """
        comp = self.component_map.get(caller_id)
        
        if not comp:
            logger.debug(f"Caller component '{caller_id}' not found")
            return None
        
        return comp.source_code or ""
    
    def _fetch_external_query(self, query: str) -> str:
        """
        Fetch response for external query using LLM.
        
        Args:
            query: Search query string (e.g., "Dijkstra algorithm")
            
        Returns:
            LLM-generated explanation or error message
        """
        try:
            logger.debug(f"Fetching external query: {query}")
            
            # Create prompt for LLM
            prompt = f"""Explain the following concept/algorithm in a clear, concise way suitable for code documentation:

{query}

Provide:
1. A brief definition (1-2 sentences)
2. Key characteristics or how it works (2-3 sentences)
3. When/why it's used (1 sentence)

Keep the explanation technical but accessible."""

            # Use BaseAgent's LLM generation
            response = self.generate_with_llm(
                prompt=prompt,
                system_prompt="You are a technical knowledge expert. Provide clear, concise explanations for algorithms and technical concepts.",
                temperature=0.5,
                max_tokens=500
            )
            
            return response or "[No response received]"
            
        except Exception as e:
            error_msg = f"[API Error: {str(e)}]"
            logger.error(f"External query failed for '{query}': {e}")
            return error_msg
    
    def _create_empty_result(self) -> AgentResult:
        """Create AgentResult with empty SearcherOutput."""
        return AgentResult(
            agent_name=self.agent_name,
            status=AgentStatus.SUCCESS,
            output=SearcherOutput(
                component_id="unknown",
                dependency_contexts=[],
                reference_contexts=[],
                external_contexts=[],
                search_summary="No search performed",
                metadata={}
            ),
            metadata={}
        )
    
    def _create_empty_output(self) -> Dict[str, Any]:
        """Create empty output structure."""
        return {
            'internal': {
                'calls': {
                    'class': {},
                    'function': {},
                    'method': {}
                },
                'called_by': []
            },
            'external': {}
        }
    
    def _save_output_to_file(self, component_id: str, output: Dict[str, Any]) -> None:
        """
        Save searcher output to JSON file.
        
        Args:
            component_id: ID of the focal component
            output: The output dictionary to save
        """
        try:
            # Create output directory
            output_dir = Path("data/intermediate/agent_output/searcher")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Create safe filename from component_id
            safe_name = component_id.replace(".", "_").replace("/", "_").replace("\\", "_")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_name}_{timestamp}.json"
            
            filepath = output_dir / filename
            
            # Prepare output with metadata
            output_with_meta = {
                "component_id": component_id,
                "timestamp": datetime.now().isoformat(),
                "searcher_output": output
            }
            
            # Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(output_with_meta, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Searcher output saved to: {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save searcher output: {e}")
    
    def save_consolidated_output(self, filename: str = "consolidated_searcher_output.json") -> Optional[Path]:
        """
        Save all collected outputs to a single consolidated JSON file.
        
        Args:
            filename: Name of the consolidated output file
            
        Returns:
            Path to the consolidated output file, or None if failed
        """
        try:
            if not self.consolidated_outputs:
                logger.warning("No consolidated outputs to save")
                return None
            
            output_file = self.output_dir / filename
            
            consolidated_data = {
                "timestamp": datetime.now().isoformat(),
                "total_components": len(self.consolidated_outputs),
                "components": self.consolidated_outputs
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(consolidated_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Consolidated searcher output saved to: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to save consolidated output: {e}")
            return None
    
    def clear_consolidated_outputs(self) -> None:
        """Clear the consolidated outputs list."""
        self.consolidated_outputs = []
        logger.debug("Consolidated outputs cleared")
