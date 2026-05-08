"""Hybrid Program Graph (HPG) Builder

In this codebase, an HPG (Hybrid Program Graph) is constructed by overlaying
PDG *data dependency* edges onto the CFG structure.

Implementation goals:
- Use CFG nodes/edges as the base representation.
- Add PDG edges where edge.type == "data".
- Prefer mapping PDG statement nodes onto existing CFG statement nodes
  (via shared IR statement ids) so the overlay truly connects the CFG.
- Ensure the returned graph has no dangling edges: every edge endpoint exists
  as a node in the returned graph.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple, Optional

from .models import FunctionIR, Graph, GraphNode, GraphEdge
from .cfg_builder import build_cfg
from .pdg_builder import build_pdg, build_pdg_with_reaching_defs


def _index_nodes_by_id(nodes: List[GraphNode]) -> Dict[str, GraphNode]:
    return {n.id: n for n in nodes}


def _get_statement_id(node: GraphNode) -> Optional[str]:
    # Stored by cfg_builder/pdg_builder when available.
    stmt_id = node.metadata.get("statement_id") if node.metadata else None
    return stmt_id if isinstance(stmt_id, str) and stmt_id else None


def build_hpg(func_ir: FunctionIR, use_reaching_defs: bool = False) -> Graph:
    """Build a Hybrid Program Graph for a FunctionIR.

    Args:
        func_ir: function/method IR
        use_reaching_defs: if True, build PDG using reaching definitions

    Returns:
        Graph of type "hpg"
    """

    cfg = build_cfg(func_ir)
    pdg = build_pdg_with_reaching_defs(func_ir) if use_reaching_defs else build_pdg(func_ir)

    cfg_nodes: List[GraphNode] = list(cfg.nodes)
    cfg_edges: List[GraphEdge] = list(cfg.edges)

    # Map IR statement id -> CFG node id
    stmt_to_cfg_node: Dict[str, str] = {}
    for n in cfg_nodes:
        stmt_id = _get_statement_id(n)
        if stmt_id:
            stmt_to_cfg_node[stmt_id] = n.id

    pdg_nodes_by_id = _index_nodes_by_id(pdg.nodes)

    # Start with all CFG nodes. We may add extra PDG nodes (e.g., parameter nodes)
    # when they participate in data edges and do not map to a CFG node.
    hpg_nodes_by_id: Dict[str, GraphNode] = _index_nodes_by_id(cfg_nodes)

    def map_or_keep_node_id(pdg_node_id: str) -> str:
        node = pdg_nodes_by_id.get(pdg_node_id)
        if not node:
            return pdg_node_id

        stmt_id = _get_statement_id(node)
        if stmt_id and stmt_id in stmt_to_cfg_node:
            return stmt_to_cfg_node[stmt_id]

        # No mapping: keep PDG node in HPG so edges have valid endpoints.
        if node.id not in hpg_nodes_by_id:
            hpg_nodes_by_id[node.id] = node
        return node.id

    # Add PDG data edges, mapping onto CFG nodes where possible.
    hpg_edges: List[GraphEdge] = list(cfg_edges)
    existing_edges: Set[Tuple[str, str, str, Optional[str]]] = set(
        (e.source, e.target, e.type, e.label) for e in hpg_edges
    )

    edge_counter = 0
    pdg_entry = next((n for n in pdg.nodes if n.type == "entry"), None)
    pdg_entry_id = pdg_entry.id if pdg_entry else None

    for e in pdg.edges:
        if e.type not in ("data", "control"):
            continue

        # Filter out control dependencies from Entry node to avoid clutter
        if e.type == "control" and e.source == pdg_entry_id:
            continue

        src = map_or_keep_node_id(e.source)
        tgt = map_or_keep_node_id(e.target)
        if src == tgt:
            continue

        # Map types to frontend-friendly types
        hpg_type = "data_flow" if e.type == "data" else "control_flow"

        key = (src, tgt, hpg_type, e.label)
        if key in existing_edges:
            continue
        existing_edges.add(key)

        edge_counter += 1
        hpg_edges.append(
            GraphEdge(
                id=f"hpg_edge_{edge_counter}",
                source=src,
                target=tgt,
                type=hpg_type,
                label=e.label or ("control" if e.type == "control" else None),
                metadata=e.metadata or {},
            )
        )

    hpg_nodes = list(hpg_nodes_by_id.values())

    return Graph(
        id=f"hpg_{func_ir.id}",
        name=f"HPG: {func_ir.name}",
        type="hpg",
        nodes=hpg_nodes,
        edges=hpg_edges,
        component_id=func_ir.id,
        component_name=func_ir.name,
        file_path=func_ir.file_path,
        metadata={
            "cfg_nodes": len(cfg.nodes),
            "cfg_edges": len(cfg.edges),
            "pdg_nodes": len(pdg.nodes),
            "pdg_edges": len(pdg.edges),
            "pdg_data_edges": sum(1 for edge in pdg.edges if edge.type == "data"),
            "use_reaching_defs": use_reaching_defs,
        },
    )
