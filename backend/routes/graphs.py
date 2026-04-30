"""
FastAPI Routes for Graph Generation

Provides REST API endpoints for:
- Repository parsing
- CFG (Control Flow Graph) generation
- PDG (Program Dependency Graph) generation
- DAG (Dependency Graph) generation
- HPG (Hybrid Program Graph) generation
"""

import os
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
import logging

from ..graph_ir import (
    get_graph_service,
    GraphResponse,
    MultiGraphResponse,
    GraphListResponse,
    ParseStatusResponse,
    Graph,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graphs", tags=["graphs"])


# =============================================================================
# Request/Response Models
# =============================================================================

class ParseRequest(BaseModel):
    """Request to parse a repository"""
    repo_path: str = Field(..., description="Path to the repository root")
    force: bool = Field(False, description="Force re-parsing even if cached")
    exclude_patterns: Optional[List[str]] = Field(
        None,
        description="Patterns to exclude (e.g., ['test_*', '*_test.py'])"
    )


class ParseResponse(BaseModel):
    """Response for repository parsing"""
    success: bool
    message: str
    file_count: int = 0
    function_count: int = 0
    class_count: int = 0
    errors: List[str] = []


class ComponentGraphRequest(BaseModel):
    """Request for component-level graph"""
    repo_path: str = Field(..., description="Path to the repository root")
    component_id: str = Field(..., description="Component ID (function/method/class)")


class DAGRequest(BaseModel):
    """Request for DAG generation"""
    repo_path: str = Field(..., description="Path to the repository root")
    file_path: Optional[str] = Field(None, description="Filter to specific file")
    component_id: Optional[str] = Field(None, description="Get neighborhood for component")
    neighborhood_depth: int = Field(1, description="Depth for neighborhood DAG")


# =============================================================================
# Parsing Endpoints
# =============================================================================

@router.post("/parse", response_model=ParseResponse)
def parse_repository(request: ParseRequest):
    """
    Parse a repository to build IR.

    This is the first step - parse the repository to extract functions,
    classes, and their structure. The IR is cached for subsequent graph
    generation requests.
    """
    service = get_graph_service()

    try:
        if not os.path.isdir(request.repo_path):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid repository path: {request.repo_path}"
            )

        # 1) Multi-language component IR (Navigator) for repo-wide graphs
        try:
            service.parse_repository_components(request.repo_path, force=request.force)
        except Exception as nav_exc:
            # Do not hard-fail parse if Navigator has an issue; CFG/PDG/HPG may still work for Python.
            logger.warning(f"Navigator component parse failed: {nav_exc}")

        # 2) Python statement-level IR for CFG/PDG/HPG
        try:
            service.parse_repository(
                request.repo_path,
                force=request.force,
                exclude_patterns=request.exclude_patterns
            )
        except Exception as py_exc:
            logger.warning(f"Python IR parse failed: {py_exc}")

        # 3) Pre-build CKG (Complete Knowledge Graph) so it's ready immediately
        try:
            service.get_ckg(request.repo_path, force=request.force)
            logger.info(f"CKG pre-built for {request.repo_path}")
        except Exception as ckg_exc:
            logger.warning(f"CKG pre-build failed (will build on-demand): {ckg_exc}")

        status = service.get_parse_status(request.repo_path)

        return ParseResponse(
            success=True,
            message="Repository parsed successfully",
            file_count=status.file_count,
            function_count=status.function_count,
            class_count=status.class_count,
            errors=status.errors,
        )
    except Exception as e:
        logger.error(f"Error parsing repository: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/parse/status", response_model=ParseStatusResponse)
def get_parse_status(
    repo_path: str = Query(..., description="Repository path")
):
    """Get parsing status for a repository"""
    service = get_graph_service()
    return service.get_parse_status(repo_path)


@router.post("/parse/clear")
def clear_parse_cache(
    repo_path: Optional[str] = Query(None, description="Repository path (or all if omitted)")
):
    """Clear parsed IR cache"""
    service = get_graph_service()
    service.clear_cache(repo_path)
    return {"success": True, "message": "Cache cleared"}


# =============================================================================
# Component Listing Endpoints
# =============================================================================

@router.get("/components", response_model=GraphListResponse)
def list_components(
    repo_path: str = Query(..., description="Repository path"),
    component_type: Optional[str] = Query(None, description="Filter by type (function, method, class)"),
    file_path: Optional[str] = Query(None, description="Filter by file path")
):
    """
    List all parseable components in a repository.

    Returns functions, methods, and classes that can have graphs generated.
    """
    service = get_graph_service()

    # Auto-parse if not already done
    if not service.get_ir(repo_path):
        if not os.path.isdir(repo_path):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid repository path: {repo_path}"
            )
        service.parse_repository(repo_path)

    return service.list_components(repo_path, component_type, file_path)


