"""
Topological sorting utilities for dependency graphs with cycle handling.

This module operates on the Intermediate Representation (IR) produced
by the repository analyzer and provides:

1. Dependency graph construction from IR
2. Cycle detection using Tarjan's algorithm (SCC)
3. Cycle resolution (graph sanitization)
4. Kahn-style topological sort
5. Dependency-first DFS traversal

The graph uses NATURAL dependency direction:
- If A depends on B, the graph has an edge A → B
"""

import logging
from typing import Dict, Set, List, Any
from collections import deque

logger = logging.getLogger(__name__)

# ============================================================
# 1. BUILD GRAPH FROM IR
# ============================================================

def build_graph_from_components(
    components: Dict[str, Any]
) -> Dict[str, Set[str]]:
    """
    Build a dependency graph from IR components.

    Graph direction:
        A → B  means  A depends on B

    Args:
        components: Dict of component_id -> CodeComponent

    Returns:
        Dict[str, Set[str]] adjacency list
    """
    graph: Dict[str, Set[str]] = {}

    for comp_id, component in components.items():
        graph.setdefault(comp_id, set())

        for dep in getattr(component, "depends_on", []):
            if dep in components:
                graph[comp_id].add(dep)

    return graph

# ============================================================
# 2. CYCLE DETECTION (TARJAN / SCC)
# ============================================================

def detect_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """
    Detect cycles using Tarjan's Strongly Connected Components algorithm.

    Args:
        graph: Dependency graph (A → B means A depends on B)

    Returns:
        List of cycles (each cycle is a list of node IDs)
    """
    index_counter = 0
    stack = []
    indices = {}
    lowlinks = {}
    on_stack = set()
    cycles = []

    def strongconnect(node: str):
        nonlocal index_counter
        indices[node] = index_counter
        lowlinks[node] = index_counter
        index_counter += 1
        stack.append(node)
        on_stack.add(node)

        for successor in graph.get(node, set()):
            if successor not in indices:
                strongconnect(successor)
                lowlinks[node] = min(lowlinks[node], lowlinks[successor])
            elif successor in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[successor])

        if lowlinks[node] == indices[node]:
            scc = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                scc.append(w)
                if w == node:
                    break
            if len(scc) > 1:
                cycles.append(scc)

    for node in graph:
        if node not in indices:
            strongconnect(node)

    return cycles

# ============================================================
# 3. CYCLE RESOLUTION
# ============================================================
def resolve_cycles(graph: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    """
    Resolve cycles in a dependency graph by identifying strongly connected
    components and breaking cycles.
    
    Args:
        graph: A dependency graph represented as adjacency lists
               (node -> set of dependencies)
    
    Returns:
        A new acyclic graph with the same nodes but with cycles broken
    """
    cycles = detect_cycles(graph)

    if not cycles:
        return graph

    logger.warning(f"Detected {len(cycles)} cycle(s), resolving...")

    new_graph = {n: deps.copy() for n, deps in graph.items()}

    for cycle in cycles:
        # Break ALL internal edges in the SCC
        cycle_set = set(cycle)
        for node in cycle:
            for dep in list(new_graph[node]):
                if dep in cycle_set:
                    logger.warning(f"Breaking cycle edge: {node} -> {dep}")
                    new_graph[node].remove(dep)

    return new_graph


# ============================================================
# 4. TOPOLOGICAL SORT (KAHN)
# ============================================================
def topological_sort(graph: Dict[str, Set[str]]) -> List[str]:
    """
    Topological sort where:
    edge A -> B means A must come BEFORE B
    (dependency -> dependent)
    """
    graph = resolve_cycles(graph)

    # Build reverse adjacency (dependency -> dependents)
    dependents = {node: set() for node in graph}
    in_degree = {node: 0 for node in graph}

    for dependent, deps in graph.items():
        for dep in deps:
            if dep in graph:
                dependents[dep].add(dependent)
                in_degree[dependent] += 1

    queue = deque([n for n, d in in_degree.items() if d == 0])
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)

        for child in dependents[node]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if len(result) != len(graph):
        logger.error("Topological sort failed due to unresolved cycles")
        return list(graph.keys())

    return result

# ============================================================
# 5. DEPENDENCY-FIRST DFS (ALTERNATIVE ORDER)
# ============================================================

def dependency_first_dfs(graph: Dict[str, Set[str]]) -> List[str]:
    """
    DFS traversal where dependencies are visited before dependents.

    Useful for:
    - Documentation generation
    - Explanation pipelines
    - Code walkthroughs

    Args:
        graph: Dependency graph (A → B means A depends on B)

    Returns:
        Dependency-first ordered list
    """
    graph = resolve_cycles(graph)

    visited = set()
    result = []

    def dfs(node: str):
        if node in visited:
            return
        visited.add(node)
        for dep in sorted(graph.get(node, set())):
            dfs(dep)
        result.append(node)

    for node in sorted(graph.keys()):
        dfs(node)

    return result
