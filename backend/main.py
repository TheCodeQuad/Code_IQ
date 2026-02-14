import sys
from pathlib import Path

# Ensure project root is on sys.path so 'backend.*' imports work when running this file directly
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.navigator.core.repository_parser import RepositoryParser
from backend.navigator.core.topo import (
    build_graph_from_components,
    topological_sort,
    dependency_first_dfs,
    resolve_cycles
)
from backend.navigator.core.ir_export import export_ir
from backend.navigator.core.dag_export import export_dag
from backend.models.code_component import CodeComponent, ComponentType
from backend.navigator.core.repo_loader import clone_repo
from pathlib import Path
import sys

# Orchestrator disabled for navigator-only run
# from backend.agents.orchestrator.orchestrator import Orchestrator

def main():
    # Prompt for GitHub repo URL or local path
    print("Navigator runner (no agents)")
    print("Enter GitHub repository URL or local path (e.g., data/input/repositories/<repo>):")
    user_input = input("> ").strip()

    if not user_input:
        print("No input provided. Exiting.")
        return

    # Resolve repository path: clone if URL, else treat as local path
    if user_input.startswith("http"):
        print(f"Cloning repository: {user_input}")
        repo_path = Path(clone_repo(user_input))
    else:
        repo_path = Path(user_input)
        if not repo_path.is_absolute():
            # Treat relative paths as relative to project root
            project_root = Path(__file__).resolve().parents[1]
            repo_path = (project_root / repo_path).resolve()

    if not repo_path.exists():
        print(f"Repository path does not exist: {repo_path}")
        return

    # Ensure project root is on sys.path for backend.* imports if run directly
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    repo_id = repo_path.name
    parser = RepositoryParser(str(repo_path))  # navigator-only parse

    components = parser.parse()
    export_ir(components, repo_id=repo_id)

    graph = build_graph_from_components(components)
    graph = resolve_cycles(graph)
    export_dag(graph, repo_id=repo_id)

    # Get topological order of component IDs
    topo_order = topological_sort(graph)
    # Convert all components to the standard CodeComponent if needed
    for cid, nav_comp in components.items():
    # Only convert if not already the correct type
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
# components is already a dict: {id: CodeComponent}
    # id_to_component = components
    ordered_components = [components[cid] for cid in topo_order if cid in components]
    for idx, component in enumerate(components.values()):
        print(f"Component {idx}: type={type(component)}, value={component}")

    # Orchestrator pipeline disabled for faster navigator-only iteration
    # orchestrator = Orchestrator()
    # docs = orchestrator.process_components(ordered_components)
    
    print("Parsed components:", components)
    print("Topological order:", topo_order)
    print("Ordered components:", ordered_components)

    # print("\nGenerated Documentation:")
    # for doc in docs:
    #     print(doc)  # Or format as needed

if __name__ == "__main__":
    main()