@router.get("/component/{component_id}")
def get_component(
    component_id: str,
    repo_path: str = Query(..., description="Repository path")
):
    """Get details of a specific component"""
    service = get_graph_service()

    component = service.get_component(repo_path, component_id)
    if not component:
        # Fallback to Navigator multi-language components
        comps = service.get_components(repo_path)
        if comps is None:
            try:
                comps = service.parse_repository_components(repo_path)
            except Exception:
                comps = None

        if comps and component_id in comps:
            return {
                "success": True,
                "data": comps[component_id].to_dict(),
            }

        raise HTTPException(
            status_code=404,
            detail=f"Component not found: {component_id}"
        )

    return {
        "success": True,
        "data": component.model_dump()
    }


# =============================================================================
# CFG Endpoints
# =============================================================================

@router.get("/cfg/{component_id}", response_model=GraphResponse)
def get_cfg(
    component_id: str,
    repo_path: str = Query(..., description="Repository path")
):
    """
    Get Control Flow Graph for a function/method.

    The CFG shows all possible execution paths through the function,
    including branches (if/else), loops (for/while), and exception handling.

    Nodes represent:
    - Entry/Exit points
    - Basic blocks (sequences of statements)
    - Branch points (conditions)
    - Merge points

    Edges represent:
    - Control flow between blocks
    - True/False branches
    - Loop back-edges
    """
    service = get_graph_service()

    # Auto-parse if needed
    if not service.get_ir(repo_path):
        if os.path.isdir(repo_path):
            service.parse_repository(repo_path)
        else:
            raise HTTPException(status_code=400, detail="Invalid repository path")

    response = service.get_cfg(repo_path, component_id)

    if not response.success:
        raise HTTPException(status_code=404, detail=response.message)

    return response


@router.post("/cfg", response_model=GraphResponse)
def get_cfg_post(request: ComponentGraphRequest):
    """Get CFG (POST version for complex paths)"""
    service = get_graph_service()

    if not service.get_ir(request.repo_path):
        if os.path.isdir(request.repo_path):
            service.parse_repository(request.repo_path)
        else:
            raise HTTPException(status_code=400, detail="Invalid repository path")

    response = service.get_cfg(request.repo_path, request.component_id)

    if not response.success:
        raise HTTPException(status_code=404, detail=response.message)

    return response


# =============================================================================
# PDG Endpoints
# =============================================================================

@router.get("/pdg/{component_id}", response_model=GraphResponse)
def get_pdg(
    component_id: str,
    repo_path: str = Query(..., description="Repository path"),
    use_reaching_defs: bool = Query(False, description="Use reaching definitions analysis")
):
    """
    Get Program Dependency Graph for a function/method.

    The PDG shows two types of dependencies:

    1. Data Dependencies (def-use chains):
       - Where variables are defined (assigned)
       - Where variables are used (read)
       - Edges show data flow between definitions and uses

    2. Control Dependencies:
       - Which statements depend on branch conditions
       - Edges show control flow influence

    Nodes represent:
    - Function entry
    - Parameters
    - Statements (assignments, calls, etc.)
    - Return statements

    This is useful for:
    - Understanding data flow
    - Program slicing
    - Impact analysis
    """
    service = get_graph_service()

    if not service.get_ir(repo_path):
        if os.path.isdir(repo_path):
            service.parse_repository(repo_path)
        else:
            raise HTTPException(status_code=400, detail="Invalid repository path")

    response = service.get_pdg(repo_path, component_id, use_reaching_defs)

    if not response.success:
        raise HTTPException(status_code=404, detail=response.message)

    return response


@router.post("/pdg", response_model=GraphResponse)
def get_pdg_post(
    request: ComponentGraphRequest,
    use_reaching_defs: bool = Query(False)
):
    """Get PDG (POST version)"""
    service = get_graph_service()

    if not service.get_ir(request.repo_path):
        if os.path.isdir(request.repo_path):
            service.parse_repository(request.repo_path)
        else:
            raise HTTPException(status_code=400, detail="Invalid repository path")

    response = service.get_pdg(request.repo_path, request.component_id, use_reaching_defs)

    if not response.success:
        raise HTTPException(status_code=404, detail=response.message)

    return response


# =============================================================================
# DAG Endpoints
# =============================================================================

