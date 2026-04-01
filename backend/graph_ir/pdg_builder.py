"""
Program Dependency Graph (PDG) Builder

This module builds Program Dependency Graphs from the IR representation.
A PDG shows data dependencies (def-use chains) and control dependencies.
"""

from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from .models import (
    FunctionIR, IRStatement, StatementType, Variable,
    Graph, GraphNode, GraphEdge, DependencyType
)


@dataclass
class DefUseInfo:
    """Tracks definition and use information for a variable"""
    name: str
    definitions: List[str] = field(default_factory=list)  # Statement IDs that define this var
    uses: List[str] = field(default_factory=list)  # Statement IDs that use this var


@dataclass
class PDGNode:
    """Internal PDG node representation"""
    id: str
    statement: Optional[IRStatement] = None
    node_type: str = "statement"  # entry, parameter, statement, return
    label: str = ""
    line: Optional[int] = None
    code: str = ""

    # Variables defined and used by this node
    definitions: Set[str] = field(default_factory=set)
    uses: Set[str] = field(default_factory=set)


@dataclass
class PDGEdge:
    """Internal PDG edge representation"""
    source: str
    target: str
    dependency_type: DependencyType
    variable: Optional[str] = None  # For data dependencies


class PDGBuilder:
    """
    Builds Program Dependency Graph from FunctionIR.

    The PDG has two types of edges:
    1. Data Dependencies: Variable definition -> Variable use
    2. Control Dependencies: Branch statement -> Statements controlled by it

    Nodes represent:
    - Function entry
    - Parameters
    - Statements
    - Return statements
    """

    def __init__(self):
        self.nodes: Dict[str, PDGNode] = {}
        self.edges: List[PDGEdge] = []
        self.entry_id: str = ""
        self._node_counter = 0

        # Def-use analysis
        self.var_info: Dict[str, DefUseInfo] = defaultdict(
            lambda: DefUseInfo(name="")
        )

        # Control dependency tracking
        self.control_stack: List[str] = []  # Stack of branch statement IDs

    def _new_node_id(self) -> str:
        """Generate a new node ID"""
        self._node_counter += 1
        return f"pdg_node_{self._node_counter}"

    def _create_node(
        self,
        node_type: str,
        label: str,
        statement: Optional[IRStatement] = None,
        line: Optional[int] = None,
        code: str = ""
    ) -> PDGNode:
        """Create a new PDG node"""
        node_id = self._new_node_id()

        definitions = set()
        uses = set()

        if statement:
            definitions = {v.name for v in statement.definitions}
            uses = {v.name for v in statement.uses}

        node = PDGNode(
            id=node_id,
            statement=statement,
            node_type=node_type,
            label=label,
            line=line or (statement.line if statement else None),
            code=code or (statement.code if statement else ""),
            definitions=definitions,
            uses=uses
        )
        self.nodes[node_id] = node
        return node

    def _add_data_dependency(self, from_id: str, to_id: str, variable: str):
        """Add a data dependency edge"""
        self.edges.append(PDGEdge(
            source=from_id,
            target=to_id,
            dependency_type=DependencyType.DATA,
            variable=variable
        ))

    def _add_control_dependency(self, from_id: str, to_id: str):
        """Add a control dependency edge"""
        self.edges.append(PDGEdge(
            source=from_id,
            target=to_id,
            dependency_type=DependencyType.CONTROL
        ))

    def _add_call_dependency(self, from_id: str, to_id: str):
        """Add a function call dependency edge"""
        self.edges.append(PDGEdge(
            source=from_id,
            target=to_id,
            dependency_type=DependencyType.CALL
        ))

    def build(self, func_ir: FunctionIR) -> Graph:
        """Build PDG from FunctionIR"""
        self.nodes = {}
        self.edges = []
        self._node_counter = 0
        self.var_info = defaultdict(lambda: DefUseInfo(name=""))
        self.control_stack = []

        # Create entry node
        entry = self._create_node(
            "entry",
            f"Entry: {func_ir.name}",
            line=func_ir.start_line,
            code=f"def {func_ir.name}(...)"
        )
        self.entry_id = entry.id

        # Create parameter nodes
        param_nodes = []
        for param in func_ir.parameters:
            param_node = self._create_node(
                "parameter",
                f"param: {param.name}",
                line=func_ir.start_line,
                code=param.name
            )
            param_node.definitions.add(param.name)

            # Entry -> Parameter (control dependency)
            self._add_control_dependency(entry.id, param_node.id)

            # Track parameter as defined
            self.var_info[param.name].name = param.name
            self.var_info[param.name].definitions.append(param_node.id)

            param_nodes.append(param_node)

        # Process all statements
        self._process_statements(func_ir.statements, entry.id)

        # Build data dependency edges based on def-use chains
        self._build_data_dependencies()

        return self._to_graph(func_ir)

    def _process_statements(
        self,
        statements: List[IRStatement],
        control_parent: str
    ):
        """Process statements and build PDG nodes"""
        for stmt in statements:
            # Skip synthetic statements
            if stmt.type in (StatementType.ELSE, StatementType.ELIF):
                continue

            # Create node for statement
            node = self._create_node(
                stmt.type.value,
                self._get_label(stmt),
                statement=stmt
            )

            # Add control dependency from current control parent
            self._add_control_dependency(control_parent, node.id)

            # Update def-use information
            for var in stmt.definitions:
                var_name = var.name
                self.var_info[var_name].name = var_name
                self.var_info[var_name].definitions.append(node.id)

            for var in stmt.uses:
                var_name = var.name
                self.var_info[var_name].name = var_name
                self.var_info[var_name].uses.append(node.id)

            # Add call dependencies
            for call in stmt.calls:
                call_node = self._create_node(
                    "call",
                    f"call: {call.name}",
                    line=call.line,
                    code=f"{call.name}(...)"
                )
                self._add_call_dependency(node.id, call_node.id)

                # Arguments create data dependencies
                for arg in call.args:
                    if arg and not arg.startswith("<") and not arg.startswith("'"):
                        self.var_info[arg].uses.append(call_node.id)

            # Handle branch statements - they control subsequent statements
            if stmt.type in (StatementType.IF, StatementType.FOR,
                            StatementType.WHILE, StatementType.TRY):
                # Statements in the body are control-dependent on this branch
                # This is simplified - in a full implementation we'd track
                # the actual nested structure
                pass

    def _build_data_dependencies(self):
        """Build data dependency edges from def-use information"""
        for var_name, info in self.var_info.items():
            if not info.definitions or not info.uses:
                continue

            # For each use, find reaching definitions
            # Simplified: connect all definitions to all uses
            # A full implementation would do reaching definitions analysis
            for def_node_id in info.definitions:
                for use_node_id in info.uses:
                    if def_node_id != use_node_id:
                        self._add_data_dependency(def_node_id, use_node_id, var_name)

    def _get_label(self, stmt: IRStatement) -> str:
        """Get a short label for a statement"""
        if stmt.type == StatementType.ASSIGNMENT:
            defs = [v.name for v in stmt.definitions]
            uses = [v.name for v in stmt.uses[:2]]
            if defs:
                return f"{', '.join(defs[:2])} = ..."
            return "assign"

        elif stmt.type == StatementType.RETURN:
            uses = [v.name for v in stmt.uses[:2]]
            if uses:
                return f"return {', '.join(uses)}"
            return "return"

        elif stmt.type == StatementType.IF:
            return f"if {stmt.condition or '...'}"[:30]

        elif stmt.type == StatementType.FOR:
            return f"for {stmt.condition or '...'}"[:30]

        elif stmt.type == StatementType.WHILE:
            return f"while {stmt.condition or '...'}"[:30]

        elif stmt.type == StatementType.CALL:
            if stmt.calls:
                return f"{stmt.calls[0].name}(...)"
            return "call"

        else:
            return stmt.type.value

    def _to_graph(self, func_ir: FunctionIR) -> Graph:
        """Convert internal representation to Graph output"""
        graph_nodes: List[GraphNode] = []
        graph_edges: List[GraphEdge] = []

        # Group nodes by type for layout
        entry_nodes = []
        param_nodes = []
        statement_nodes = []
        call_nodes = []
        return_nodes = []

        for node_id, node in self.nodes.items():
            if node.node_type == "entry":
                entry_nodes.append(node)
            elif node.node_type == "parameter":
                param_nodes.append(node)
            elif node.node_type == "return":
                return_nodes.append(node)
            elif node.node_type == "call":
                call_nodes.append(node)
            else:
                statement_nodes.append(node)

        # Layout: Entry at top, then params, then statements, calls on side, returns at bottom
        y_offset = 50

        # Entry node
        for node in entry_nodes:
            graph_nodes.append(GraphNode(
                id=node.id,
                label=node.label,
                type=node.node_type,
                x=300,
                y=y_offset,
                line=node.line,
                code=node.code,
                metadata={
                    "definitions": list(node.definitions),
                    "uses": list(node.uses)
                }
            ))
        y_offset += 80

        # Parameter nodes
        for i, node in enumerate(param_nodes):
            x = 100 + i * 120
            graph_nodes.append(GraphNode(
                id=node.id,
                label=node.label,
                type=node.node_type,
                x=x,
                y=y_offset,
                line=node.line,
                code=node.code,
                metadata={
                    "definitions": list(node.definitions),
                    "uses": list(node.uses)
                }
            ))
        if param_nodes:
            y_offset += 80

        # Statement nodes
        for i, node in enumerate(statement_nodes):
            row = i // 3
            col = i % 3
            x = 100 + col * 180
            y = y_offset + row * 70
            graph_nodes.append(GraphNode(
                id=node.id,
                label=node.label,
                type=node.node_type,
                x=x,
                y=y,
                line=node.line,
                code=node.code,
                metadata={
                    "definitions": list(node.definitions),
                    "uses": list(node.uses)
                }
            ))

        if statement_nodes:
            rows = (len(statement_nodes) + 2) // 3
            y_offset += rows * 70 + 30

        # Call nodes (on the right side)
        for i, node in enumerate(call_nodes):
            graph_nodes.append(GraphNode(
                id=node.id,
                label=node.label,
                type=node.node_type,
                x=500,
                y=200 + i * 60,
                line=node.line,
                code=node.code,
                metadata={
                    "definitions": list(node.definitions),
                    "uses": list(node.uses)
                }
            ))

        # Return nodes at bottom
        for i, node in enumerate(return_nodes):
            x = 200 + i * 150
            graph_nodes.append(GraphNode(
                id=node.id,
                label=node.label,
                type=node.node_type,
                x=x,
                y=y_offset,
                line=node.line,
                code=node.code,
                metadata={
                    "definitions": list(node.definitions),
                    "uses": list(node.uses)
                }
            ))

        # Create edges
        edge_counter = 0
        for edge in self.edges:
            edge_counter += 1

            label = None
            if edge.dependency_type == DependencyType.DATA and edge.variable:
                label = edge.variable

            graph_edges.append(GraphEdge(
                id=f"edge_{edge_counter}",
                source=edge.source,
                target=edge.target,
                type=edge.dependency_type.value,
                label=label,
                metadata={
                    "variable": edge.variable
                } if edge.variable else {}
            ))

        return Graph(
            id=f"pdg_{func_ir.id}",
            name=f"PDG: {func_ir.name}",
            type="pdg",
            nodes=graph_nodes,
            edges=graph_edges,
            component_id=func_ir.id,
            component_name=func_ir.name,
            file_path=func_ir.file_path,
            metadata={
                "function_name": func_ir.name,
                "start_line": func_ir.start_line,
                "end_line": func_ir.end_line,
                "parameters": [p.name for p in func_ir.parameters],
                "local_variables": func_ir.local_variables,
                "data_dependencies": sum(1 for e in self.edges if e.dependency_type == DependencyType.DATA),
                "control_dependencies": sum(1 for e in self.edges if e.dependency_type == DependencyType.CONTROL),
                "call_dependencies": sum(1 for e in self.edges if e.dependency_type == DependencyType.CALL)
            }
        )


