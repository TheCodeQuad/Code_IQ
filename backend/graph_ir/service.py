"""
Graph IR Service Layer

This module provides a high-level service interface for parsing repositories
and generating graphs. It manages caching, lazy loading, and provides
the API used by FastAPI routes.
"""

import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from threading import Lock
import logging

from .models import (
    RepositoryIR, FunctionIR, ClassIR, ModuleIR,
    Graph, GraphResponse, MultiGraphResponse,
    ComponentInfo, ComponentType, GraphListResponse,
    ParseStatusResponse
)
from .parser import RepositoryParser, parse_repository, parse_file
from .cfg_builder import build_cfg, CFGBuilder
from .pdg_builder import build_pdg, build_pdg_with_reaching_defs, PDGBuilder
from .dag_builder import (
    build_dag, build_file_dag, build_neighborhood_dag,
    get_dependencies_dict, DAGBuilder
)

logger = logging.getLogger(__name__)


class GraphService:
    """
    Main service class for graph generation.

    Provides:
    - Repository parsing with caching
    - CFG, PDG, DAG generation
    - Component listing and lookup
    """

    def __init__(self, cache_dir: Optional[str] = None):
        self._ir_cache: Dict[str, RepositoryIR] = {}
        self._cache_lock = Lock()
        self._parse_timestamps: Dict[str, datetime] = {}
        self._parse_errors: Dict[str, List[str]] = {}

        # Cache directory for persisted IR
        self.cache_dir = cache_dir or os.path.join(
            os.path.dirname(__file__), ".cache"
        )
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_key(self, repo_path: str) -> str:
        """Generate cache key for a repository"""
        abs_path = os.path.abspath(repo_path)
        return hashlib.md5(abs_path.encode()).hexdigest()

    def parse_repository(
        self,
        repo_path: str,
        force: bool = False,
        exclude_patterns: Optional[List[str]] = None
    ) -> RepositoryIR:
        """
        Parse a repository and cache the IR.

        Args:
            repo_path: Path to repository root
            force: Force re-parsing even if cached
            exclude_patterns: Patterns to exclude (e.g., ['test_*', '*_test.py'])

        Returns:
            RepositoryIR for the repository
        """
        cache_key = self._get_cache_key(repo_path)

        with self._cache_lock:
            if not force and cache_key in self._ir_cache:
                return self._ir_cache[cache_key]

        # Parse the repository
        logger.info(f"Parsing repository: {repo_path}")
        parser = RepositoryParser(repo_path, exclude_patterns)
        ir = parser.parse_repository()

        with self._cache_lock:
            self._ir_cache[cache_key] = ir
            self._parse_timestamps[cache_key] = datetime.now()
            self._parse_errors[cache_key] = parser.errors

        logger.info(
            f"Parsed {len(ir.functions)} functions, "
            f"{len(ir.classes)} classes, "
            f"{len(ir.modules)} modules"
        )

        return ir

    def parse_file(self, file_path: str) -> RepositoryIR:
        """Parse a single file"""
        return parse_file(file_path)

    def get_parse_status(self, repo_path: str) -> ParseStatusResponse:
        """Get parsing status for a repository"""
        cache_key = self._get_cache_key(repo_path)

        with self._cache_lock:
            if cache_key not in self._ir_cache:
                return ParseStatusResponse(
                    success=True,
                    is_parsed=False
                )

            ir = self._ir_cache[cache_key]
            timestamp = self._parse_timestamps.get(cache_key)
            errors = self._parse_errors.get(cache_key, [])

            return ParseStatusResponse(
                success=True,
                is_parsed=True,
                file_count=len(ir.modules),
                function_count=len(ir.functions),
                class_count=len(ir.classes),
                last_parsed=timestamp.isoformat() if timestamp else None,
                errors=errors
            )

    def get_ir(self, repo_path: str) -> Optional[RepositoryIR]:
        """Get cached IR for a repository"""
        cache_key = self._get_cache_key(repo_path)
        with self._cache_lock:
            return self._ir_cache.get(cache_key)

    def clear_cache(self, repo_path: Optional[str] = None):
        """Clear cached IR"""
        with self._cache_lock:
            if repo_path:
                cache_key = self._get_cache_key(repo_path)
                self._ir_cache.pop(cache_key, None)
                self._parse_timestamps.pop(cache_key, None)
                self._parse_errors.pop(cache_key, None)
            else:
                self._ir_cache.clear()
                self._parse_timestamps.clear()
                self._parse_errors.clear()

    # =========================================================================
    # Component Listing
    # =========================================================================

    def list_components(
        self,
        repo_path: str,
        component_type: Optional[str] = None,
        file_path: Optional[str] = None
    ) -> GraphListResponse:
        """
        List all parseable components in a repository.

        Args:
            repo_path: Repository path
            component_type: Filter by type (function, class, method)
            file_path: Filter by file

        Returns:
            List of ComponentInfo objects
        """
        ir = self.get_ir(repo_path)
        if not ir:
            ir = self.parse_repository(repo_path)

        components: List[ComponentInfo] = []

        # Add functions
        for func_id, func_ir in ir.functions.items():
            if file_path and func_ir.file_path != file_path:
                continue
            if component_type and func_ir.type.value != component_type:
                continue

            components.append(ComponentInfo(
                id=func_id,
                name=func_ir.name,
                type=func_ir.type,
                file_path=func_ir.file_path,
                start_line=func_ir.start_line,
                end_line=func_ir.end_line,
                parent_class=func_ir.parent_class
            ))

        # Add classes
        if not component_type or component_type == "class":
            for class_id, class_ir in ir.classes.items():
                if file_path and class_ir.file_path != file_path:
                    continue

                components.append(ComponentInfo(
                    id=class_id,
                    name=class_ir.name,
                    type=ComponentType.CLASS,
                    file_path=class_ir.file_path,
                    start_line=class_ir.start_line,
                    end_line=class_ir.end_line
                ))

        return GraphListResponse(
            success=True,
            components=components,
            total=len(components)
        )

    def get_component(
        self,
        repo_path: str,
        component_id: str
    ) -> Optional[FunctionIR | ClassIR]:
        """Get a specific component by ID"""
        ir = self.get_ir(repo_path)
        if not ir:
            ir = self.parse_repository(repo_path)

        if component_id in ir.functions:
            return ir.functions[component_id]
        if component_id in ir.classes:
            return ir.classes[component_id]
        return None

    def find_component_by_name(
        self,
        repo_path: str,
        name: str,
        file_path: Optional[str] = None
    ) -> Optional[str]:
        """Find a component ID by name"""
        ir = self.get_ir(repo_path)
        if not ir:
            ir = self.parse_repository(repo_path)

        # Search functions
        for func_id, func_ir in ir.functions.items():
            if func_ir.name == name:
                if not file_path or func_ir.file_path == file_path:
                    return func_id

        # Search classes
        for class_id, class_ir in ir.classes.items():
            if class_ir.name == name:
                if not file_path or class_ir.file_path == file_path:
                    return class_id

        return None

    # =========================================================================
    # Graph Generation
    # =========================================================================

    def get_cfg(
        self,
        repo_path: str,
        component_id: str
    ) -> GraphResponse:
        """
        Get Control Flow Graph for a function/method.

        Args:
            repo_path: Repository path
            component_id: Function or method ID

        Returns:
            GraphResponse containing the CFG
        """
        ir = self.get_ir(repo_path)
        if not ir:
            ir = self.parse_repository(repo_path)

        func_ir = ir.functions.get(component_id)
        if not func_ir:
            return GraphResponse(
                success=False,
                message=f"Function not found: {component_id}"
            )

        try:
            cfg = build_cfg(func_ir)
            return GraphResponse(success=True, data=cfg)
        except Exception as e:
            logger.error(f"Error building CFG: {e}")
            return GraphResponse(
                success=False,
                message=f"Error building CFG: {str(e)}"
            )

    def get_pdg(
        self,
        repo_path: str,
        component_id: str,
        use_reaching_defs: bool = False
    ) -> GraphResponse:
        """
        Get Program Dependency Graph for a function/method.

        Args:
            repo_path: Repository path
            component_id: Function or method ID
            use_reaching_defs: Use reaching definitions analysis for accuracy

        Returns:
            GraphResponse containing the PDG
        """
        ir = self.get_ir(repo_path)
        if not ir:
            ir = self.parse_repository(repo_path)

        func_ir = ir.functions.get(component_id)
        if not func_ir:
            return GraphResponse(
                success=False,
                message=f"Function not found: {component_id}"
            )

        try:
            if use_reaching_defs:
                pdg = build_pdg_with_reaching_defs(func_ir)
            else:
                pdg = build_pdg(func_ir)
            return GraphResponse(success=True, data=pdg)
        except Exception as e:
            logger.error(f"Error building PDG: {e}")
            return GraphResponse(
                success=False,
                message=f"Error building PDG: {str(e)}"
            )

    def get_dag(
        self,
        repo_path: str,
        file_path: Optional[str] = None,
        component_id: Optional[str] = None,
        neighborhood_depth: int = 1
    ) -> GraphResponse:
        """
        Get Dependency Graph.

        Args:
            repo_path: Repository path
            file_path: Optional - get DAG for specific file
            component_id: Optional - get neighborhood DAG for component
            neighborhood_depth: Depth for neighborhood DAG

        Returns:
            GraphResponse containing the DAG
        """
        ir = self.get_ir(repo_path)
        if not ir:
            ir = self.parse_repository(repo_path)

        try:
            if component_id:
                dag = build_neighborhood_dag(ir, component_id, neighborhood_depth)
            elif file_path:
                dag = build_file_dag(ir, file_path)
            else:
                dag = build_dag(ir)

            return GraphResponse(success=True, data=dag)
        except Exception as e:
            logger.error(f"Error building DAG: {e}")
            return GraphResponse(
                success=False,
                message=f"Error building DAG: {str(e)}"
            )

    def get_dag_dict(self, repo_path: str) -> Dict[str, List[str]]:
        """
        Get dependencies as simple dict (for backward compatibility).

        Returns:
            Dict mapping component names to their dependency names
        """
        ir = self.get_ir(repo_path)
        if not ir:
            ir = self.parse_repository(repo_path)

        return get_dependencies_dict(ir)

    def get_all_graphs(
        self,
        repo_path: str,
        component_id: str
    ) -> MultiGraphResponse:
        """
        Get all graphs (CFG, PDG, neighborhood DAG) for a component.

        Args:
            repo_path: Repository path
            component_id: Function or method ID

        Returns:
            MultiGraphResponse with all graphs
        """
        graphs: Dict[str, Graph] = {}

        # Get CFG
        cfg_response = self.get_cfg(repo_path, component_id)
        if cfg_response.success and cfg_response.data:
            graphs["cfg"] = cfg_response.data

        # Get PDG
        pdg_response = self.get_pdg(repo_path, component_id)
        if pdg_response.success and pdg_response.data:
            graphs["pdg"] = pdg_response.data

        # Get neighborhood DAG
        dag_response = self.get_dag(repo_path, component_id=component_id)
        if dag_response.success and dag_response.data:
            graphs["dag"] = dag_response.data

        return MultiGraphResponse(
            success=True,
            data=graphs
        )

    # =========================================================================
    # Hybrid Program Graph (HPG)
    # =========================================================================

    def get_hpg(
        self,
        repo_path: str,
        component_id: str
    ) -> GraphResponse:
        """
        Get Hybrid Program Graph combining CFG and PDG.

        The HPG overlays data dependencies on the control flow graph.

        Args:
            repo_path: Repository path
            component_id: Function or method ID

        Returns:
            GraphResponse containing the HPG
        """
        ir = self.get_ir(repo_path)
        if not ir:
            ir = self.parse_repository(repo_path)

        func_ir = ir.functions.get(component_id)
        if not func_ir:
            return GraphResponse(
                success=False,
                message=f"Function not found: {component_id}"
            )

        try:
            # Build CFG
            cfg = build_cfg(func_ir)

            # Build PDG
            pdg = build_pdg(func_ir)

            # Combine: use CFG nodes/edges as base, add PDG data dependency edges
            hpg_nodes = cfg.nodes.copy()
            hpg_edges = cfg.edges.copy()

            # Add data dependency edges from PDG
            edge_id_offset = len(hpg_edges)
            for pdg_edge in pdg.edges:
                if pdg_edge.type == "data":
                    # Map PDG node IDs to CFG node IDs if possible
                    # For simplicity, we'll include PDG edges directly
                    new_edge = pdg_edge.model_copy()
                    new_edge.id = f"hpg_edge_{edge_id_offset}"
                    edge_id_offset += 1
                    hpg_edges.append(new_edge)

            hpg = Graph(
                id=f"hpg_{component_id}",
                name=f"HPG: {func_ir.name}",
                type="hpg",
                nodes=hpg_nodes,
                edges=hpg_edges,
                component_id=component_id,
                component_name=func_ir.name,
                file_path=func_ir.file_path,
                metadata={
                    "cfg_nodes": len(cfg.nodes),
                    "cfg_edges": len(cfg.edges),
                    "pdg_data_edges": sum(1 for e in pdg.edges if e.type == "data")
                }
            )

            return GraphResponse(success=True, data=hpg)
        except Exception as e:
            logger.error(f"Error building HPG: {e}")
            return GraphResponse(
                success=False,
                message=f"Error building HPG: {str(e)}"
            )


# Global service instance
_service: Optional[GraphService] = None


def get_graph_service() -> GraphService:
    """Get or create the global GraphService instance"""
    global _service
    if _service is None:
        _service = GraphService()
    return _service


def initialize_service(cache_dir: Optional[str] = None) -> GraphService:
    """Initialize the global service with custom settings"""
    global _service
    _service = GraphService(cache_dir=cache_dir)
    return _service