@router.get("/dag", response_model=GraphResponse)
def get_dag(
    repo_path: str = Query(..., description="Repository path"),
    file_path: Optional[str] = Query(None, description="Filter to specific file"),
    component_id: Optional[str] = Query(None, description="Get neighborhood for component"),
    neighborhood_depth: int = Query(1, description="Depth for neighborhood DAG")
):
    """
    Get Dependency Graph for a repository.

    The DAG shows relationships between code components:
    - Function/method call dependencies
    - Class inheritance relationships
    - Import dependencies

    Options:
    - Full repository DAG: shows all dependencies
    - File DAG: shows dependencies within a single file
    - Neighborhood DAG: shows a component and its immediate dependencies/dependents

    Nodes represent:
    - Functions
    - Methods
    - Classes
    - Modules

    Edges represent:
    - Function calls
    - Inheritance (extends)
    - Imports
    """
    service = get_graph_service()

    if not service.get_ir(repo_path):
        if os.path.isdir(repo_path):
            service.parse_repository(repo_path)
        else:
            raise HTTPException(status_code=400, detail="Invalid repository path")

    response = service.get_dag(repo_path, file_path, component_id, neighborhood_depth)

    if not response.success:
        raise HTTPException(status_code=404, detail=response.message)

    return response


@router.post("/dag", response_model=GraphResponse)
def get_dag_post(request: DAGRequest):
    """Get DAG (POST version)"""
    service = get_graph_service()

    if not service.get_ir(request.repo_path):
        if os.path.isdir(request.repo_path):
            service.parse_repository(request.repo_path)
        else:
            raise HTTPException(status_code=400, detail="Invalid repository path")

    response = service.get_dag(
        request.repo_path,
        request.file_path,
        request.component_id,
        request.neighborhood_depth
    )

    if not response.success:
        raise HTTPException(status_code=404, detail=response.message)

    return response


@router.get("/dag/dict")
def get_dag_dict(
    repo_path: str = Query(..., description="Repository path")
):
    """
    Get dependencies as a simple dictionary.

    Returns: {component_name: [dependency_names]}

    This format is compatible with existing frontend code.
    """
    service = get_graph_service()

    if not service.get_ir(repo_path):
        if os.path.isdir(repo_path):
            service.parse_repository(repo_path)
        else:
            raise HTTPException(status_code=400, detail="Invalid repository path")

    deps = service.get_dag_dict(repo_path)

    return {
        "success": True,
        "data": deps
    }


# =============================================================================
# HPG Endpoints
# =============================================================================

@router.get("/hpg/{component_id}", response_model=GraphResponse)
def get_hpg(
    component_id: str,
    repo_path: str = Query(..., description="Repository path")
):
    """
    Get Hybrid Program Graph for a function/method.

    The HPG combines CFG and PDG into a unified representation:
    - Control flow edges from CFG
    - Data dependency edges from PDG

    This provides the most comprehensive view of a function's structure,
    showing both how control flows and how data moves through the code.
    """
    service = get_graph_service()

    if not service.get_ir(repo_path):
        if os.path.isdir(repo_path):
            service.parse_repository(repo_path)
        else:
            raise HTTPException(status_code=400, detail="Invalid repository path")

    response = service.get_hpg(repo_path, component_id)

    if not response.success:
        raise HTTPException(status_code=404, detail=response.message)

    return response


# =============================================================================
# Combined Graph Endpoints
# =============================================================================

@router.get("/all/{component_id}", response_model=MultiGraphResponse)
def get_all_graphs(
    component_id: str,
    repo_path: str = Query(..., description="Repository path")
):
    """
    Get all graphs (CFG, PDG, DAG) for a component.

    Returns all available graph types in a single request.
    """
    service = get_graph_service()

    if not service.get_ir(repo_path):
        if os.path.isdir(repo_path):
            service.parse_repository(repo_path)
        else:
            raise HTTPException(status_code=400, detail="Invalid repository path")

    return service.get_all_graphs(repo_path, component_id)


# =============================================================================
# Utility Endpoints
# =============================================================================

@router.get("/find")
def find_component(
    repo_path: str = Query(..., description="Repository path"),
    name: str = Query(..., description="Component name to find"),
    file_path: Optional[str] = Query(None, description="Filter by file")
):
    """Find a component ID by name"""
    service = get_graph_service()

    if not service.get_ir(repo_path):
        if os.path.isdir(repo_path):
            service.parse_repository(repo_path)
        else:
            raise HTTPException(status_code=400, detail="Invalid repository path")

    component_id = service.find_component_by_name(repo_path, name, file_path)

    if not component_id:
        raise HTTPException(
            status_code=404,
            detail=f"Component not found: {name}"
        )

    return {
        "success": True,
        "component_id": component_id
    }


# =============================================================================
# CKG (Complete Knowledge Graph) Endpoints
# =============================================================================

