"""
Repository-Level DAG (Directed Acyclic Graph) Builder

This module builds a dependency graph showing relationships between
functions, classes, and files in a repository.
"""

from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import os

from .models import (
    RepositoryIR, FunctionIR, ClassIR, ModuleIR,
    Graph, GraphNode, GraphEdge, ComponentType
)


@dataclass
class DAGNode:
    """Internal DAG node representation"""
    id: str
    name: str
    qualified_name: str
    node_type: str  # function, class, method, module
    file_path: str
    line: Optional[int] = None

    # Dependencies
    depends_on: Set[str] = field(default_factory=set)  # IDs this node depends on
    depended_by: Set[str] = field(default_factory=set)  # IDs that depend on this


class DAGBuilder:
    """
    Builds repository-level Directed Acyclic Graph.

    The DAG shows:
    - Function/method dependencies (calls)
    - Class inheritance relationships
    - Import dependencies
    - Module dependencies
    """

    def __init__(self):
        self.nodes: Dict[str, DAGNode] = {}
        self.edges: List[Tuple[str, str, str]] = []  # (from, to, type)

        # Name resolution maps
        self.name_to_id: Dict[str, str] = {}  # qualified_name -> id
        self.short_name_to_ids: Dict[str, List[str]] = defaultdict(list)  # short_name -> [ids]

    def build(self, ir: RepositoryIR) -> Graph:
        """Build DAG from RepositoryIR"""
        self.nodes = {}
        self.edges = []
        self.name_to_id = {}
        self.short_name_to_ids = defaultdict(list)

        # First pass: create all nodes
        self._create_nodes(ir)

        # Second pass: resolve dependencies
        self._resolve_dependencies(ir)

        return self._to_graph(ir)

    def _create_nodes(self, ir: RepositoryIR):
        """Create DAG nodes for all components"""
        # Create function/method nodes
        for func_id, func_ir in ir.functions.items():
            node = DAGNode(
                id=func_id,
                name=func_ir.name,
                qualified_name=func_ir.qualified_name,
                node_type=func_ir.type.value,
                file_path=func_ir.file_path,
                line=func_ir.start_line
            )
            self.nodes[func_id] = node
            self.name_to_id[func_ir.qualified_name] = func_id
            self.short_name_to_ids[func_ir.name].append(func_id)

        # Create class nodes
        for class_id, class_ir in ir.classes.items():
            node = DAGNode(
                id=class_id,
                name=class_ir.name,
                qualified_name=class_ir.qualified_name,
                node_type="class",
                file_path=class_ir.file_path,
                line=class_ir.start_line
            )
            self.nodes[class_id] = node
            self.name_to_id[class_ir.qualified_name] = class_id
            self.short_name_to_ids[class_ir.name].append(class_id)

        # Create module nodes
        for module_id, module_ir in ir.modules.items():
            node = DAGNode(
                id=module_id,
                name=module_ir.module_name,
                qualified_name=module_ir.module_name,
                node_type="module",
                file_path=module_ir.file_path
            )
            self.nodes[module_id] = node
            self.name_to_id[module_ir.module_name] = module_id

    def _resolve_dependencies(self, ir: RepositoryIR):
        """Resolve and create dependency edges"""
        # Function call dependencies
        for func_id, func_ir in ir.functions.items():
            for call in func_ir.calls:
                target_id = self._resolve_call(call.name, call.receiver, func_ir, ir)
                if target_id and target_id != func_id:
                    self._add_dependency(func_id, target_id, "call")

        # Class inheritance dependencies
        for class_id, class_ir in ir.classes.items():
            for base in class_ir.bases:
                target_id = self._resolve_name(base, class_ir.file_path, ir)
                if target_id:
                    self._add_dependency(class_id, target_id, "inherits")

        # Import dependencies (module level)
        for module_id, module_ir in ir.modules.items():
            for imp in module_ir.imports:
                # Try to resolve import to a module in the repo
                target_id = self._resolve_import(imp.module, ir)
                if target_id:
                    self._add_dependency(module_id, target_id, "imports")

                # Also check for function/class imports
                for name in imp.names:
                    if name != "*":
                        full_name = f"{imp.module}.{name}" if imp.module else name
                        target_id = self.name_to_id.get(full_name)
                        if target_id:
                            self._add_dependency(module_id, target_id, "imports")

    def _resolve_call(
        self,
        call_name: str,
        receiver: Optional[str],
        func_ir: FunctionIR,
        ir: RepositoryIR
    ) -> Optional[str]:
        """Resolve a function call to a node ID"""
        # Try qualified name first
        if receiver:
            # Could be a method call on an object
            # Try to find the class
            class_name = self._get_type_of_variable(receiver, func_ir)
            if class_name:
                qualified = f"{class_name}.{call_name}"
                if qualified in self.name_to_id:
                    return self.name_to_id[qualified]

            # Try module.function
            qualified = f"{receiver}.{call_name}"
            if qualified in self.name_to_id:
                return self.name_to_id[qualified]

        # Try same module
        module_name = self._get_module_name(func_ir.file_path, ir)
        if module_name:
            qualified = f"{module_name}.{call_name}"
            if qualified in self.name_to_id:
                return self.name_to_id[qualified]

        # Try same class (for method calls within class)
        if func_ir.parent_class:
            qualified = f"{module_name}.{func_ir.parent_class}.{call_name}"
            if qualified in self.name_to_id:
                return self.name_to_id[qualified]

        # Try short name (might have multiple matches)
        if call_name in self.short_name_to_ids:
            candidates = self.short_name_to_ids[call_name]
            # Prefer same file
            for cand_id in candidates:
                if self.nodes[cand_id].file_path == func_ir.file_path:
                    return cand_id
            # Return first match
            if candidates:
                return candidates[0]

        return None

    def _get_type_of_variable(self, var_name: str, func_ir: FunctionIR) -> Optional[str]:
        """Try to infer the type of a variable (simplified)"""
        # Check if it's 'self' in a method
        if var_name == "self" and func_ir.parent_class:
            return func_ir.parent_class

        # Check parameter annotations
        for param in func_ir.parameters:
            if param.name == var_name and param.annotation:
                return param.annotation

        return None

    def _resolve_name(self, name: str, file_path: str, ir: RepositoryIR) -> Optional[str]:
        """Resolve a name (class, function) to a node ID"""
        # Try qualified name
        if name in self.name_to_id:
            return self.name_to_id[name]

        # Try with module prefix
        module_name = self._get_module_name(file_path, ir)
        if module_name:
            qualified = f"{module_name}.{name}"
            if qualified in self.name_to_id:
                return self.name_to_id[qualified]

        # Try short name
        if name in self.short_name_to_ids:
            candidates = self.short_name_to_ids[name]
            if candidates:
                return candidates[0]

        return None

    def _resolve_import(self, module_name: str, ir: RepositoryIR) -> Optional[str]:
        """Resolve an import to a module ID"""
        if module_name in self.name_to_id:
            return self.name_to_id[module_name]

        # Try partial match (e.g., 'backend.utils' vs 'utils')
        for mod_id, mod_ir in ir.modules.items():
            if mod_ir.module_name.endswith(module_name):
                return mod_id
            if module_name.endswith(mod_ir.module_name):
                return mod_id

        return None

    def _get_module_name(self, file_path: str, ir: RepositoryIR) -> Optional[str]:
        """Get module name for a file path"""
        module_id = ir.file_to_module.get(file_path)
        if module_id and module_id in ir.modules:
            return ir.modules[module_id].module_name
        return None

    def _add_dependency(self, from_id: str, to_id: str, dep_type: str):
        """Add a dependency edge"""
        if from_id in self.nodes and to_id in self.nodes:
            self.nodes[from_id].depends_on.add(to_id)
            self.nodes[to_id].depended_by.add(from_id)
            self.edges.append((from_id, to_id, dep_type))

    def _to_graph(self, ir: RepositoryIR) -> Graph:
        """Convert to Graph output format"""
        graph_nodes: List[GraphNode] = []
        graph_edges: List[GraphEdge] = []

        # Calculate layout using topological levels
        levels = self._calculate_levels()

        # Group nodes by file for better layout
        file_groups: Dict[str, List[DAGNode]] = defaultdict(list)
        for node in self.nodes.values():
            file_groups[node.file_path].append(node)

        # Layout nodes
        y_offset = 50
        for file_path, nodes in file_groups.items():
            # Sort by level within file
            nodes.sort(key=lambda n: levels.get(n.id, 0))

            for i, node in enumerate(nodes):
                level = levels.get(node.id, 0)
                x = 100 + (i % 4) * 180
                y = y_offset + (i // 4) * 70

                graph_nodes.append(GraphNode(
                    id=node.id,
                    label=node.name,
                    type=node.node_type,
                    x=x,
                    y=y,
                    line=node.line,
                    code=node.qualified_name,
                    metadata={
                        "file_path": node.file_path,
                        "qualified_name": node.qualified_name,
                        "depends_on_count": len(node.depends_on),
                        "depended_by_count": len(node.depended_by)
                    }
                ))

            y_offset += ((len(nodes) + 3) // 4) * 70 + 50

        # Create edges
        for i, (from_id, to_id, dep_type) in enumerate(self.edges):
            graph_edges.append(GraphEdge(
                id=f"dag_edge_{i}",
                source=from_id,
                target=to_id,
                type=dep_type,
                label=dep_type if dep_type != "call" else None
            ))

        return Graph(
            id="repository_dag",
            name="Repository Dependency Graph",
            type="dag",
            nodes=graph_nodes,
            edges=graph_edges,
            metadata={
                "total_functions": len(ir.functions),
                "total_classes": len(ir.classes),
                "total_modules": len(ir.modules),
                "total_dependencies": len(self.edges)
            }
        )

    def _calculate_levels(self) -> Dict[str, int]:
        """Calculate topological levels for layout"""
        levels: Dict[str, int] = {}
        visited: Set[str] = set()

        def dfs(node_id: str, depth: int):
            if node_id in visited:
                return
            visited.add(node_id)
            levels[node_id] = max(levels.get(node_id, 0), depth)

            node = self.nodes.get(node_id)
            if node:
                for dep_id in node.depends_on:
                    dfs(dep_id, depth + 1)

        # Start from nodes with no dependents (roots)
        roots = [n.id for n in self.nodes.values() if not n.depended_by]
        for root_id in roots:
            dfs(root_id, 0)

        # Handle any remaining nodes (cycles)
        for node_id in self.nodes:
            if node_id not in levels:
                levels[node_id] = 0

        return levels


class FileDAGBuilder:
    """
    Builds a DAG for a single file showing function/class dependencies.
    """

    def __init__(self):
        self.nodes: Dict[str, DAGNode] = {}
        self.edges: List[Tuple[str, str, str]] = []

    def build(self, ir: RepositoryIR, file_path: str) -> Graph:
        """Build DAG for a single file"""
        self.nodes = {}
        self.edges = []

        # Get module for this file
        module_id = ir.file_to_module.get(file_path)
        if not module_id:
            return Graph(
                id=f"dag_{file_path}",
                name=f"File DAG: {os.path.basename(file_path)}",
                type="dag",
                nodes=[],
                edges=[]
            )

        # Get all functions and classes in this file
        funcs_in_file = [
            (fid, fir) for fid, fir in ir.functions.items()
            if fir.file_path == file_path
        ]
        classes_in_file = [
            (cid, cir) for cid, cir in ir.classes.items()
            if cir.file_path == file_path
        ]

        # Create nodes
        name_to_id: Dict[str, str] = {}

        for func_id, func_ir in funcs_in_file:
            self.nodes[func_id] = DAGNode(
                id=func_id,
                name=func_ir.name,
                qualified_name=func_ir.qualified_name,
                node_type=func_ir.type.value,
                file_path=file_path,
                line=func_ir.start_line
            )
            name_to_id[func_ir.name] = func_id

        for class_id, class_ir in classes_in_file:
            self.nodes[class_id] = DAGNode(
                id=class_id,
                name=class_ir.name,
                qualified_name=class_ir.qualified_name,
                node_type="class",
                file_path=file_path,
                line=class_ir.start_line
            )
            name_to_id[class_ir.name] = class_id

        # Resolve internal dependencies
        for func_id, func_ir in funcs_in_file:
            for call in func_ir.calls:
                if call.name in name_to_id:
                    target_id = name_to_id[call.name]
                    if target_id != func_id:
                        self.edges.append((func_id, target_id, "call"))

        # Build graph
        graph_nodes: List[GraphNode] = []
        graph_edges: List[GraphEdge] = []

        # Sort nodes by line number
        sorted_nodes = sorted(self.nodes.values(), key=lambda n: n.line or 0)

        for i, node in enumerate(sorted_nodes):
            graph_nodes.append(GraphNode(
                id=node.id,
                label=node.name,
                type=node.node_type,
                x=150 + (i % 3) * 180,
                y=80 + (i // 3) * 80,
                line=node.line,
                code=node.qualified_name
            ))

        for i, (from_id, to_id, dep_type) in enumerate(self.edges):
            graph_edges.append(GraphEdge(
                id=f"edge_{i}",
                source=from_id,
                target=to_id,
                type=dep_type
            ))

        return Graph(
            id=f"dag_{file_path}",
            name=f"File Dependency Graph: {os.path.basename(file_path)}",
            type="dag",
            nodes=graph_nodes,
            edges=graph_edges,
            file_path=file_path
        )


class ComponentNeighborhoodDAG:
    """
    Builds a DAG showing a component and its immediate dependencies/dependents.
    """

    def build(
        self,
        ir: RepositoryIR,
        component_id: str,
        depth: int = 1
    ) -> Graph:
        """Build neighborhood DAG for a component"""
        full_dag_builder = DAGBuilder()
        full_dag_builder._create_nodes(ir)
        full_dag_builder._resolve_dependencies(ir)

        if component_id not in full_dag_builder.nodes:
            return Graph(
                id=f"neighborhood_{component_id}",
                name="Component Neighborhood",
                type="dag",
                nodes=[],
                edges=[]
            )

        # Collect neighborhood
        neighborhood: Set[str] = {component_id}
        frontier = {component_id}

        for _ in range(depth):
            new_frontier: Set[str] = set()
            for node_id in frontier:
                node = full_dag_builder.nodes.get(node_id)
                if node:
                    neighborhood.update(node.depends_on)
                    neighborhood.update(node.depended_by)
                    new_frontier.update(node.depends_on)
                    new_frontier.update(node.depended_by)
            frontier = new_frontier - neighborhood
            neighborhood.update(frontier)

        # Build subgraph
        graph_nodes: List[GraphNode] = []
        graph_edges: List[GraphEdge] = []

        center_node = full_dag_builder.nodes[component_id]

        # Layout: center node in middle, dependencies above, dependents below
        deps = center_node.depends_on & neighborhood
        dependents = center_node.depended_by & neighborhood
        others = neighborhood - deps - dependents - {component_id}

        y = 50
        # Dependencies (above)
        for i, dep_id in enumerate(deps):
            node = full_dag_builder.nodes[dep_id]
            graph_nodes.append(GraphNode(
                id=node.id,
                label=node.name,
                type="dependency",
                x=100 + (i % 4) * 150,
                y=y + (i // 4) * 60,
                line=node.line,
                code=node.qualified_name
            ))
        y += ((len(deps) + 3) // 4) * 60 + 40

        # Center node
        graph_nodes.append(GraphNode(
            id=center_node.id,
            label=center_node.name,
            type="selected",
            x=250,
            y=y,
            line=center_node.line,
            code=center_node.qualified_name
        ))
        y += 80

        # Dependents (below)
        for i, dep_id in enumerate(dependents):
            node = full_dag_builder.nodes[dep_id]
            graph_nodes.append(GraphNode(
                id=node.id,
                label=node.name,
                type="dependent",
                x=100 + (i % 4) * 150,
                y=y + (i // 4) * 60,
                line=node.line,
                code=node.qualified_name
            ))

        # Edges
        edge_count = 0
        for from_id, to_id, dep_type in full_dag_builder.edges:
            if from_id in neighborhood and to_id in neighborhood:
                edge_count += 1
                graph_edges.append(GraphEdge(
                    id=f"edge_{edge_count}",
                    source=from_id,
                    target=to_id,
                    type=dep_type
                ))

        return Graph(
            id=f"neighborhood_{component_id}",
            name=f"Neighborhood: {center_node.name}",
            type="dag",
            nodes=graph_nodes,
            edges=graph_edges,
            component_id=component_id,
            component_name=center_node.name,
            file_path=center_node.file_path
        )


def build_dag(ir: RepositoryIR) -> Graph:
    """Build repository-level DAG"""
    builder = DAGBuilder()
    return builder.build(ir)


def build_file_dag(ir: RepositoryIR, file_path: str) -> Graph:
    """Build DAG for a single file"""
    builder = FileDAGBuilder()
    return builder.build(ir, file_path)


def build_neighborhood_dag(ir: RepositoryIR, component_id: str, depth: int = 1) -> Graph:
    """Build neighborhood DAG for a component"""
    builder = ComponentNeighborhoodDAG()
    return builder.build(ir, component_id, depth)


def get_dependencies_dict(ir: RepositoryIR) -> Dict[str, List[str]]:
    """
    Get dependencies as a simple dict for API compatibility.
    Returns {component_name: [dependency_names]}
    """
    builder = DAGBuilder()
    builder._create_nodes(ir)
    builder._resolve_dependencies(ir)

    result: Dict[str, List[str]] = {}
    for node in builder.nodes.values():
        dep_names = []
        for dep_id in node.depends_on:
            dep_node = builder.nodes.get(dep_id)
            if dep_node:
                dep_names.append(dep_node.qualified_name)
        result[node.qualified_name] = dep_names

    return result
