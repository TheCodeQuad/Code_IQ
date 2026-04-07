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

from backend.navigator.core.repository_parser import RepositoryParser as NavigatorRepositoryParser
from backend.models.code_component import CodeComponent

from .models import (
    RepositoryIR, FunctionIR, ClassIR, ModuleIR,
    Graph, GraphNode, GraphEdge, GraphResponse, MultiGraphResponse,
    ComponentInfo, ComponentType, GraphListResponse,
    ParseStatusResponse
)
from .parser import RepositoryParser, parse_repository, parse_file
from .cfg_builder import build_cfg, CFGBuilder
from .pdg_builder import build_pdg, build_pdg_with_reaching_defs, PDGBuilder
from .hpg_builder import build_hpg
from .dag_builder import (
    build_dag, build_file_dag, build_neighborhood_dag,
    get_dependencies_dict, DAGBuilder
)
from .multilang_ir_adapter import function_ir_from_code_component

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
        self._components_cache: Dict[str, Dict[str, CodeComponent]] = {}
        self._cache_lock = Lock()
        self._parse_timestamps: Dict[str, datetime] = {}
        self._parse_errors: Dict[str, List[str]] = {}

        self._components_timestamps: Dict[str, datetime] = {}
        self._components_errors: Dict[str, List[str]] = {}

        # On-demand synthesized FunctionIR objects for non-Python languages.
        self._synth_function_cache: Dict[str, Dict[str, FunctionIR]] = {}

        # Cache directory for persisted IR
        self.cache_dir = cache_dir or os.path.join(
            os.path.dirname(__file__), ".cache"
        )
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_key(self, repo_path: str) -> str:
        """Generate cache key for a repository"""
        # Normalize paths so that Windows drive-letter casing and separator
        # differences (e.g., C:/... vs c:\...) do not create different caches.
        abs_path = os.path.abspath(repo_path)
        normalized = os.path.normcase(os.path.normpath(abs_path))
        return hashlib.md5(normalized.encode()).hexdigest()

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

    # =========================================================================
    # Navigator (multi-language) Component IR
    # =========================================================================

    def parse_repository_components(self, repo_path: str, force: bool = False) -> Dict[str, CodeComponent]:
        """Parse a repository with Navigator to extract multi-language components.

        Navigator builds a repository-wide component IR (functions/classes/methods/etc.)
        across multiple languages. This IR is used for component listing and DAG graphs.
        """
        cache_key = self._get_cache_key(repo_path)
        with self._cache_lock:
            if not force and cache_key in self._components_cache:
                return self._components_cache[cache_key]

        try:
            parser = NavigatorRepositoryParser(repo_path)
            components = parser.parse()  # Dict[str, CodeComponent]

            with self._cache_lock:
                self._components_cache[cache_key] = components
                self._components_timestamps[cache_key] = datetime.now()
                self._components_errors[cache_key] = []

            return components
        except Exception as e:
            logger.error(f"Error parsing repository components (navigator): {e}")
            with self._cache_lock:
                self._components_cache.pop(cache_key, None)
                self._components_timestamps[cache_key] = datetime.now()
                self._components_errors[cache_key] = [str(e)]
            raise

    def get_components(self, repo_path: str) -> Optional[Dict[str, CodeComponent]]:
        cache_key = self._get_cache_key(repo_path)
        with self._cache_lock:
            return self._components_cache.get(cache_key)

    def parse_file(self, file_path: str) -> RepositoryIR:
        """Parse a single file"""
        return parse_file(file_path)

    def get_parse_status(self, repo_path: str) -> ParseStatusResponse:
        """Get parsing status for a repository"""
        cache_key = self._get_cache_key(repo_path)

        with self._cache_lock:
            components = self._components_cache.get(cache_key)
            if components is not None:
                timestamp = self._components_timestamps.get(cache_key)
                errors = self._components_errors.get(cache_key, [])

                # Navigator component types are strings.
                class_count = sum(1 for c in components.values() if getattr(c.type, "value", c.type) == "class")
                function_like = {"function", "arrow_function", "method", "constructor"}
                function_count = sum(
                    1
                    for c in components.values()
                    if getattr(c.type, "value", c.type) in function_like
                )
                file_count = len({c.location.file_path for c in components.values() if getattr(c, "location", None)})

                return ParseStatusResponse(
                    success=True,
                    is_parsed=True,
                    file_count=file_count,
                    function_count=function_count,
                    class_count=class_count,
                    last_parsed=timestamp.isoformat() if timestamp else None,
                    errors=errors,
                )

            if cache_key not in self._ir_cache:
                return ParseStatusResponse(success=True, is_parsed=False)

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
                errors=errors,
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
                self._components_cache.pop(cache_key, None)
                self._components_timestamps.pop(cache_key, None)
                self._components_errors.pop(cache_key, None)
                self._synth_function_cache.pop(cache_key, None)
            else:
                self._ir_cache.clear()
                self._parse_timestamps.clear()
                self._parse_errors.clear()
                self._components_cache.clear()
                self._components_timestamps.clear()
                self._components_errors.clear()
                self._synth_function_cache.clear()

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
        # Prefer Navigator multi-language components.
        comps = self.get_components(repo_path)
        if comps is None:
            try:
                comps = self.parse_repository_components(repo_path)
            except Exception:
                comps = None

        components: List[ComponentInfo] = []

        if comps is not None:
            from .models import ComponentType as IRComponentType

            allowed_raw_types = {"class", "function", "arrow_function", "method", "constructor"}

            def map_type(raw: str) -> IRComponentType:
                if raw == "class":
                    return IRComponentType.CLASS
                if raw in ("method", "constructor"):
                    return IRComponentType.METHOD
                return IRComponentType.FUNCTION

            for comp in comps.values():
                raw_type = getattr(comp.type, "value", comp.type)

                # Only surface core components for graph browsing.
                if raw_type not in allowed_raw_types:
                    continue
                mapped_type = map_type(raw_type)

                if component_type and mapped_type.value != component_type:
                    continue

                comp_file_path = comp.location.file_path
                if file_path and comp_file_path != file_path:
                    continue

                parent_class = None
                if mapped_type == IRComponentType.METHOD:
                    parts = str(comp.id).split(".")
                    if len(parts) >= 3:
                        parent_class = parts[-2]

                components.append(ComponentInfo(
                    id=comp.id,
                    name=comp.name,
                    type=mapped_type,
                    file_path=comp_file_path,
                    start_line=comp.location.start_line,
                    end_line=comp.location.end_line,
                    parent_class=parent_class,
                ))
        else:
            # Fallback: Python-only IR
            ir = self.get_ir(repo_path)
            if not ir:
                ir = self.parse_repository(repo_path)

            # Add functions
            for func_id, func_ir in ir.functions.items():
                if file_path and func_ir.file_path != file_path:
                    continue
                if component_type and func_ir.type.value != component_type:
                    continue

                components.append(ComponentInfo(
                    id=func_ir.qualified_name,
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
                        id=class_ir.qualified_name,
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

    def _resolve_function_ir(self, repo_path: str, component_id: str) -> Optional[FunctionIR]:
        """Resolve a function by graph-ir id or by qualified_name (navigator-style id)."""
        ir = self.get_ir(repo_path)
        if not ir:
            ir = self.parse_repository(repo_path)

        func_ir = ir.functions.get(component_id)
        if func_ir:
            return func_ir

        for candidate in ir.functions.values():
            if candidate.qualified_name == component_id:
                return candidate

        # If the component exists in Navigator IR (multi-language), synthesize a FunctionIR.
        cache_key = self._get_cache_key(repo_path)
        with self._cache_lock:
            existing = self._synth_function_cache.get(cache_key, {}).get(component_id)
            if existing:
                return existing

        comps = self.get_components(repo_path)
        if comps is None:
            try:
                comps = self.parse_repository_components(repo_path)
            except Exception:
                comps = None

        if comps and component_id in comps:
            comp = comps[component_id]
            lang = (getattr(comp, "language", "python") or "python").lower()
            raw_type = getattr(comp.type, "value", comp.type)
            if raw_type not in ("function", "arrow_function", "method", "constructor"):
                return None

            # Synthesize on demand.
            try:
                func = function_ir_from_code_component(comp)
            except Exception as e:
                logger.error(f"Error synthesizing FunctionIR for {component_id} ({lang}): {e}")
                return None

            with self._cache_lock:
                self._synth_function_cache.setdefault(cache_key, {})[component_id] = func
            return func

        return None

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

        # Also allow lookup by qualified_name (navigator-style ids)
        for func in ir.functions.values():
            if func.qualified_name == component_id:
                return func
        for cls in ir.classes.values():
            if cls.qualified_name == component_id:
                return cls
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
        func_ir = self._resolve_function_ir(repo_path, component_id)
        if not func_ir:
            comps = self.get_components(repo_path)
            if comps and component_id in comps:
                lang = getattr(comps[component_id], "language", "unknown")
                return GraphResponse(
                    success=False,
                    message=f"CFG is only available for Python components (selected: {lang})",
                )
            return GraphResponse(success=False, message=f"Function not found: {component_id}")

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
        func_ir = self._resolve_function_ir(repo_path, component_id)
        if not func_ir:
            comps = self.get_components(repo_path)
            if comps and component_id in comps:
                lang = getattr(comps[component_id], "language", "unknown")
                return GraphResponse(
                    success=False,
                    message=f"PDG is only available for Python components (selected: {lang})",
                )
            return GraphResponse(success=False, message=f"Function not found: {component_id}")

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
        # Prefer Navigator multi-language components for DAG.
        components = self.get_components(repo_path)
        if components is None:
            components = self.parse_repository_components(repo_path)

        try:
            allowed_raw_types = {"class", "function", "arrow_function", "method", "constructor"}

            # Filter nodes
            if file_path:
                selected_ids = {
                    cid for cid, comp in components.items()
                    if comp.location.file_path == file_path
                }
            else:
                selected_ids = set(components.keys())

            # Keep DAG focused on callable/structural components.
            selected_ids = {
                cid
                for cid in selected_ids
                if getattr(components[cid].type, "value", components[cid].type) in allowed_raw_types
            }

            # Build reverse adjacency for neighborhood expansion
            dependents_by_dep: Dict[str, List[str]] = {}
            for cid, comp in components.items():
                raw_type = getattr(comp.type, "value", comp.type)
                if raw_type not in allowed_raw_types:
                    continue
                for dep in comp.depends_on:
                    dependents_by_dep.setdefault(dep, []).append(cid)

            if component_id:
                # Neighborhood expansion in both directions (dependencies + dependents)
                frontier = {component_id}
                neighborhood = {component_id}
                for _ in range(max(neighborhood_depth, 1)):
                    next_frontier: Set[str] = set()
                    for nid in frontier:
                        comp = components.get(nid)
                        if comp:
                            # Only follow edges to allowed component types.
                            for dep in comp.depends_on:
                                if dep in components and getattr(components[dep].type, "value", components[dep].type) in allowed_raw_types:
                                    next_frontier.add(dep)
                        next_frontier.update(dependents_by_dep.get(nid, []))
                    next_frontier -= neighborhood
                    neighborhood |= next_frontier
                    frontier = next_frontier
                    if not frontier:
                        break
                selected_ids &= neighborhood

            # Ensure we include any dependencies that are referenced but not present
            # as components (create placeholder nodes so edges don't dangle).
            placeholder_nodes: Dict[str, GraphNode] = {}
            for cid in list(selected_ids):
                comp = components.get(cid)
                if not comp:
                    continue
                for dep in comp.depends_on:
                    if dep not in selected_ids and dep not in components:
                        placeholder_nodes[dep] = GraphNode(
                            id=dep,
                            label=dep,
                            type="module",
                        )

            # Nodes
            graph_nodes: List[GraphNode] = []
            i = 0
            for cid in sorted(selected_ids):
                comp = components.get(cid)
                if not comp:
                    continue
                raw_type = getattr(comp.type, "value", comp.type)
                node_type = raw_type if raw_type in ("function", "method", "class", "module") else "function"
                graph_nodes.append(
                    GraphNode(
                        id=cid,
                        label=comp.name or cid,
                        type=node_type,
                        x=100 + (i % 4) * 220,
                        y=60 + (i // 4) * 80,
                        line=comp.location.start_line,
                        code=comp.signature,
                        metadata={
                            "file_path": comp.location.file_path,
                            "language": comp.language,
                        },
                    )
                )
                i += 1

            graph_nodes.extend(placeholder_nodes.values())
            node_ids = {n.id for n in graph_nodes}

            # Edges
            graph_edges: List[GraphEdge] = []
            edge_counter = 0
            for cid in sorted(selected_ids):
                comp = components.get(cid)
                if not comp:
                    continue
                for dep in comp.depends_on:
                    if dep not in selected_ids and dep not in placeholder_nodes:
                        continue
                    if dep not in node_ids or cid not in node_ids:
                        continue
                    edge_counter += 1
                    graph_edges.append(
                        GraphEdge(
                            id=f"edge_{edge_counter}",
                            source=dep,
                            target=cid,
                            type="call",
                        )
                    )

            dag_graph = Graph(
                id=f"dag_{self._get_cache_key(repo_path)}",
                name="DAG: Repository Dependencies",
                type="dag",
                nodes=graph_nodes,
                edges=graph_edges,
                metadata={
                    "node_count": len(graph_nodes),
                    "edge_count": len(graph_edges),
                    "neighborhood_depth": neighborhood_depth if component_id else None,
                    "file_path": file_path,
                },
            )

            return GraphResponse(success=True, data=dag_graph)
        except Exception as e:
            logger.error(f"Error building DAG (navigator): {e}")
            return GraphResponse(success=False, message=f"Error building DAG: {str(e)}")

    def get_dag_dict(self, repo_path: str) -> Dict[str, List[str]]:
        """
        Get dependencies as simple dict (for backward compatibility).

        Returns:
            Dict mapping component names to their dependency names
        """
        components = self.get_components(repo_path)
        if components is not None:
            return {cid: list(comp.depends_on) for cid, comp in components.items()}

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
        func_ir = self._resolve_function_ir(repo_path, component_id)
        if not func_ir:
            comps = self.get_components(repo_path)
            if comps and component_id in comps:
                lang = getattr(comps[component_id], "language", "unknown")
                return GraphResponse(
                    success=False,
                    message=f"HPG is only available for Python components (selected: {lang})",
                )
            return GraphResponse(success=False, message=f"Function not found: {component_id}")

        try:
            hpg = build_hpg(func_ir)
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