class ReachingDefinitionsAnalysis:
    """
    Performs reaching definitions analysis for more accurate PDG construction.
    This determines which definitions can reach a given use.
    """

    def __init__(self, func_ir: FunctionIR):
        self.func_ir = func_ir
        self.statements = func_ir.statements

        # gen[s] = definitions generated by statement s
        self.gen: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)  # (var_name, stmt_id)

        # kill[s] = definitions killed by statement s
        self.kill: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)

        # in[s] = definitions reaching entry of s
        self.reach_in: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)

        # out[s] = definitions reaching exit of s
        self.reach_out: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)

        # All definitions for each variable
        self.all_defs: Dict[str, Set[str]] = defaultdict(set)  # var -> set of stmt_ids

    def analyze(self) -> Dict[str, Set[Tuple[str, str]]]:
        """
        Run reaching definitions analysis.
        Returns reach_in for each statement.
        """
        # First pass: compute gen and kill sets
        for stmt in self.statements:
            for var in stmt.definitions:
                self.gen[stmt.id].add((var.name, stmt.id))
                self.all_defs[var.name].add(stmt.id)

        # Compute kill sets
        for stmt in self.statements:
            for var in stmt.definitions:
                for def_id in self.all_defs[var.name]:
                    if def_id != stmt.id:
                        self.kill[stmt.id].add((var.name, def_id))

        # Iterative dataflow analysis (simplified - assumes straight-line code)
        # A full implementation would use CFG for predecessor/successor info
        changed = True
        while changed:
            changed = False
            current_in: Set[Tuple[str, str]] = set()

            for stmt in self.statements:
                old_out = self.reach_out[stmt.id].copy()

                # in[s] = union of out[predecessors]
                self.reach_in[stmt.id] = current_in.copy()

                # out[s] = gen[s] U (in[s] - kill[s])
                self.reach_out[stmt.id] = self.gen[stmt.id] | (
                    self.reach_in[stmt.id] - self.kill[stmt.id]
                )

                if self.reach_out[stmt.id] != old_out:
                    changed = True

                current_in = self.reach_out[stmt.id]

        return self.reach_in