@router.get("/ckg", response_model=dict)
def get_ckg(
    repo_path: str = Query(..., description="Repository path"),
    force: bool = Query(False, description="Force rebuild")
):
    """
    Get Complete Knowledge Graph for the entire repository.
    
    The CKG is a unified graph combining:
    - Hierarchy: module → class → function → statement
    - Calls: function/method invocations
    - Imports: module dependencies
    - Inheritance: class extends relationships
    - Control flow: CFG edges within functions
    - Data flow: PDG data dependencies within functions
    
    Returns JSON format:
    {
        "nodes": [{"id": "...", "label": "...", "type": "...", "metadata": {...}}],
        "edges": [{"id": "...", "source": "...", "target": "...", "type": "...", "label": "..."}],
        "stats": {"node_count": ..., "edge_count": ..., "node_types": {...}, "edge_types": {...}}
    }
    """
    service = get_graph_service()
    
    try:
        if not os.path.isdir(repo_path):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid repository path: {repo_path}"
            )
        
        # Auto-parse if not already done
        if not service.get_ir(repo_path) and not force:
            try:
                service.parse_repository(repo_path)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse repository: {str(e)}"
                )
        
        ckg_data = service.get_ckg_export(repo_path, force)
        
        # Check if CKG is empty and provide helpful message
        if ckg_data.get("stats", {}).get("node_count", 0) == 0:
            logger.warning(f"CKG is empty for {repo_path}")
            return {
                "success": True,
                "data": ckg_data,
                "warning": "No code components found in repository. Ensure it contains Python files with functions/classes."
            }
        
        return {
            "success": True,
            "data": ckg_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building CKG: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ckg/subgraph", response_model=dict)
def get_ckg_subgraph(
    repo_path: str = Query(..., description="Repository path"),
    component_id: str = Query(..., description="Center node ID"),
    k_hops: int = Query(1, description="Number of hops", ge=1, le=5),
    edge_types: Optional[str] = Query(None, description="Comma-separated edge types"),
    direction: str = Query("both", description="Direction: in, out, or both")
):
    """
    Get k-hop neighborhood subgraph around a component.
    
    Useful for:
    - Analyzing local dependencies of a function
    - Visualizing call chains
    - Tracing data flow around a component
    
    Args:
        repo_path: Repository path
        component_id: Center node ID (function/class/module)
        k_hops: Number of hops to expand (1-5)
        edge_types: Filter by types (e.g., "calls,hierarchy")
        direction: "in" (predecessors), "out" (successors), or "both"
    """
    service = get_graph_service()
    
    try:
        if not os.path.isdir(repo_path):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid repository path: {repo_path}"
            )
        
        # Parse edge types if provided
        edge_type_list = None
        if edge_types:
            edge_type_list = [t.strip() for t in edge_types.split(",")]
        
        # Get subgraph
        subgraph_data = service.get_ckg_subgraph(
            repo_path,
            component_id,
            k_hops,
            edge_type_list,
            direction
        )
        
        return {
            "success": True,
            "data": subgraph_data
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting CKG subgraph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ckg/stats", response_model=dict)
def get_ckg_stats(
    repo_path: str = Query(..., description="Repository path")
):
    """
    Get statistics about the Complete Knowledge Graph.
    
    Returns:
    - Node/edge counts by type
    - Degree statistics
    - Graph properties (DAG, connected components, etc.)
    """
    service = get_graph_service()
    
    try:
        if not os.path.isdir(repo_path):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid repository path: {repo_path}"
            )
        
        stats = service.get_ckg_stats(repo_path)
        
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        logger.error(f"Error getting CKG stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ckg/paths", response_model=dict)
def get_ckg_paths(
    repo_path: str = Query(..., description="Repository path"),
    source: str = Query(..., description="Source node ID"),
    target: str = Query(..., description="Target node ID"),
    max_depth: int = Query(10, description="Maximum path length", ge=1, le=20),
    edge_types: Optional[str] = Query(None, description="Comma-separated edge types")
):
    """
    Find all paths between two nodes in the CKG.
    
    Useful for:
    - Dependency analysis (what does X depend on through Y?)
    - Call chain analysis (how is function A reached from function B?)
    - Data flow tracing (how does data flow from A to B?)
    
    Args:
        source: Source node ID
        target: Target node ID
        max_depth: Maximum path length (1-20)
        edge_types: Filter by types (e.g., "calls,hierarchy")
    """
    service = get_graph_service()
    
    try:
        if not os.path.isdir(repo_path):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid repository path: {repo_path}"
            )
        
        # Parse edge types if provided
        edge_type_list = None
        if edge_types:
            edge_type_list = [t.strip() for t in edge_types.split(",")]
        
        # Find paths
        paths = service.get_ckg_paths(
            repo_path,
            source,
            target,
            max_depth,
            edge_type_list
        )
        
        return {
            "success": True,
            "data": {
                "paths": paths,
                "count": len(paths)
            }
        }
    except Exception as e:
        logger.error(f"Error finding CKG paths: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ckg/clear")
def clear_ckg_cache(
    repo_path: Optional[str] = Query(None, description="Repository path (or all if omitted)")
):
    """Clear CKG cache for a repository or all repositories"""
    service = get_graph_service()
    service.clear_ckg_cache(repo_path)
    
    return {
        "success": True,
        "message": "CKG cache cleared"
    }

