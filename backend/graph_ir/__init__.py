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
    
    # CKG models
    CKGRequest,
    CKGSubgraphRequest,
    CKGPathRequest,
    CKGStatsResponse,
    CKGResponse,
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

from .hpg_builder import (
    build_hpg,
)

from .ckg_builder import (
    build_ckg,
    export_to_json,
    extract_subgraph,
    get_graph_statistics,
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
    "CKGRequest",
    "CKGSubgraphRequest",
    "CKGPathRequest",
    "CKGStatsResponse",
    "CKGResponse",

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

    # HPG
    "build_hpg",

    # CKG
    "build_ckg",
    "export_to_json",
    "extract_subgraph",
    "get_graph_statistics",

    # Service
    "GraphService",
    "get_graph_service",
    "initialize_service",
]
