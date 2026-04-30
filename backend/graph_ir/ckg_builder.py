"""
Complete Knowledge Graph (CKG) Builder

This module builds a unified Program Knowledge Graph that combines all graph types:
- DAG: Repository-level dependencies (calls, imports, inheritance)
- CFG: Control flow within functions
- PDG: Data and control dependencies within functions
- HPG: Hybrid program graph
- Hierarchy: Module → Class → Function → Statement relationships

The CKG provides a comprehensive, queryable view of the entire codebase structure
at all abstraction levels using a NetworkX MultiDiGraph.
"""

from typing import Dict, List, Optional, Set, Any, Tuple
from collections import defaultdict
import networkx as nx
from pathlib import Path
import logging

from .models import (
    RepositoryIR, ModuleIR, ClassIR, FunctionIR, IRStatement,
    ComponentType, StatementType
)
from .cfg_builder import build_cfg
from .pdg_builder import build_pdg
from .dag_builder import build_dag

logger = logging.getLogger(__name__)


class CKGBuilder:
    """
    Builds a Complete Knowledge Graph combining all graph types.
    
    Node Types:
    - module: Source code files/modules
    - class: Class definitions
    - function: Function/method definitions
    - statement: Individual statements within functions
    - variable: Variables (optional, can be added)
    
    Edge Types:
    - hierarchy: Parent-child relationships (module→class→function→statement)
    - calls: Function/method invocations
    - imports: Module import dependencies
    - extends: Class inheritance
    - control_flow: CFG edges within functions
    - data_flow: PDG data dependencies
    - control_dependency: PDG control dependencies
    """
    
    def __init__(self):
        self.graph = nx.MultiDiGraph()
        self.ir: Optional[RepositoryIR] = None
        
        # Tracking for node/edge creation
        self.node_count_by_type: Dict[str, int] = defaultdict(int)
        self.edge_count_by_type: Dict[str, int] = defaultdict(int)
        
        # Node ID tracking to prevent duplicates
        self.added_nodes: Set[str] = set()
        
        # Name indexes for fast cross-referencing
        self.function_name_index: Dict[str, Set[str]] = defaultdict(set)
        self.class_name_index: Dict[str, Set[str]] = defaultdict(set)
        self.module_name_index: Dict[str, Set[str]] = defaultdict(set)
        
    def build(self, ir: RepositoryIR) -> nx.MultiDiGraph:
        """
        Build complete knowledge graph from RepositoryIR.
        
        Construction order:
        1. Add all hierarchy nodes (modules, classes, functions, statements)
        2. Add hierarchy edges connecting the tree
        3. Add DAG edges (calls, imports, inheritance)
        4. Add CFG edges (control flow within functions)
        5. Add PDG edges (data/control dependencies within functions)
        
        Args:
            ir: Repository intermediate representation
            
        Returns:
            NetworkX MultiDiGraph with comprehensive metadata
        """
        self.ir = ir
        self.graph.clear()
        self.added_nodes.clear()
        self.node_count_by_type.clear()
        self.edge_count_by_type.clear()
        self.function_name_index.clear()
        self.class_name_index.clear()
        self.module_name_index.clear()
        
        # Build name indexes used for cross-references across the repository
        self._build_name_indexes()
        
        logger.info(f"Building CKG for repository: {ir.root_path}")
        logger.info(f"IR contains: {len(ir.modules)} modules, {len(ir.classes)} classes, {len(ir.functions)} functions")
        
        # Check if IR is empty
        if len(ir.modules) == 0 and len(ir.classes) == 0 and len(ir.functions) == 0:
            logger.warning(f"⚠️  Empty IR - repository has no parseable components")
            logger.warning(f"   Root path: {ir.root_path}")
            # Return empty graph with metadata
            self.graph.graph['repo_path'] = ir.root_path
            self.graph.graph['node_counts'] = {}
            self.graph.graph['edge_counts'] = {}
            self.graph.graph['total_nodes'] = 0
            self.graph.graph['total_edges'] = 0
            logger.info(f"CKG built (empty): 0 nodes, 0 edges")
            return self.graph
        
        # Phase 1: Build hierarchical structure
        self._add_module_nodes()
        self._add_class_nodes()
        self._add_function_nodes()
        self._add_statement_nodes()
        
        # Phase 2: Add hierarchy edges
        self._add_hierarchy_edges()
        
        # Phase 3: Add semantic edges from DAG
        self._add_call_edges()
        self._add_import_edges()
        self._add_inheritance_edges()
        
        # Phase 4: Add intra-procedural edges (CFG + PDG)
        self._add_control_flow_edges()
        self._add_data_flow_edges()
        
        # Add graph-level metadata
        self.graph.graph['repo_path'] = ir.root_path
        self.graph.graph['node_counts'] = dict(self.node_count_by_type)
        self.graph.graph['edge_counts'] = dict(self.edge_count_by_type)
        self.graph.graph['total_nodes'] = self.graph.number_of_nodes()
        self.graph.graph['total_edges'] = self.graph.number_of_edges()
        
        logger.info(f"CKG built: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
        logger.info(f"Node distribution: {dict(self.node_count_by_type)}")
        logger.info(f"Edge distribution: {dict(self.edge_count_by_type)}")
        
        return self.graph

    def _build_name_indexes(self):
        """Build helper indexes for resolving names across modules, classes, and functions."""
        if not self.ir:
            return
        
        # Module name index (supports full and suffix matches)
        for module_id, module_ir in self.ir.modules.items():
            names: Set[str] = set()
            if getattr(module_ir, "module_name", None):
                mod_name = module_ir.module_name
                names.add(mod_name)
                parts = mod_name.split(".")
                # Add suffixes like "sub.package" if full name is "root.sub.package"
                for i in range(1, len(parts)):
                    suffix = ".".join(parts[i:])
                    names.add(suffix)
            # Also index by file stem where available
            file_path = getattr(module_ir, "file_path", None)
            if file_path:
                try:
                    stem = Path(file_path).stem
                    if stem:
                        names.add(stem)
                except Exception:
                    pass
            for name in names:
                key = name.lower()
                self.module_name_index[key].add(module_id)
        
        # Class name index (supports qualified and simple names)
        for class_id, class_ir in self.ir.classes.items():
            names: Set[str] = set()
            if getattr(class_ir, "name", None):
                names.add(class_ir.name)
            if getattr(class_ir, "qualified_name", None):
                qn = class_ir.qualified_name
                names.add(qn)
                parts = qn.split(".")
                if parts:
                    names.add(parts[-1])
            for name in names:
                key = name.lower()
                self.class_name_index[key].add(class_id)
        
        # Function / method name index (supports qualified, simple, and Class.method forms)
        for func_id, func_ir in self.ir.functions.items():
            names: Set[str] = set()
            if getattr(func_ir, "name", None):
                names.add(func_ir.name)
            if getattr(func_ir, "qualified_name", None):
                qn = func_ir.qualified_name
                names.add(qn)
                parts = qn.split(".")
                if parts:
                    names.add(parts[-1])
            # Class.method variant for methods
            parent_class_id = getattr(func_ir, "parent_class", None)
            if parent_class_id and parent_class_id in self.ir.classes and getattr(func_ir, "name", None):
                cls_ir = self.ir.classes[parent_class_id]
                if getattr(cls_ir, "name", None):
                    names.add(f"{cls_ir.name}.{func_ir.name}")
            for name in names:
                key = name.lower()
                self.function_name_index[key].add(func_id)
    
    def _add_node(self, node_id: str, node_type: str, **attrs):
        """Add node with metadata tracking"""
        if node_id not in self.added_nodes:
            self.graph.add_node(node_id, type=node_type, **attrs)
            self.added_nodes.add(node_id)
            self.node_count_by_type[node_type] += 1
    
    def _add_edge(self, source: str, target: str, edge_type: str, **attrs):
        """Add edge with type metadata tracking"""
        # Only add edge if both nodes exist
        if source in self.added_nodes and target in self.added_nodes:
            self.graph.add_edge(source, target, type=edge_type, **attrs)
            self.edge_count_by_type[edge_type] += 1
        else:
            logger.debug(f"Skipping edge {source} -> {target}: missing node(s)")
    
    # =========================================================================
    # Phase 1: Hierarchy Nodes
    # =========================================================================
    
    def _add_module_nodes(self):
        """
        Add module (file) nodes.
        
        Each module represents a source file with metadata:
        - id: module ID from IR
        - type: "module"
        - name: module name
        - file_path: absolute path to source file
        - imports: list of imported modules
        - function_count: number of functions in module
        - class_count: number of classes in module
        """
        logger.debug(f"Adding {len(self.ir.modules)} module nodes")
        
        for module_id, module_ir in self.ir.modules.items():
            self._add_node(
                node_id=module_id,
                node_type="module",
                name=module_ir.module_name,
                file_path=module_ir.file_path,
                qualified_name=module_ir.module_name,
                imports=[imp.module for imp in module_ir.imports],
                function_count=len(module_ir.functions),
                class_count=len(module_ir.classes),
                statement_count=len(module_ir.statements)
            )
    
    def _add_class_nodes(self):
        """
        Add class definition nodes.
        
        Metadata:
        - id: class ID from IR
        - type: "class"
        - name: class name
        - qualified_name: fully qualified class name
        - file_path: source file
        - line: definition line number
        - end_line: end line number
        - bases: base class names
        - method_count: number of methods
        - docstring: class documentation
        """
        logger.debug(f"Adding {len(self.ir.classes)} class nodes")
        
        for class_id, class_ir in self.ir.classes.items():
            self._add_node(
                node_id=class_id,
                node_type="class",
                name=class_ir.name,
                qualified_name=class_ir.qualified_name,
                file_path=class_ir.file_path,
                line=class_ir.start_line,
                end_line=class_ir.end_line,
                bases=class_ir.bases,
                method_count=len(class_ir.methods),
                docstring=class_ir.docstring,
                decorators=class_ir.decorators
            )
    
    def _add_function_nodes(self):
        """
        Add function/method definition nodes.
        
        Metadata:
        - id: function ID from IR
        - type: "function"
        - name: function name
        - qualified_name: fully qualified name
        - file_path: source file
        - line: definition line
        - end_line: end line
        - signature: function signature with parameters
        - return_annotation: return type annotation
        - is_method: whether this is a method
        - parent_class: parent class ID if method
        - docstring: function documentation
        - statement_count: number of statements in body
        """
        logger.debug(f"Adding {len(self.ir.functions)} function nodes")
        
        for func_id, func_ir in self.ir.functions.items():
            # Build signature string
            params = ", ".join([p.name for p in func_ir.parameters])
            signature = f"{func_ir.name}({params})"
            if func_ir.return_annotation:
                signature += f" -> {func_ir.return_annotation}"
            
            self._add_node(
                node_id=func_id,
                node_type="function",
                name=func_ir.name,
                qualified_name=func_ir.qualified_name,
                file_path=func_ir.file_path,
                line=func_ir.start_line,
                end_line=func_ir.end_line,
                signature=signature,
                return_annotation=func_ir.return_annotation,
                is_method=func_ir.type == ComponentType.METHOD,
                parent_class=func_ir.parent_class,
                docstring=func_ir.docstring,
                statement_count=len(func_ir.statements),
                decorators=func_ir.decorators,
                is_static=func_ir.is_static,
                is_classmethod=func_ir.is_classmethod,
                is_property=func_ir.is_property
            )
    
    def _add_statement_nodes(self):
        """
        Add statement nodes within functions.
        
        Metadata:
        - id: statement ID (function_id:stmt_id)
        - type: "statement"
        - statement_type: specific type (if, for, return, assignment, etc.)
        - line: source line number
        - end_line: end line number
        - code: source code snippet
        - definitions: variables defined in this statement
        - uses: variables used in this statement
        - is_branch: whether this is a branch point
        - is_loop_header: whether this is a loop header
        """
        logger.debug("Adding statement nodes from all functions")
        statement_count = 0
        
        for func_id, func_ir in self.ir.functions.items():
            for stmt in func_ir.statements:
                stmt_id = f"{func_id}:{stmt.id}"
                
                self._add_node(
                    node_id=stmt_id,
                    node_type="statement",
                    statement_type=stmt.type.value,
                    line=stmt.line,
                    end_line=stmt.end_line,
                    code=stmt.code[:100] if stmt.code else "",  # Truncate long code
                    definitions=[v.name for v in stmt.definitions],
                    uses=[v.name for v in stmt.uses],
                    is_branch=stmt.is_branch,
                    is_loop_header=stmt.is_loop_header,
                    parent_function=func_id
                )
                statement_count += 1
        
        logger.debug(f"Added {statement_count} statement nodes")
    
    # =========================================================================
    # Phase 2: Hierarchy Edges
    # =========================================================================
    
    def _add_hierarchy_edges(self):
        """
        Add hierarchy edges connecting parent-child relationships.
        
        Hierarchy structure:
        - module → class (classes defined in module)
        - module → function (module-level functions)
        - class → function (methods in class)
        - function → statement (statements in function body)
        """
        logger.debug("Adding hierarchy edges")
        
        # Module → Class edges
        for module_id, module_ir in self.ir.modules.items():
            for class_id in module_ir.classes:
                self._add_edge(module_id, class_id, "hierarchy", label="contains")
        
        # Module → Function edges (module-level functions)
        for module_id, module_ir in self.ir.modules.items():
            for func_id in module_ir.functions:
                func_ir = self.ir.functions.get(func_id)
                if func_ir and func_ir.type == ComponentType.FUNCTION:
                    self._add_edge(module_id, func_id, "hierarchy", label="contains")
        
        # Class → Method edges
        for class_id, class_ir in self.ir.classes.items():
            for method_id in class_ir.methods:
                self._add_edge(class_id, method_id, "hierarchy", label="contains")
        
        # Function → Statement edges
        for func_id, func_ir in self.ir.functions.items():
            for stmt in func_ir.statements:
                stmt_id = f"{func_id}:{stmt.id}"
                self._add_edge(func_id, stmt_id, "hierarchy", label="contains")
    
    # =========================================================================
    # Phase 3: Semantic Edges (DAG)
    # =========================================================================
    
    def _add_call_edges(self):
        """
        Add function call edges.
        
        These edges represent function invocations:
        - function → function (calls)
        - function → method (calls)
        - method → method (calls)
        
        Can also add statement-level call edges:
        - statement → function (call site)
        """
        logger.debug("Adding call edges")
        
        # Function-level calls
        for func_id, func_ir in self.ir.functions.items():
            for call in func_ir.calls:
                # Try to resolve the called function
                target_id = self._resolve_function_name(call.name)
                if target_id:
                    self._add_edge(
                        func_id, 
                        target_id, 
                        "calls",
                        label=call.name,
                        line=call.line,
                        is_method=call.is_method
                    )
                
                # Add statement-level call edge if we have line info
                if call.line:
                    # Find statement at this line
                    stmt_id = self._find_statement_at_line(func_id, call.line)
                    if stmt_id and target_id:
                        self._add_edge(
                            stmt_id,
                            target_id,
                            "calls",
                            label=call.name,
                            line=call.line
                        )
    
    def _add_import_edges(self):
        """
        Add import dependency edges.
        
        These edges show module import relationships:
        - module → module (imports)
        """
        logger.debug("Adding import edges")
        
        for module_id, module_ir in self.ir.modules.items():
            for imp in module_ir.imports:
                # Try to find imported module in our IR
                target_module_id = self._resolve_module_name(imp.module)
                if target_module_id:
                    self._add_edge(
                        module_id,
                        target_module_id,
                        "imports",
                        label=imp.module,
                        line=imp.line,
                        imported_names=imp.names,
                        alias=imp.alias
                    )
    
    def _add_inheritance_edges(self):
        """
        Add class inheritance edges.
        
        These edges show inheritance relationships:
        - class → class (extends/inherits from)
        """
        logger.debug("Adding inheritance edges")
        
        for class_id, class_ir in self.ir.classes.items():
            for base_name in class_ir.bases:
                # Try to resolve base class
                base_id = self._resolve_class_name(base_name)
                if base_id:
                    self._add_edge(
                        class_id,
                        base_id,
                        "extends",
                        label=base_name
                    )
    
    # =========================================================================
    # Phase 4: Intra-Procedural Edges (CFG + PDG)
    # =========================================================================
    
    def _add_control_flow_edges(self):
        """
        Add control flow edges within functions (from CFG).
        
        These edges show execution flow:
        - statement → statement (control flow)
        - Labeled with branch conditions (true/false) where applicable
        """
        logger.debug("Adding control flow edges from CFG")
        
        for func_id, func_ir in self.ir.functions.items():
            try:
                # Build CFG for this function
                cfg = build_cfg(func_ir)
                
                # Map CFG edges to statement nodes
                for edge in cfg.edges:
                    # CFG node IDs might be different from statement IDs
                    # We need to map them back to our statement nodes
                    source_stmt_id = self._map_cfg_node_to_statement(func_id, edge.source)
                    target_stmt_id = self._map_cfg_node_to_statement(func_id, edge.target)
                    
                    if source_stmt_id and target_stmt_id:
                        edge_label = edge.label or "next"
                        self._add_edge(
                            source_stmt_id,
                            target_stmt_id,
                            "control_flow",
                            label=edge_label,
                            cfg_edge_type=edge.type
                        )
            except Exception as e:
                logger.debug(f"Failed to add CFG edges for {func_id}: {e}")
    
    def _add_data_flow_edges(self):
        """
        Add data flow edges within functions (from PDG).
        
        These edges show data dependencies:
        - statement → statement (data flow)
        - Labeled with variable names that flow between statements
        """
        logger.debug("Adding data flow edges from PDG")
        
        for func_id, func_ir in self.ir.functions.items():
            try:
                # Build PDG for this function
                pdg = build_pdg(func_ir)
                
                # Map PDG edges to statement nodes
                for edge in pdg.edges:
                    if edge.type == "data":
                        source_stmt_id = self._map_pdg_node_to_statement(func_id, edge.source)
                        target_stmt_id = self._map_pdg_node_to_statement(func_id, edge.target)
                        if source_stmt_id and target_stmt_id:
                            self._add_edge(
                                source_stmt_id,
                                target_stmt_id,
                                "data_flow",
                                label=edge.label or "",
                                variable=edge.label
                            )
                    elif edge.type == "control":
                        # Also capture control dependencies to increase graph density
                        source_stmt_id = self._map_pdg_node_to_statement(func_id, edge.source)
                        target_stmt_id = self._map_pdg_node_to_statement(func_id, edge.target)
                        if source_stmt_id and target_stmt_id:
                            self._add_edge(
                                source_stmt_id,
                                target_stmt_id,
                                "control_dependency",
                                label=edge.label or ""
                            )
            except Exception as e:
                logger.debug(f"Failed to add PDG edges for {func_id}: {e}")
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _resolve_function_name(self, name: str) -> Optional[str]:
        """Resolve a function name to a function ID in the IR"""
        if not self.ir or not name:
            return None
        key = name.lower()
        # Direct index match
        ids = self.function_name_index.get(key)
        if ids:
            return sorted(ids)[0]
        # If dotted, also try the last segment (e.g., "module.func" → "func")
        if "." in name:
            short = name.split(".")[-1].lower()
            ids = self.function_name_index.get(short)
            if ids:
                return sorted(ids)[0]
        # Fallback to linear scan
        for func_id, func_ir in self.ir.functions.items():
            if func_ir.qualified_name == name or func_ir.name == name:
                return func_id
        return None
    
    def _resolve_module_name(self, name: str) -> Optional[str]:
        """Resolve a module name to a module ID in the IR"""
        if not self.ir or not name:
            return None
        key = name.lower()
        ids = self.module_name_index.get(key)
        if ids:
            return sorted(ids)[0]
        if "." in name:
            short = name.split(".")[-1].lower()
            ids = self.module_name_index.get(short)
            if ids:
                return sorted(ids)[0]
        # Fallback to linear scan
        for module_id, module_ir in self.ir.modules.items():
            if module_ir.module_name == name:
                return module_id
        return None
    
    def _resolve_class_name(self, name: str) -> Optional[str]:
        """Resolve a class name to a class ID in the IR"""
        if not self.ir or not name:
            return None
        key = name.lower()
        ids = self.class_name_index.get(key)
        if ids:
            return sorted(ids)[0]
        if "." in name:
            short = name.split(".")[-1].lower()
            ids = self.class_name_index.get(short)
            if ids:
                return sorted(ids)[0]
        # Fallback to linear scan
        for class_id, class_ir in self.ir.classes.items():
            if class_ir.qualified_name == name or class_ir.name == name:
                return class_id
        return None
    
    def _find_statement_at_line(self, func_id: str, line: int) -> Optional[str]:
        """Find statement ID at a specific line in a function"""
        func_ir = self.ir.functions.get(func_id)
        if not func_ir:
            return None
        
        for stmt in func_ir.statements:
            if stmt.line == line:
                return f"{func_id}:{stmt.id}"
        return None
    
    def _map_cfg_node_to_statement(self, func_id: str, cfg_node_id: str) -> Optional[str]:
        """Map a CFG node ID to a statement node ID"""
        # CFG nodes might have IDs like "entry", "exit", or statement IDs
        if cfg_node_id in ["entry", "exit"]:
            return None
        
        # Check if this is already a valid statement ID
        stmt_id = f"{func_id}:{cfg_node_id}"
        if stmt_id in self.added_nodes:
            return stmt_id
        
        # Try to match by finding the statement in function IR
        func_ir = self.ir.functions.get(func_id)
        if not func_ir:
            return None
        
        for stmt in func_ir.statements:
            if stmt.id == cfg_node_id:
                return f"{func_id}:{stmt.id}"
        
        return None
    
    def _map_pdg_node_to_statement(self, func_id: str, pdg_node_id: str) -> Optional[str]:
        """Map a PDG node ID to a statement node ID"""
        # Similar to CFG mapping
        if pdg_node_id in ["entry", "exit"] or pdg_node_id.startswith("param_"):
            return None
        
        stmt_id = f"{func_id}:{pdg_node_id}"
        if stmt_id in self.added_nodes:
            return stmt_id
        
        func_ir = self.ir.functions.get(func_id)
        if not func_ir:
            return None
        
        for stmt in func_ir.statements:
            if stmt.id == pdg_node_id:
                return f"{func_id}:{stmt.id}"
        
        return None


def build_ckg(ir: RepositoryIR) -> nx.MultiDiGraph:
    """
    Build a Complete Knowledge Graph from RepositoryIR.
    
    This is the main entry point for CKG construction. It creates a unified
    graph combining:
    - Hierarchy: module → class → function → statement
    - DAG: calls, imports, inheritance at repository level
    - CFG: control flow within functions
    - PDG: data/control dependencies within functions
    
    Args:
        ir: Repository intermediate representation
        
    Returns:
        NetworkX MultiDiGraph with comprehensive metadata
        
    Example:
        >>> from backend.graph_ir.parser import parse_repository
        >>> from backend.graph_ir.ckg_builder import build_ckg
        >>> 
        >>> ir = parse_repository("/path/to/repo")
        >>> ckg = build_ckg(ir)
        >>> 
        >>> # Query the graph
        >>> print(f"Total nodes: {ckg.number_of_nodes()}")
        >>> print(f"Total edges: {ckg.number_of_edges()}")
        >>> 
        >>> # Get all modules
        >>> modules = [n for n, d in ckg.nodes(data=True) if d['type'] == 'module']
        >>> 
        >>> # Find function calls
        >>> calls = [(u, v) for u, v, d in ckg.edges(data=True) if d['type'] == 'calls']
    """
    builder = CKGBuilder()
    return builder.build(ir)


# =============================================================================
# Utility Functions
# =============================================================================

def export_to_json(graph: nx.MultiDiGraph) -> Dict[str, Any]:
    """
    Export CKG to JSON format for frontend visualization.
    
    Output format:
    {
        "nodes": [
            {"id": "...", "label": "...", "type": "...", "metadata": {...}},
            ...
        ],
        "edges": [
            {"id": "...", "source": "...", "target": "...", "type": "...", "label": "...", "metadata": {...}},
            ...
        ],
        "stats": {
            "node_count": ...,
            "edge_count": ...,
            "node_types": {...},
            "edge_types": {...}
        }
    }
    
    Args:
        graph: NetworkX MultiDiGraph from build_ckg()
        
    Returns:
        Dictionary with nodes, edges, and statistics
    """
    nodes = []
    edges = []
    edge_id_counter = 0
    
    # Convert nodes
    for node_id, node_data in graph.nodes(data=True):
        node_dict = {
            "id": node_id,
            "label": node_data.get("name", node_id),
            "type": node_data.get("type", "unknown"),
            "metadata": {}
        }
        
        # Add all other attributes as metadata
        for key, value in node_data.items():
            if key not in ["name", "type"]:
                node_dict["metadata"][key] = value
        
        nodes.append(node_dict)
    
    # Convert edges (handle multi-edges)
    for source, target, edge_data in graph.edges(data=True):
        edge_dict = {
            "id": f"e{edge_id_counter}",
            "source": source,
            "target": target,
            "type": edge_data.get("type", "unknown"),
            "label": edge_data.get("label", ""),
            "metadata": {}
        }
        
        # Add all other attributes as metadata
        for key, value in edge_data.items():
            if key not in ["type", "label"]:
                edge_dict["metadata"][key] = value
        
        edges.append(edge_dict)
        edge_id_counter += 1
    
    # Calculate statistics
    node_type_counts = defaultdict(int)
    edge_type_counts = defaultdict(int)
    
    for node_data in nodes:
        node_type_counts[node_data["type"]] += 1
    
    for edge_data in edges:
        edge_type_counts[edge_data["type"]] += 1
    
    stats = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_types": dict(node_type_counts),
        "edge_types": dict(edge_type_counts),
        "repo_path": graph.graph.get("repo_path", "")
    }
    
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": stats
    }


