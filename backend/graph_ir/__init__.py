"""
Graph IR Package

Provides code analysis and graph generation capabilities:
- AST parsing to Intermediate Representation (IR)
- Control Flow Graph (CFG) generation
- Program Dependency Graph (PDG) generation
- Repository-level DAG generation
- Hybrid Program Graph (HPG) generation
"""

from .models import (
    # Core IR models
    IRStatement,
    StatementType,
    Variable,
    FunctionCall,
    Import,
    ParameterInfo,
    FunctionIR,
    ClassIR,
    ModuleIR,
    RepositoryIR,
    ComponentType,
    DependencyType,

    # Graph output models
    Graph,
    GraphNode,
    GraphEdge,

    # API response models
    ComponentInfo,
    GraphResponse,
    MultiGraphResponse,
    GraphListResponse,
    ParseStatusResponse,
)

from .parser import (
    RepositoryParser,
    parse_repository,
    parse_file,
)

from .cfg_builder import (
    CFGBuilder,
    build_cfg,
    build_cfg_from_source,
)

from .pdg_builder import (
    PDGBuilder,
    build_pdg,
    build_pdg_with_reaching_defs,
)

from .dag_builder import (
    DAGBuilder,
    build_dag,
    build_file_dag,
    build_neighborhood_dag,
    get_dependencies_dict,
)

from .service import (
    GraphService,
    get_graph_service,
    initialize_service,
)

__all__ = [
    # Models
    "IRStatement",
    "StatementType",
    "Variable",
    "FunctionCall",
    "Import",
    "ParameterInfo",
    "FunctionIR",
    "ClassIR",
    "ModuleIR",
    "RepositoryIR",
    "ComponentType",
    "DependencyType",
    "Graph",
    "GraphNode",
    "GraphEdge",
    "ComponentInfo",
    "GraphResponse",
    "MultiGraphResponse",
    "GraphListResponse",
    "ParseStatusResponse",

    # Parser
    "RepositoryParser",
    "parse_repository",
    "parse_file",

    # Builders
    "CFGBuilder",
    "build_cfg",
    "build_cfg_from_source",
    "PDGBuilder",
    "build_pdg",
    "build_pdg_with_reaching_defs",
    "DAGBuilder",
    "build_dag",
    "build_file_dag",
    "build_neighborhood_dag",
    "get_dependencies_dict",

    # Service
    "GraphService",
    "get_graph_service",
    "initialize_service",
]
