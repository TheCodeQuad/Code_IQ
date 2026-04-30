"""
Program Dependency Graph (PDG) Builder

This module builds Program Dependency Graphs from the IR representation.
A PDG shows data dependencies (def-use chains) and control dependencies.
"""

from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from .models import (
    FunctionIR, IRStatement, StatementType,
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

        # Methods that mutate their receiver (treat as defining the receiver)
        self._mutating_methods: Set[str] = {
            # list
            "append", "extend", "insert", "remove", "pop", "clear", "sort", "reverse",
            # dict
            "update", "setdefault",
            # set
            "add", "discard",
        }

    @staticmethod
    def _is_likely_variable_reference(value: str) -> bool:
        """Heuristic for whether a string looks like a variable reference.

        The IR call extractor may include literals (e.g. "'foo'"), <expr>, etc.
        We only want identifier-ish tokens here.
        """
        if not value:
            return False
        if value.startswith("<"):
            return False
        if value.startswith("'") or value.startswith('"'):
            return False
        # Allow dotted names from VariableVisitor (e.g., os.path)
        if "." in value:
            return all(part.isidentifier() for part in value.split("."))
        return value.isidentifier()

    def _collect_statement_uses(self, stmt: IRStatement) -> Set[str]:
        """Collect variable uses for a statement at statement granularity."""
        def normalize(name: str) -> str:
            # Reduce noise from attribute paths like `car.values` by treating them
            # as uses of the base variable (`car`) at statement granularity.
            if "." in name:
                base = name.split(".", 1)[0]
                if base.isidentifier():
                    return base
            return name

        uses_from_ast: Set[str] = {normalize(v.name) for v in stmt.uses}
        arg_uses: Set[str] = set()
        receiver_uses: Set[str] = set()
        callee_names: Set[str] = set()

        # Some uses may appear only inside call args in the simplified call extractor.
        # Also, the AST-level variable collector includes the callee identifier (e.g., `open`,
        # `os.path.join`, `obj.method`) as a "use"; that's usually not meaningful for
        # value-flow edges, so we remove callees but keep receiver/args.
        for call in stmt.calls:
            if call.name:
                callee_names.add(call.name)
            if call.module and call.name:
                callee_names.add(f"{call.module}.{call.name}")
            if call.receiver and call.name:
                callee_names.add(f"{call.receiver}.{call.name}")

            for arg in call.args:
                if self._is_likely_variable_reference(arg):
                    arg_uses.add(normalize(arg))
            if call.receiver and self._is_likely_variable_reference(call.receiver):
                receiver_uses.add(normalize(call.receiver))

        return (uses_from_ast - callee_names) | arg_uses | receiver_uses

    def _collect_statement_definitions(self, stmt: IRStatement) -> Set[str]:
        """Collect variable definitions for a statement at statement granularity.

        Includes explicit IR definitions and receiver mutations for common
        mutating methods (e.g., answers.append, result.append).
        """
        definitions: Set[str] = {v.name for v in stmt.definitions}

        for call in stmt.calls:
            if call.receiver and call.name in self._mutating_methods:
                # Only consider a simple identifier receiver at this abstraction level.
                if call.receiver.isidentifier():
                    definitions.add(call.receiver)

        return definitions

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

    def _add_data_dependency(self, from_id: str, to_id: str, variable: Optional[str]):
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

        # Track the most recent defining node for each variable name.
        last_definition: Dict[str, str] = {}

        # Create parameter nodes (definitions)
        for param in func_ir.parameters:
            param_node = self._create_node(
                "parameter",
                f"param: {param.name}",
                line=func_ir.start_line,
                code=param.name
            )
            param_node.definitions.add(param.name)
            self._add_control_dependency(entry.id, param_node.id)
            last_definition[param.name] = param_node.id

        # Create one node per statement (calls are merged into the statement node)
        # and build nested control dependencies using a simple line-range stack.
        stmt_to_node: Dict[str, str] = {}
        stmt_parent: Dict[str, str] = {}
        control_stack: List[Tuple[str, int, StatementType]] = []  # (parent_node_id, end_line, type)

        def pop_finished_blocks(current_line: int):
            while control_stack and current_line > control_stack[-1][1]:
                control_stack.pop()

        for stmt in func_ir.statements:
            if stmt.type in (StatementType.ELSE, StatementType.ELIF):
                continue

            pop_finished_blocks(stmt.line)
            parent_id = control_stack[-1][0] if control_stack else entry.id
            stmt_parent[stmt.id] = parent_id

            stmt_node = self._create_node(
                stmt.type.value,
                self._get_label(stmt),
                statement=stmt,
            )
            stmt_to_node[stmt.id] = stmt_node.id
            self._add_control_dependency(parent_id, stmt_node.id)

            # If this is a block header, push it so subsequent statements become control-dependent on it.
            if stmt.type in (StatementType.IF, StatementType.FOR, StatementType.WHILE, StatementType.TRY, StatementType.WITH):
                if stmt.end_line and stmt.end_line >= stmt.line:
                    control_stack.append((stmt_node.id, stmt.end_line, stmt.type))

        # Add direct data dependencies based on last definition (no transitive expansion).
        emitted: Set[Tuple[str, str, str]] = set()
        for stmt in func_ir.statements:
            node_id = stmt_to_node.get(stmt.id)
            if not node_id:
                continue

            # Route through condition/loop headers: a statement in a controlled region
            # depends on the immediate controlling predicate/header result.
            parent_id = stmt_parent.get(stmt.id)
            if parent_id and parent_id != entry.id and parent_id != node_id:
                parent_node = self.nodes.get(parent_id)
                parent_stmt_type = parent_node.statement.type if parent_node and parent_node.statement else None
                if parent_stmt_type in (StatementType.IF, StatementType.WHILE, StatementType.FOR):
                    key = (parent_id, node_id, "guard")
                    if key not in emitted:
                        emitted.add(key)
                        self._add_data_dependency(parent_id, node_id, "guard")

            uses = self._collect_statement_uses(stmt)
            for var_name in sorted(uses):
                def_node_id = last_definition.get(var_name)
                if not def_node_id:
                    # No local definition/parameter in this function; do not attach
                    # a data-source edge to Entry. Entry is control-only.
                    continue
                if def_node_id == node_id:
                    continue
                key = (def_node_id, node_id, var_name)
                if key in emitted:
                    continue
                emitted.add(key)
                self._add_data_dependency(def_node_id, node_id, var_name)

            for var_name in sorted(self._collect_statement_definitions(stmt)):
                last_definition[var_name] = node_id

        return self._to_graph(func_ir)

    def _get_label(self, stmt: IRStatement) -> str:
        """Get a short label for a statement"""
        if stmt.type == StatementType.ASSIGNMENT:
            defs = [v.name for v in stmt.definitions]
            if defs:
                if stmt.calls:
                    return f"{defs[0]} = {stmt.calls[0].name}(...)"[:30]
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
                call = stmt.calls[0]
                if call.receiver:
                    return f"{call.receiver}.{call.name}(...)"[:30]
                return f"{call.name}(...)"
            return "call"

        else:
            return stmt.type.value

    def _to_graph(self, func_ir: FunctionIR) -> Graph:
        """Convert internal representation to Graph output"""
        graph_nodes: List[GraphNode] = []
        graph_edges: List[GraphEdge] = []

        # Group nodes for layout
        entry_nodes: List[PDGNode] = []
        param_nodes: List[PDGNode] = []
        statement_nodes: List[PDGNode] = []

        for node in self.nodes.values():
            if node.node_type == "entry":
                entry_nodes.append(node)
            elif node.node_type == "parameter":
                param_nodes.append(node)
            else:
                statement_nodes.append(node)

        y_offset = 50

        # Entry at top
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
                    "uses": list(node.uses),
                },
            ))
        y_offset += 80

        # Parameters row
        for i, node in enumerate(param_nodes):
            graph_nodes.append(GraphNode(
                id=node.id,
                label=node.label,
                type=node.node_type,
                x=100 + i * 140,
                y=y_offset,
                line=node.line,
                code=node.code,
                metadata={
                    "definitions": list(node.definitions),
                    "uses": list(node.uses),
                },
            ))
        if param_nodes:
            y_offset += 80

        # Statements grid
        for i, node in enumerate(sorted(statement_nodes, key=lambda n: (n.line or 10**9, n.id))):
            row = i // 3
            col = i % 3
            graph_nodes.append(GraphNode(
                id=node.id,
                label=node.label,
                type=node.node_type,
                x=100 + col * 220,
                y=y_offset + row * 70,
                line=node.line,
                code=node.code,
                metadata={
                    "definitions": list(node.definitions),
                    "uses": list(node.uses),
                    **({"statement_id": node.statement.id} if node.statement else {}),
                },
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

    def __init__(self, func_ir: FunctionIR, param_def_ids: Optional[Dict[str, str]] = None):
        self.func_ir = func_ir
        self.statements = func_ir.statements

        # Optional: seed reaching definitions with parameter definitions.
        # Maps variable name -> pseudo-definition id.
        self.param_def_ids: Dict[str, str] = param_def_ids or {}

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
        # Seed all_defs with parameter pseudo-definitions so assignments will kill them.
        for var_name, def_id in self.param_def_ids.items():
            self.all_defs[var_name].add(def_id)

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
            current_in: Set[Tuple[str, str]] = {(var, def_id) for var, def_id in self.param_def_ids.items()}

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
    """Build PDG with reaching definitions analysis.

    Note: the current PDG implementation is statement-level and emits direct
    def→use dependencies using a "most recent definition" heuristic.
    For consistency, this entrypoint returns the same structure as `build_pdg`.
    """
    builder = PDGBuilder()
    return builder.build(func_ir)
