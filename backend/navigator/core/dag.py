from collections import defaultdict

def build_dag(components):
    """
    components: Dict[str, CodeComponent]
    returns: adjacency list {node: set(dependents)}
    """
    dag = defaultdict(set)
    for comp in components.values():
        for dep in comp.depends_on:
            dag[dep].add(comp.id)
    return dag
