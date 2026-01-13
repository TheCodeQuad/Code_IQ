"""
Main pipeline orchestrator
"""

from typing import List,Dict
from backend.navigator.core.dag_export import PROJECT_ROOT
from backend.navigator.core.repository_parser import RepositoryParser
from backend.navigator.core.topo import (
    build_graph_from_components,
    topological_sort,
    dependency_first_dfs,
    resolve_cycles
)
from backend.agents.orchestrator.orchestrator import Orchestrator
from backend.models.code_component import CodeComponent, ComponentType
from backend.utils.file_handler import FileHandler
from backend.utils.logger import get_logger
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
logger = get_logger(__name__)

def run_pipeline(repo_path: str):
    """
    Run the documentation pipeline for a given repository path.
    Returns a dict with components, graph, orders, and documentation.
    """
    logger.info(f"Starting pipeline for repository: {repo_path}")
    
    # Stage 1: Parse repository and extract components
    logger.info("Stage 1: Parsing repository and extracting components...")
    parser = RepositoryParser(repo_path)
    components = parser.parse()  # {id: CodeComponent}
    # Extract module globals and inject into component metadata
    _extract_module_globals(components)
    logger.info(f"Populated module_globals metadata for components")
    logger.info(f"Extracted {len(components)} components")

    # Convert all components to standard CodeComponent if needed
    for cid, nav_comp in components.items():
        if not hasattr(nav_comp, "name"):
            comp_type = nav_comp.type
            if not isinstance(comp_type, ComponentType):
                comp_type = ComponentType(comp_type)
            components[cid] = CodeComponent(
                id=getattr(nav_comp, 'id', cid),
                name=getattr(nav_comp, 'name', getattr(nav_comp, 'id', cid)),
                type=comp_type,
                location=getattr(nav_comp, 'location', None),
                source_code=getattr(nav_comp, 'source_code', ''),
                signature=getattr(nav_comp, 'signature', ''),
                parameters=getattr(nav_comp, 'parameters', []),
                return_type=getattr(nav_comp, 'return_type', None),
                decorators=getattr(nav_comp, 'decorators', []),
                parent_classes=getattr(nav_comp, 'parent_classes', []),
                methods=getattr(nav_comp, 'methods', []),
                attributes=getattr(nav_comp, 'attributes', []),
                existing_docstring=getattr(nav_comp, 'existing_docstring', None),
                calls=getattr(nav_comp, 'calls', []),
                imports=getattr(nav_comp, 'imports', []),
                depends_on=getattr(nav_comp, 'depends_on', []),
                complexity=getattr(nav_comp, 'complexity', None),
                lines_of_code=getattr(nav_comp, 'lines_of_code', 0),
                language=getattr(nav_comp, 'language', 'python'),
                is_async=getattr(nav_comp, 'is_async', False),
                is_generator=getattr(nav_comp, 'is_generator', False),
                is_abstract=getattr(nav_comp, 'is_abstract', False),
                is_static=getattr(nav_comp, 'is_static', False),
                is_class_method=getattr(nav_comp, 'is_class_method', False),
                priority=getattr(nav_comp, 'priority', 0),
                dependency_level=getattr(nav_comp, 'dependency_level', 0),
                metadata=getattr(nav_comp, 'metadata', {}),
            )

    # Stage 2: Build dependency graph and orders
    logger.info("Stage 2: Building dependency graph...")
    graph = build_graph_from_components(components)
    graph = resolve_cycles(graph)
    topo_order = topological_sort(graph)
    dfs_order = dependency_first_dfs(graph)
    
    logger.info(f"Built dependency graph with {len(graph)} nodes and {sum(len(v) for v in graph.values())} edges")

    # Stage 3: Order components for orchestrator
    logger.info("Stage 3: Ordering components...")
    ordered_components = [components[cid] for cid in topo_order if cid in components]
    # for idx, component in enumerate(components.values()):
    #     print(f"Component {idx}: type={type(component)}, value={component}")

    # navigator_output_path = PROJECT_ROOT / "data" / "intermediate" / "navigator_output" / f"{repo_name}_navigator_output.json"
    # FileHandler.write_json(navigator_output_path, {
    #     "graph": {k: list(v) for k, v in graph.items()},
    #     "topological_order": topo_order,
    #     "dfs_order": dfs_order
    # })
    
    # Create project DAG as set of component IDs for faster lookups
    project_dag = set(components.keys())
    logger.info(f"Created project DAG with {len(project_dag)} components")
    
    # Stage 4: Initialize Orchestrator with project DAG
    logger.info("Stage 4: Initializing orchestrator...")
    orchestrator = Orchestrator(project_dag=project_dag)
    
    # Stage 5: Set repository data in searcher
    logger.info("Stage 5: Setting up searcher with repository data...")

    # Stage 5: Pass repository data to the searcher agent BEFORE processing
    orchestrator.searcher.set_repository_data(
        all_components=ordered_components,
        dependency_graph=None
    )

    # Stage 6: Run multi-agent pipeline
    logger.info("Stage 6: Running multi-agent pipeline...")
    docs = orchestrator.process_components(ordered_components)
    
    logger.info(
        f"Pipeline complete: "
        f"{orchestrator.successful_docs} successful, "
        f"{orchestrator.failed_docs} failed"
    )
    
    # Stage 7: Save writer output (documentation) to disk
    logger.info("Stage 7: Saving writer agent output to disk...")
    repo_path_obj = Path(repo_path)
    repo_name = repo_path_obj.name
    docs_output_path = PROJECT_ROOT / "data" / "intermediate" / "agent_output" / "writer" / f"{repo_name}_writer_output.json"
    try:
        serialized_docs = {}
        for doc in docs:
            if hasattr(doc, 'to_dict'):
                serialized_docs[doc.component_id] = doc.to_dict()
            else:
                serialized_docs[doc.component_id] = FileHandler.serialize_component(doc)
        
        FileHandler.write_json(docs_output_path, serialized_docs)
        logger.info(f"Writer output saved to {docs_output_path}")
    except Exception as e:
        logger.warning(f"Failed to save writer output: {e}")

    # Extract module globals and inject into component metadata
    _extract_module_globals(components)
    logger.info(f"Populated module_globals metadata for components")

    # Return all relevant results as a dict
    return {
        "components": components,
        "graph": graph,
        "topological_order": topo_order,
        "dfs_order": dfs_order,
        "documentation": docs,
        "statistics": {
            'total_processed': orchestrator.total_components_processed,
            'successful': orchestrator.successful_docs,
            'failed': orchestrator.failed_docs,
            'success_rate': (orchestrator.successful_docs / max(orchestrator.total_components_processed, 1)) * 100
        }
    }