def extract_subgraph(
    graph: nx.MultiDiGraph,
    node_id: str,
    k_hops: int = 1,
    edge_types: Optional[List[str]] = None,
    direction: str = "both"
) -> nx.MultiDiGraph:
    """
    Extract k-hop neighborhood subgraph around a node.
    
    Args:
        graph: Full CKG
        node_id: Center node ID
        k_hops: Number of hops to expand (default: 1)
        edge_types: Filter by edge types (e.g., ["calls", "hierarchy"])
                   If None, include all edge types
        direction: "in" (predecessors), "out" (successors), or "both" (default)
        
    Returns:
        Subgraph containing the neighborhood
        
    Example:
        >>> # Get 2-hop neighborhood of a function with only call edges
        >>> subgraph = extract_subgraph(ckg, "my_module.my_function", 
        ...                            k_hops=2, edge_types=["calls"])
    """
    if node_id not in graph:
        raise ValueError(f"Node {node_id} not found in graph")
    
    # Start with the center node
    nodes_to_include = {node_id}
    current_frontier = {node_id}
    
    # Expand k hops
    for _ in range(k_hops):
        next_frontier = set()
        
        for node in current_frontier:
            # Get neighbors based on direction
            if direction in ["out", "both"]:
                for successor in graph.successors(node):
                    # Check edge type filter
                    if edge_types is None:
                        next_frontier.add(successor)
                    else:
                        # Check if any edge matches the filter
                        for _, _, edge_data in graph.edges(node, successor, data=True):
                            if edge_data.get("type") in edge_types:
                                next_frontier.add(successor)
                                break
            
            if direction in ["in", "both"]:
                for predecessor in graph.predecessors(node):
                    if edge_types is None:
                        next_frontier.add(predecessor)
                    else:
                        for _, _, edge_data in graph.edges(predecessor, node, data=True):
                            if edge_data.get("type") in edge_types:
                                next_frontier.add(predecessor)
                                break
        
        nodes_to_include.update(next_frontier)
        current_frontier = next_frontier
    
    # Create subgraph with filtered edges
    subgraph = graph.subgraph(nodes_to_include).copy()
    
    # If edge_types filter is specified, remove non-matching edges
    if edge_types is not None:
        edges_to_remove = []
        for u, v, key, data in subgraph.edges(keys=True, data=True):
            if data.get("type") not in edge_types:
                edges_to_remove.append((u, v, key))
        
        for edge in edges_to_remove:
            subgraph.remove_edge(*edge)
    
    return subgraph


