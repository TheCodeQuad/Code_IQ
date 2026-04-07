#!/usr/bin/env python3
"""Regression test for HPG generation.

This repo's HPG should:
- build successfully for a real component
- contain no dangling edges (all edge endpoints are present in nodes)

Run:
  python test_hpg_generation.py
"""

from __future__ import annotations

import os
from pathlib import Path

from backend.graph_ir import get_graph_service


def main() -> int:
    repo_path = str(Path(__file__).parent)
    service = get_graph_service()

    print("[HPG TEST] Parsing repository...")
    service.parse_repository(repo_path, force=True)

    target_file = os.path.join(repo_path, "backend", "graph_ir", "service.py")
    component_id = service.find_component_by_name(repo_path, "get_hpg", file_path=target_file)

    if not component_id:
        print(f"[HPG TEST] Could not find get_hpg in {target_file}")
        return 2

    print(f"[HPG TEST] Building HPG for component_id={component_id}")
    response = service.get_hpg(repo_path, component_id)
    if not response.success or not response.data:
        print(f"[HPG TEST] Failed to build HPG: {response.message}")
        return 3

    graph = response.data
    node_ids = {n.id for n in graph.nodes}

    dangling = []
    for e in graph.edges:
        if e.source not in node_ids or e.target not in node_ids:
            dangling.append((e.id, e.source, e.target, e.type, e.label))

    print(f"[HPG TEST] Nodes: {len(graph.nodes)}, Edges: {len(graph.edges)}")
    data_edges = sum(1 for e in graph.edges if e.type == "data")
    print(f"[HPG TEST] Data edges: {data_edges}")

    if dangling:
        print("[HPG TEST] Dangling edges found:")
        for item in dangling[:10]:
            print("  -", item)
        return 4

    print("[HPG TEST] ✓ No dangling edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