def _extract_module_globals(components: Dict[str, CodeComponent]) -> None:
    """
    Extract module-level globals and inject into component metadata.
    Scan each module in the component set for module-level variable definitions.
    """
    # Group components by module path
    modules: Dict[str, List[CodeComponent]] = {}
    for comp in components.values():
        module = getattr(comp, 'module_path', None)
        if module:
            if module not in modules:
                modules[module] = []
            modules[module].append(comp)
    
    # For each module, extract globals from any module-level component
    for module_path, comps in modules.items():
        module_globals = set()
        
        # Look for module docstring or use first function's module context
        module_source = None
        for comp in comps:
            if comp.type == ComponentType.MODULE:
                module_source = comp.source_code
                break
        
        # If no module component, extract from first available component
        if not module_source and comps:
            # Get the source file and parse globals
            first_comp = comps[0]
            try:
                import re
                # Find variable assignments at module level (not indented)
                source_file_path = getattr(first_comp.location, 'file_path', None)
                if source_file_path:
                    with open(source_file_path, 'r') as f:
                        full_source = f.read()
                    
                    # Extract module-level assignments (lines not starting with spaces)
                    lines = full_source.split('\n')
                    for line in lines:
                        # Skip empty lines, comments, and indented code
                        if not line or line[0] in ' \t' or line.strip().startswith('#'):
                            continue
                        # Match variable assignments
                        match = re.match(r'^(\w+)\s*=', line)
                        if match:
                            var_name = match.group(1)
                            # Skip imports and special names
                            if not line.startswith('import ') and not line.startswith('from '):
                                module_globals.add(var_name)
            except Exception:
                pass
        
        # Inject module_globals into all components from this module
        for comp in comps:
            if not comp.metadata:
                comp.metadata = {}
            comp.metadata['module_globals'] = module_globals