def bfs_traversal(
    graph: nx.MultiDiGraph,
    start_node: str,
    edge_types: Optional[List[str]] = None,
    max_depth: Optional[int] = None
) -> List[Tuple[str, int]]:
    """
    Breadth-first traversal of the graph.
    
    Args:
        graph: CKG
        start_node: Starting node ID
        edge_types: Filter by edge types (if None, use all)
        max_depth: Maximum depth to traverse (if None, traverse all)
        
    Returns:
        List of (node_id, depth) tuples in BFS order
    """
    if start_node not in graph:
        return []
    
    visited = set()
    queue = [(start_node, 0)]
    result = []
    
    while queue:
        node, depth = queue.pop(0)
        
        if node in visited:
            continue
        
        if max_depth is not None and depth > max_depth:
            continue
        
        visited.add(node)
        result.append((node, depth))
        
        # Add successors
        for successor in graph.successors(node):
            if successor not in visited:
                # Check edge type filter
                should_add = False
                if edge_types is None:
                    should_add = True
                else:
                    for _, _, edge_data in graph.edges(node, successor, data=True):
                        if edge_data.get("type") in edge_types:
                            should_add = True
                            break
                
                if should_add:
                    queue.append((successor, depth + 1))
    
    return result


def dfs_traversal(
    graph: nx.MultiDiGraph,
    start_node: str,
    edge_types: Optional[List[str]] = None,
    max_depth: Optional[int] = None
) -> List[Tuple[str, int]]:
    """
    Depth-first traversal of the graph.
    
    Args:
        graph: CKG
        start_node: Starting node ID
        edge_types: Filter by edge types (if None, use all)
        max_depth: Maximum depth to traverse (if None, traverse all)
        
    Returns:
        List of (node_id, depth) tuples in DFS order
    """
    if start_node not in graph:
        return []
    
    visited = set()
    result = []
    
    def dfs_visit(node: str, depth: int):
        if node in visited:
            return
        
        if max_depth is not None and depth > max_depth:
            return
        
        visited.add(node)
        result.append((node, depth))
        
        # Visit successors
        for successor in graph.successors(node):
            if successor not in visited:
                # Check edge type filter
                should_visit = False
                if edge_types is None:
                    should_visit = True
                else:
                    for _, _, edge_data in graph.edges(node, successor, data=True):
                        if edge_data.get("type") in edge_types:
                            should_visit = True
                            break
                
                if should_visit:
                    dfs_visit(successor, depth + 1)
    
    dfs_visit(start_node, 0)
    return result


