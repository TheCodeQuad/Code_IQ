"""
Control Flow Graph (CFG) Builder

This module builds Control Flow Graphs from the IR representation.
A CFG shows all possible paths through a function during execution.
"""

import ast
import os
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from .models import (
    FunctionIR, IRStatement, StatementType,
    Graph, GraphNode, GraphEdge
)
from .label_utils import get_semantic_label, format_semantic_label


@dataclass
class CFGNode:
    """Internal CFG node representation"""
    id: str
    statement: Optional[IRStatement] = None
    node_type: str = "statement"  # entry, exit, statement, branch, merge
    label: str = ""
    line: Optional[int] = None
    code: str = ""

    # Successors
    successors: List[str] = field(default_factory=list)
    predecessors: List[str] = field(default_factory=list)

    # For branch nodes
    true_branch: Optional[str] = None
    false_branch: Optional[str] = None


class CFGBuilder:
    """
    Builds Control Flow Graph from FunctionIR.

    The CFG has:
    - Entry node: Function entry point
    - Exit node(s): Function exit points (return statements, end of function)
    - Basic blocks: Sequences of statements with single entry/exit
    - Branch nodes: if, while, for, try statements
    - Edges: Control flow between nodes (with labels for branches)
    """

    def __init__(self):
        self.nodes: Dict[str, CFGNode] = {}
        self.entry_id: str = ""
        self.exit_id: str = ""
        self._node_counter = 0
        # Branch nodes whose FALSE edge should fall through to the next statement node.
        self._pending_false_fallthrough: Set[str] = set()

    def _new_node_id(self) -> str:
        """Generate a new node ID"""
        self._node_counter += 1
        return f"cfg_node_{self._node_counter}"

    def _create_node(
        self,
        node_type: str,
        label: str,
        statement: Optional[IRStatement] = None,
        line: Optional[int] = None,
        code: str = ""
    ) -> CFGNode:
        """Create a new CFG node"""
        node_id = self._new_node_id()
        node = CFGNode(
            id=node_id,
            statement=statement,
            node_type=node_type,
            label=label,
            line=line or (statement.line if statement else None),
            code=code or (statement.code if statement else "")
        )
        self.nodes[node_id] = node
        return node

    def _add_edge(self, from_id: str, to_id: str, edge_type: str = "flow"):
        """Add an edge between nodes"""
        if from_id in self.nodes:
            if to_id not in self.nodes[from_id].successors:
                self.nodes[from_id].successors.append(to_id)
        if to_id in self.nodes:
            if from_id not in self.nodes[to_id].predecessors:
                self.nodes[to_id].predecessors.append(from_id)

    def build(self, func_ir: FunctionIR) -> Graph:
        """Build CFG from FunctionIR"""
        self.nodes = {}
        self._node_counter = 0
        self._pending_false_fallthrough = set()

        # Create entry and exit nodes
        entry = self._create_node(
            "entry",
            f"Entry: {func_ir.name}",
            line=func_ir.start_line,
            code=f"def {func_ir.name}(...):"
        )
        self.entry_id = entry.id

        exit_node = self._create_node(
            "exit",
            "Exit",
            line=func_ir.end_line,
            code="return"
        )
        self.exit_id = exit_node.id

        if not func_ir.statements:
            # Empty function
            self._add_edge(entry.id, exit_node.id)
        else:
            # Build CFG from statements
            last_nodes = self._process_statements(
                func_ir.statements,
                [entry.id],
                exit_node.id
            )

            if self._pending_false_fallthrough:
                for branch_id in list(self._pending_false_fallthrough):
                    if branch_id in self.nodes:
                        self.nodes[branch_id].false_branch = exit_node.id
                        self._add_edge(branch_id, exit_node.id)
                self._pending_false_fallthrough.clear()

            # Connect remaining nodes to exit
            for node_id in last_nodes:
                if node_id != exit_node.id:
                    self._add_edge(node_id, exit_node.id)

        return self._to_graph(func_ir)

    def _process_statements(
        self,
        statements: List[IRStatement],
        entry_points: List[str],
        exit_point: str,
        loop_continue: Optional[str] = None,
        loop_break: Optional[str] = None
    ) -> List[str]:
        """
        Process a list of statements and return the exit points.

        Args:
            statements: List of IR statements to process
            entry_points: Node IDs where control flows in
            exit_point: Node ID where control should flow out
            loop_continue: Node ID for continue statements (loop header)
            loop_break: Node ID for break statements (after loop)

        Returns:
            List of node IDs where control exits this block
        """
        if not statements:
            return entry_points

        current_entry = entry_points
        final_exits: List[str] = []

        i = 0
        while i < len(statements):
            stmt = statements[i]

            def _apply_pending_false_fallthrough(target_node_id: str):
                if not self._pending_false_fallthrough:
                    return
                for branch_id in list(self._pending_false_fallthrough):
                    if branch_id in current_entry:
                        self.nodes[branch_id].false_branch = target_node_id
                        self._pending_false_fallthrough.remove(branch_id)

            if stmt.type == StatementType.IF:
                # Find the complete if-elif-else chain
                if_chain, chain_end_line = self._collect_if_chain(statements, i)
                exits = self._process_if_chain(
                    if_chain, current_entry, exit_point,
                    loop_continue, loop_break
                )
                current_entry = exits
                # Skip statements that belong to this if/else chain (flattened IR)
                if chain_end_line is not None:
                    j = i
                    while j < len(statements) and statements[j].line <= chain_end_line:
                        j += 1
                    i = j
                else:
                    i += 1

            elif stmt.type in (StatementType.FOR, StatementType.WHILE):
                exits = self._process_loop(
                    stmt, statements, i, current_entry, exit_point
                )
                current_entry = exits
                i += 1

            elif stmt.type == StatementType.TRY:
                exits = self._process_try(
                    stmt, statements, i, current_entry, exit_point,
                    loop_continue, loop_break
                )
                current_entry = exits
                i += 1

            elif stmt.type == StatementType.RETURN:
                label = "return"
                code_str = (stmt.code or "").strip()
                if code_str.startswith("return"):
                    rest = code_str[len("return"):].strip()
                    if rest:
                        label = f"return {rest}"[:50]
                node = self._create_node(
                    "return",
                    label,
                    statement=stmt
                )
                _apply_pending_false_fallthrough(node.id)
                for ep in current_entry:
                    self._add_edge(ep, node.id)
                self._add_edge(node.id, self.exit_id)
                # After return, no more statements in this path
                current_entry = []
                i += 1

            elif stmt.type == StatementType.BREAK:
                if loop_break:
                    node = self._create_node("break", "break", statement=stmt)
                    _apply_pending_false_fallthrough(node.id)
                    for ep in current_entry:
                        self._add_edge(ep, node.id)
                    self._add_edge(node.id, loop_break)
                current_entry = []
                i += 1

            elif stmt.type == StatementType.CONTINUE:
                if loop_continue:
                    node = self._create_node("continue", "continue", statement=stmt)
                    _apply_pending_false_fallthrough(node.id)
                    for ep in current_entry:
                        self._add_edge(ep, node.id)
                    self._add_edge(node.id, loop_continue)
                current_entry = []
                i += 1

            elif stmt.type == StatementType.RAISE:
                code_str = (stmt.code or "").strip()
                if code_str.startswith("throw"):
                    label = code_str[:50]
                    node_type = "throw"
                else:
                    label = "raise"
                    node_type = "raise"

                node = self._create_node(node_type, label, statement=stmt)
                _apply_pending_false_fallthrough(node.id)
                for ep in current_entry:
                    self._add_edge(ep, node.id)
                # Raise exits to exit node (simplified - could go to exception handler)
                self._add_edge(node.id, self.exit_id)
                current_entry = []
                i += 1

            elif stmt.type in (StatementType.ELSE, StatementType.ELIF,
                              StatementType.EXCEPT, StatementType.FINALLY):
                # These are handled by their parent structures
                i += 1

            else:
                # Regular statement
                node = self._create_node(
                    "statement",
                    self._get_label(stmt),
                    statement=stmt
                )

                _apply_pending_false_fallthrough(node.id)

                for ep in current_entry:
                    self._add_edge(ep, node.id)
                current_entry = [node.id]
                i += 1

        return current_entry if current_entry else final_exits

    def _collect_if_chain(
        self, statements: List[IRStatement], start_idx: int
    ) -> Tuple[List[Tuple[IRStatement, List[IRStatement]]], Optional[int]]:
        """
        Collect if-elif-else chain starting at index.
        Returns list of (condition_stmt, body_statements) tuples.
        """
        chain: List[Tuple[IRStatement, List[IRStatement]]] = []
        i = start_idx
        current_stmt = statements[i]

        if current_stmt.type != StatementType.IF:
            return chain, None

        # Collect body of if
        if_body = self._collect_block_body(statements, i)
        chain.append((current_stmt, if_body))

        chain_end_line: Optional[int] = getattr(current_stmt, "end_line", None)

        # Optional else directly after the if body (multi-language IR may emit ELSE).
        # We'll scan forward until we pass the if's end_line (if present).
        j = i + 1
        while j < len(statements):
            s = statements[j]
            if chain_end_line is not None and s.line > chain_end_line + 1:
                break
            if s.type == StatementType.ELSE:
                else_body = self._collect_block_body(statements, j)
                chain.append((s, else_body))
                if getattr(s, "end_line", None) is not None:
                    chain_end_line = max(chain_end_line or s.end_line, s.end_line)
                break
            j += 1

        return chain, chain_end_line

    def _collect_block_body(
        self, statements: List[IRStatement], block_start_idx: int
    ) -> List[IRStatement]:
        """
        Collect statements that belong to a block (if/for/while body).
        This is simplified - in a real implementation we'd use indentation
        or the AST structure. Here we rely on the statement order from the parser.
        """
        header = statements[block_start_idx]
        end_line = getattr(header, "end_line", None)
        if end_line is None:
            return []

        body: List[IRStatement] = []
        j = block_start_idx + 1
        while j < len(statements):
            s = statements[j]
            if s.line > end_line:
                break

            # Do not include structural chain markers in the body.
            if s.type in (StatementType.ELSE, StatementType.ELIF, StatementType.EXCEPT, StatementType.FINALLY):
                break

            body.append(s)
            j += 1

        return body

    def _process_if_chain(
        self,
        if_chain: List[Tuple[IRStatement, List[IRStatement]]],
        entry_points: List[str],
        exit_point: str,
        loop_continue: Optional[str],
        loop_break: Optional[str]
    ) -> List[str]:
        """Process an if-elif-else chain"""
        if not if_chain:
            return entry_points

        # Get the if statement
        if_stmt = if_chain[0][0]

        # Create branch node
        branch = self._create_node(
            "branch",
            self._get_label(if_stmt),
            statement=if_stmt,
        )

        for ep in entry_points:
            self._add_edge(ep, branch.id)

        # TRUE branch body
        if_body = if_chain[0][1] if if_chain else []
        succ_before = set(self.nodes[branch.id].successors)
        if if_body:
            true_exits = self._process_statements(
                if_body,
                [branch.id],
                exit_point,
                loop_continue=loop_continue,
                loop_break=loop_break,
            )
        else:
            true_node = self._create_node("block", "then", line=if_stmt.line)
            self._add_edge(branch.id, true_node.id)
            true_exits = [true_node.id]

        succ_after = list(set(self.nodes[branch.id].successors) - succ_before)
        if succ_after:
            branch.true_branch = succ_after[0]

        # ELSE (optional)
        else_body: List[IRStatement] = []
        if len(if_chain) > 1:
            else_body = if_chain[1][1]

        if else_body:
            succ_before = set(self.nodes[branch.id].successors)
            false_exits = self._process_statements(
                else_body,
                [branch.id],
                exit_point,
                loop_continue=loop_continue,
                loop_break=loop_break,
            )
            succ_after = list(set(self.nodes[branch.id].successors) - succ_before)
            if succ_after:
                branch.false_branch = succ_after[0]
        else:
            # No else: FALSE path falls through to the next statement in the enclosing block.
            # We delay connecting the false edge until the next statement node is created.
            self._pending_false_fallthrough.add(branch.id)
            false_exits = [branch.id]

        # After the if, control can come from any non-terminated exits.
        exits = []
        if true_exits:
            exits.extend(true_exits)
        if false_exits:
            exits.extend(false_exits)

        return exits

    def _process_loop(
        self,
        loop_stmt: IRStatement,
        statements: List[IRStatement],
        stmt_idx: int,
        entry_points: List[str],
        exit_point: str
    ) -> List[str]:
        """Process for/while loop"""
        is_while = loop_stmt.type == StatementType.WHILE

        # Create loop header (condition check)
        header = self._create_node(
            "loop_header",
            self._get_label(loop_stmt),
            statement=loop_stmt
        )

        for ep in entry_points:
            self._add_edge(ep, header.id)

        # Create loop body node
        body = self._create_node(
            "loop_body",
            "loop body",
            line=loop_stmt.line
        )
        header.true_branch = body.id
        self._add_edge(header.id, body.id)

        # Back edge from body to header
        self._add_edge(body.id, header.id)

        # Create exit point after loop
        loop_exit = self._create_node("merge", "loop exit")
        header.false_branch = loop_exit.id
        self._add_edge(header.id, loop_exit.id)

        return [loop_exit.id]

    def _process_try(
        self,
        try_stmt: IRStatement,
        statements: List[IRStatement],
        stmt_idx: int,
        entry_points: List[str],
        exit_point: str,
        loop_continue: Optional[str],
        loop_break: Optional[str]
    ) -> List[str]:
        """Process try-except-finally block"""
        # Create try node
        try_node = self._create_node(
            "try",
            "try",
            statement=try_stmt
        )

        for ep in entry_points:
            self._add_edge(ep, try_node.id)

        exits: List[str] = []

        # Try body
        try_body = self._create_node("block", "try body", line=try_stmt.line)
        self._add_edge(try_node.id, try_body.id)
        exits.append(try_body.id)

        # Find except handlers
        j = stmt_idx + 1
        while j < len(statements):
            next_stmt = statements[j]
            if next_stmt.type == StatementType.EXCEPT:
                except_node = self._create_node(
                    "except",
                    f"except {next_stmt.code}"[:40],
                    statement=next_stmt
                )
                # Exception can flow from try body to handler
                self._add_edge(try_body.id, except_node.id)
                exits.append(except_node.id)
                j += 1
            elif next_stmt.type == StatementType.FINALLY:
                finally_node = self._create_node(
                    "finally",
                    "finally",
                    statement=next_stmt
                )
                # All paths go through finally
                for exit_id in exits:
                    self._add_edge(exit_id, finally_node.id)
                exits = [finally_node.id]
                j += 1
                break
            else:
                break

        # Create merge point
        merge = self._create_node("merge", "try exit")
        for exit_id in exits:
            self._add_edge(exit_id, merge.id)

        return [merge.id]

    def _get_label(self, stmt: IRStatement) -> str:
        """Get a short label for a statement"""
        return get_semantic_label(stmt, mode="verbose", wrap=True)

    def _to_graph(self, func_ir: FunctionIR) -> Graph:
        """Convert internal representation to Graph output"""
        graph_nodes: List[GraphNode] = []
        graph_edges: List[GraphEdge] = []
        edge_counter = 0

        # Layout nodes vertically based on traversal order
        visited = set()
        levels: Dict[str, int] = {}
        self._assign_levels(self.entry_id, 0, visited, levels)

        # Count nodes per level for horizontal positioning
        level_counts: Dict[int, int] = defaultdict(int)
        level_positions: Dict[int, int] = defaultdict(int)

        for node_id, level in levels.items():
            level_counts[level] += 1

        # Create graph nodes with positions
        for node_id, node in self.nodes.items():
            level = levels.get(node_id, 0)
            pos_in_level = level_positions[level]
            level_positions[level] += 1

            # Calculate position
            x = 200 + pos_in_level * 150
            y = 50 + level * 80

            # Determine node type for styling
            node_type = node.node_type
            if node.statement:
                node_type = node.statement.type.value

            raw_label = get_semantic_label(node.statement, mode="verbose", wrap=False) if node.statement else node.label
            wrapped_label = format_semantic_label(raw_label) if raw_label else raw_label

            graph_nodes.append(GraphNode(
                id=node.id,
                label=wrapped_label if wrapped_label is not None else node.label,
                type=node_type,
                x=x,
                y=y,
                line=node.line,
                code=node.code,
                metadata={
                    "raw_label": raw_label,
                    "wrapped_label": wrapped_label,
                    "successors": node.successors,
                    "predecessors": node.predecessors,
                    **({"statement_id": node.statement.id} if node.statement else {}),
                    **({"semantic_label_raw": raw_label} if node.statement else {}),
                }
            ))

        # Create edges
        for node_id, node in self.nodes.items():
            for succ_id in node.successors:
                edge_counter += 1
                edge_type = "flow"
                label = None

                # Determine edge type for branches
                if node.true_branch == succ_id:
                    edge_type = "true"
                    label = "True"
                elif node.false_branch == succ_id:
                    edge_type = "false"
                    label = "False"
                elif node.node_type == "loop_body" and succ_id in levels:
                    if levels[succ_id] < levels.get(node_id, 0):
                        edge_type = "back"
                        label = "loop"

                graph_edges.append(GraphEdge(
                    id=f"edge_{edge_counter}",
                    source=node_id,
                    target=succ_id,
                    type=edge_type,
                    label=label
                ))

        return Graph(
            id=f"cfg_{func_ir.id}",
            name=f"CFG: {func_ir.name}",
            type="cfg",
            nodes=graph_nodes,
            edges=graph_edges,
            component_id=func_ir.id,
            component_name=func_ir.name,
            file_path=func_ir.file_path,
            metadata={
                "function_name": func_ir.name,
                "start_line": func_ir.start_line,
                "end_line": func_ir.end_line,
                "parameters": [p.name for p in func_ir.parameters]
            }
        )

    def _assign_levels(
        self,
        node_id: str,
        level: int,
        visited: Set[str],
        levels: Dict[str, int]
    ):
        """Assign depth levels to nodes for layout"""
        if node_id in visited:
            return
        visited.add(node_id)
        levels[node_id] = max(levels.get(node_id, 0), level)

        node = self.nodes.get(node_id)
        if node:
            for succ_id in node.successors:
                self._assign_levels(succ_id, level + 1, visited, levels)


def build_cfg(func_ir: FunctionIR) -> Graph:
    """Convenience function to build CFG"""
    builder = CFGBuilder()
    return builder.build(func_ir)


def build_cfg_from_source(source: str, function_name: str) -> Optional[Graph]:
    """Build CFG from source code string for a specific function"""
    from .parser import RepositoryParser
    import tempfile

    # Write to temp file and parse
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(source)
        temp_path = f.name

    try:
        parser = RepositoryParser(os.path.dirname(temp_path))
        ir = parser.parse_single_file(temp_path)

        # Find the function
        for func_id, func_ir in ir.functions.items():
            if func_ir.name == function_name:
                return build_cfg(func_ir)

        return None
    finally:
        os.unlink(temp_path)
