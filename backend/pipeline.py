"""
Main pipeline orchestrator
"""

from typing import List, Dict, Callable, Optional, Any
import networkx as nx
from backend.navigator.core.repository_parser import RepositoryParser
from backend.navigator.core.ir_export import export_ir
from backend.navigator.core.dag_export import export_dag
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
from backend.utils.paths import DATA_ROOT
from pathlib import Path

logger = get_logger(__name__)


# Type alias for the optional status callback.
# Signature: callback(agent_name, status, progress_percent, message, details)
StatusCallback = Optional[Callable[[str, str, int, str, Optional[Dict[str, Any]]], None]]


def run_pipeline(repo_path: str, status_callback: StatusCallback = None):
    """
    Run the documentation pipeline for a given repository path.
    Returns a dict with components, graph, orders, and documentation.

    Args:
        repo_path: Path to the cloned repository.
        status_callback: Optional callback invoked after each major stage.
            Signature: callback(agent_name, status, progress_percent, message)
    """
    def _cb(
        agent: str,
        status: str,
        progress: int,
        msg: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Fire the callback if one was provided."""
        if status_callback:
            try:
                status_callback(agent, status, progress, msg, details or {})
            except Exception as cb_err:
                logger.warning(f"status_callback error: {cb_err}")

    logger.info(f"Starting pipeline for repository: {repo_path}")
    _cb("navigator", "in_progress", 2, "Starting pipeline…", {
        "phase": "navigator",
        "step_id": "start",
    })
    
    # Stage 1: Parse repository and extract components
    _cb("navigator", "in_progress", 5, "Parsing repository", {
        "phase": "navigator",
        "step_id": "extract-components",
    })
    logger.info("Stage 1: Parsing repository and extracting components...")
    parser = RepositoryParser(repo_path)
    components = parser.parse()  # {id: CodeComponent}

    component_summaries: list[dict[str, str]] = []
    for comp in components.values():
        comp_type = comp.type.value if hasattr(comp.type, "value") else str(comp.type)
        comp_path = getattr(getattr(comp, "location", None), "file_path", "unknown") or "unknown"
        component_summaries.append(
            {
                "id": comp.id,
                "name": comp.name,
                "type": comp_type,
                "file_path": comp_path,
            }
        )
    _cb("navigator", "completed", 7, "Repository parsed", {
        "phase": "navigator",
        "step_id": "extract-components",
    })

    _cb("navigator", "in_progress", 8, "Extracting code components", {
        "phase": "navigator",
        "step_id": "generate-metadata",
    })
    # Extract module globals and inject into component metadata
    _extract_module_globals(components)
    logger.info(f"Populated module_globals metadata for components")
    logger.info(f"Extracted {len(components)} components")

    _cb("navigator", "completed", 10, f"Extracted {len(components)} components", {
        "phase": "navigator",
        "step_id": "generate-metadata",
        "component_count": len(components),
        "components": component_summaries,
    })
    # Explicit terminal output so the component count is always visible
    # even if logger formatting/filtering changes.
    print(f"[Navigator] Total components extracted: {len(components)}")
    logger.info(f"Navigator component count: {len(components)}")

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
    _cb("navigator", "in_progress", 11, "Resolving dependencies", {
        "phase": "navigator",
        "step_id": "build-dependency-graph",
    })
    logger.info("Stage 2: Building dependency graph...")
    graph = build_graph_from_components(components)
    graph = resolve_cycles(graph)
    _cb("navigator", "completed", 13, "Dependency resolution complete", {
        "phase": "navigator",
        "step_id": "build-dependency-graph",
    })

    _cb("navigator", "in_progress", 14, "IR generation", {
        "phase": "navigator",
        "step_id": "create-dag",
    })
    repo_name = Path(repo_path).name
    try:
        export_ir(components, repo_id=repo_name)
    except Exception as exc:
        logger.warning(f"IR export failed: {exc}")
    _cb("navigator", "completed", 15, "IR generated", {
        "phase": "navigator",
        "step_id": "create-dag",
    })

    _cb("navigator", "in_progress", 16, "Running topological sort", {
        "phase": "navigator",
        "step_id": "init-llm-pipeline",
    })
    topo_order = topological_sort(graph)
    dfs_order = dependency_first_dfs(graph)
    _cb("navigator", "completed", 17, "Topological sort complete", {
        "phase": "navigator",
        "step_id": "init-llm-pipeline",
    })

    _cb("navigator", "in_progress", 18, "Generating dependency acyclic graph", {
        "phase": "navigator",
        "step_id": "load-graph",
    })
    try:
        export_dag(graph, repo_id=repo_name)
    except Exception as exc:
        logger.warning(f"DAG export failed: {exc}")
    
    logger.info(f"Built dependency graph with {len(graph)} nodes and {sum(len(v) for v in graph.values())} edges")
    _cb("navigator", "completed", 19, f"Dependency graph built: {len(graph)} nodes", {
        "phase": "navigator",
        "step_id": "load-graph",
        "node_count": len(graph),
    })

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

    # Stage 5: Convert adjacency dict to NetworkX DiGraph and pass to searcher
    # The graph is Dict[str, Set[str]] where A -> B means A depends on B
    nx_graph = nx.DiGraph()
    nx_graph.add_nodes_from(graph.keys())
    for source, targets in graph.items():
        for target in targets:
            nx_graph.add_edge(source, target)
    
    logger.info(f"Converted adjacency graph to NetworkX DiGraph: {nx_graph.number_of_nodes()} nodes, {nx_graph.number_of_edges()} edges")
    
    orchestrator.searcher.set_repository_data(
        all_components=ordered_components,
        dependency_graph=nx_graph
    )

    # Stage 6: Run multi-agent pipeline
    logger.info("Stage 6: Running multi-agent pipeline...")
    _cb("reader", "in_progress", 20, "Starting multi-agent pipeline…", {
        "phase": "agentic",
        "step_id": "reader",
    })
    docs = orchestrator.process_components(ordered_components, status_callback=_cb)
    
    logger.info(
        f"Pipeline complete: "
        f"{orchestrator.successful_docs} successful, "
        f"{orchestrator.failed_docs} failed"
    )
    
    _cb("evaluator", "in_progress", 92, "Saving documentation output…", {
        "phase": "finalization",
        "step_id": "save-outputs",
    })

    # Stage 7: Save writer output (documentation) to disk
    logger.info("Stage 7: Saving writer agent output to disk...")
    repo_path_obj = Path(repo_path)
    repo_name = repo_path_obj.name
    docs_output_path = DATA_ROOT / "intermediate" / "agent_output" / "writer" / f"{repo_name}_writer_output.json"
    try:
        serialized_docs = {}
        for doc in docs:
            if hasattr(doc, 'to_dict'):
                serialized_docs[doc.component_id] = doc.to_dict()
            else:
                serialized_docs[doc.component_id] = FileHandler.serialize_component(doc)
        
        FileHandler.write_json(docs_output_path, serialized_docs)
        logger.info(f"Writer output saved to {docs_output_path}")
        _cb("evaluator", "completed", 95, "Documentation output saved", {
            "phase": "finalization",
            "step_id": "save-outputs",
        })
    except Exception as e:
        logger.warning(f"Failed to save writer output: {e}")
        _cb("evaluator", "failed", 95, "Failed to save documentation output", {
            "phase": "finalization",
            "step_id": "save-outputs",
        })

    # Extract module globals and inject into component metadata
    _cb("evaluator", "in_progress", 96, "Generating pipeline summary…", {
        "phase": "finalization",
        "step_id": "generate-summary",
    })
    _extract_module_globals(components)
    logger.info(f"Populated module_globals metadata for components")

    _cb("evaluator", "completed", 97, "Pipeline summary generated", {
        "phase": "finalization",
        "step_id": "generate-summary",
    })
    _cb("evaluator", "completed", 100, "Pipeline complete", {
        "phase": "finalization",
        "step_id": "pipeline-completed",
    })

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