def find_paths(
    graph: nx.MultiDiGraph,
    source: str,
    target: str,
    max_depth: int = 10,
    edge_types: Optional[List[str]] = None
) -> List[List[str]]:
    """
    Find all paths between source and target nodes.
    
    Args:
        graph: CKG
        source: Source node ID
        target: Target node ID
        max_depth: Maximum path length (default: 10)
        edge_types: Filter by edge types (if None, use all)
        
    Returns:
        List of paths (each path is a list of node IDs)
    """
    if source not in graph or target not in graph:
        return []
    
    # If edge_types is specified, create a filtered view
    if edge_types is not None:
        # Create edge filter function
        def edge_filter(u, v):
            for _, _, edge_data in graph.edges(u, v, data=True):
                if edge_data.get("type") in edge_types:
                    return True
            return False
        
        # Use filtered subgraph
        filtered_graph = nx.subgraph_view(graph, filter_edge=edge_filter)
    else:
        filtered_graph = graph
    
    # Find all simple paths up to max_depth
    try:
        paths = list(nx.all_simple_paths(filtered_graph, source, target, cutoff=max_depth))
        return paths
    except nx.NetworkXNoPath:
        return []


def dependency_resolution(
    graph: nx.MultiDiGraph,
    target_node: str,
    edge_types: Optional[List[str]] = None
) -> List[str]:
    """
    Find all transitive dependencies of a node.
    
    This performs a reverse topological traversal to find all nodes
    that the target node depends on (directly or transitively).
    
    Args:
        graph: CKG
        target_node: Node to find dependencies for
        edge_types: Edge types to follow (e.g., ["calls", "imports"])
                   If None, follows all edges
        
    Returns:
        List of node IDs that target_node depends on (topologically sorted)
    """
    if target_node not in graph:
        return []
    
    # Use DFS to find all reachable predecessors
    visited = set()
    dependencies = []
    
    def visit_deps(node: str):
        if node in visited:
            return
        visited.add(node)
        
        # Visit all predecessors first (reverse topological)
        for pred in graph.predecessors(node):
            # Check edge type filter
            should_visit = False
            if edge_types is None:
                should_visit = True
            else:
                for _, _, edge_data in graph.edges(pred, node, data=True):
                    if edge_data.get("type") in edge_types:
                        should_visit = True
                        break
            
            if should_visit and pred not in visited:
                visit_deps(pred)
        
        dependencies.append(node)
    
    visit_deps(target_node)
    
    # Remove the target node itself from the result
    dependencies.remove(target_node)
    
    return dependencies