def build_pdg(func_ir: FunctionIR) -> Graph:
    """Convenience function to build PDG"""
    builder = PDGBuilder()
    return builder.build(func_ir)


def build_pdg_with_reaching_defs(func_ir: FunctionIR) -> Graph:
    """Build PDG with reaching definitions analysis for more accurate data dependencies"""
    # Run reaching definitions analysis
    rd_analysis = ReachingDefinitionsAnalysis(func_ir)
    reaching_defs = rd_analysis.analyze()

    # Build PDG using reaching definitions
    builder = PDGBuilder()
    builder.nodes = {}
    builder.edges = []
    builder._node_counter = 0
    builder.var_info = defaultdict(lambda: DefUseInfo(name=""))

    # Create entry node
    entry = builder._create_node(
        "entry",
        f"Entry: {func_ir.name}",
        line=func_ir.start_line
    )
    builder.entry_id = entry.id

    # Create parameter nodes
    for param in func_ir.parameters:
        param_node = builder._create_node(
            "parameter",
            f"param: {param.name}",
            line=func_ir.start_line
        )
        param_node.definitions.add(param.name)
        builder._add_control_dependency(entry.id, param_node.id)
        builder.var_info[param.name].definitions.append(param_node.id)

    # Create statement nodes
    stmt_to_node: Dict[str, str] = {}
    for stmt in func_ir.statements:
        node = builder._create_node(
            stmt.type.value,
            builder._get_label(stmt),
            statement=stmt
        )
        stmt_to_node[stmt.id] = node.id

        # Control dependency
        builder._add_control_dependency(entry.id, node.id)

        # Track definitions
        for var in stmt.definitions:
            builder.var_info[var.name].definitions.append(node.id)

    # Build data dependencies using reaching definitions
    for stmt in func_ir.statements:
        node_id = stmt_to_node.get(stmt.id)
        if not node_id:
            continue

        for var in stmt.uses:
            # Get reaching definitions for this use
            for def_var, def_stmt_id in reaching_defs.get(stmt.id, set()):
                if def_var == var.name:
                    def_node_id = stmt_to_node.get(def_stmt_id)
                    if def_node_id and def_node_id != node_id:
                        builder._add_data_dependency(def_node_id, node_id, var.name)

    return builder._to_graph(func_ir)