def topological_sort_subgraph(
    graph: nx.MultiDiGraph,
    nodes: Optional[Set[str]] = None
) -> List[str]:
    """
    Perform topological sort on a subgraph (or full graph if nodes=None).
    
    Only works on DAG portions of the graph. Will raise exception if cycles exist.
    
    Args:
        graph: CKG
        nodes: Set of node IDs to sort (if None, sort entire graph)
        
    Returns:
        List of node IDs in topological order
        
    Raises:
        NetworkXError: If graph contains cycles
    """
    if nodes is not None:
        subgraph = graph.subgraph(nodes)
    else:
        subgraph = graph
    
    try:
        return list(nx.topological_sort(subgraph))
    except nx.NetworkXError as e:
        logger.warning(f"Topological sort failed (likely contains cycles): {e}")
        raise


def get_graph_statistics(graph: nx.MultiDiGraph) -> Dict[str, Any]:
    """
    Calculate comprehensive statistics about the CKG.
    
    Returns:
        Dictionary with various graph metrics
    """
    stats = {
        "total_nodes": graph.number_of_nodes(),
        "total_edges": graph.number_of_edges(),
        "node_types": graph.graph.get("node_counts", {}),
        "edge_types": graph.graph.get("edge_counts", {}),
        "repo_path": graph.graph.get("repo_path", "")
    }
    
    # Calculate degree statistics
    in_degrees = [d for n, d in graph.in_degree()]
    out_degrees = [d for n, d in graph.out_degree()]
    
    if in_degrees:
        stats["avg_in_degree"] = sum(in_degrees) / len(in_degrees)
        stats["max_in_degree"] = max(in_degrees)
    
    if out_degrees:
        stats["avg_out_degree"] = sum(out_degrees) / len(out_degrees)
        stats["max_out_degree"] = max(out_degrees)
    
    # Check if graph is a DAG (no cycles)
    try:
        stats["is_dag"] = nx.is_directed_acyclic_graph(graph)
    except:
        stats["is_dag"] = False
    
    # Count connected components
    try:
        stats["num_weakly_connected_components"] = nx.number_weakly_connected_components(graph)
    except:
        stats["num_weakly_connected_components"] = None
    
    return stats
