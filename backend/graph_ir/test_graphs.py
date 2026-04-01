"""
Test script for Graph IR system

Run this to verify the graph generation works correctly.
"""

import os
import sys
import json

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.graph_ir import (
    parse_repository,
    parse_file,
    build_cfg,
    build_pdg,
    build_dag,
    get_graph_service
)


def test_parse_single_file():
    """Test parsing a single Python file"""
    print("\n=== Test: Parse Single File ===")

    # Create a test file
    test_code = '''
def calculate_sum(numbers: list) -> int:
    """Calculate sum of numbers."""
    total = 0
    for num in numbers:
        if num > 0:
            total += num
        else:
            print(f"Skipping {num}")
    return total


def process_data(data):
    """Process input data."""
    result = calculate_sum(data)
    if result > 100:
        return "Large"
    elif result > 50:
        return "Medium"
    else:
        return "Small"


class DataProcessor:
    """Process data with different strategies."""

    def __init__(self, strategy="default"):
        self.strategy = strategy
        self.cache = {}

    def process(self, items):
        """Process items using strategy."""
        if self.strategy == "sum":
            return calculate_sum(items)
        elif self.strategy == "filter":
            return [x for x in items if x > 0]
        return items
'''

    # Write to temp file
    test_file = os.path.join(os.path.dirname(__file__), "_test_sample.py")
    with open(test_file, "w") as f:
        f.write(test_code)

    try:
        # Parse the file
        ir = parse_file(test_file)

        print(f"Parsed {len(ir.functions)} functions:")
        for func_id, func_ir in ir.functions.items():
            print(f"  - {func_ir.name} ({func_ir.type.value})")
            print(f"    Parameters: {[p.name for p in func_ir.parameters]}")
            print(f"    Statements: {len(func_ir.statements)}")
            print(f"    Calls: {[c.name for c in func_ir.calls]}")

        print(f"\nParsed {len(ir.classes)} classes:")
        for class_id, class_ir in ir.classes.items():
            print(f"  - {class_ir.name}")
            print(f"    Methods: {len(class_ir.methods)}")
            print(f"    Instance attrs: {class_ir.instance_attributes}")

        return ir

    finally:
        # Cleanup
        if os.path.exists(test_file):
            os.remove(test_file)


def test_cfg_generation(ir):
    """Test CFG generation"""
    print("\n=== Test: CFG Generation ===")

    for func_id, func_ir in ir.functions.items():
        print(f"\nCFG for {func_ir.name}:")
        cfg = build_cfg(func_ir)
        print(f"  Nodes: {cfg.node_count}")
        print(f"  Edges: {cfg.edge_count}")

        # Show some nodes
        for node in cfg.nodes[:5]:
            print(f"    [{node.type}] {node.label}")


def test_pdg_generation(ir):
    """Test PDG generation"""
    print("\n=== Test: PDG Generation ===")

    for func_id, func_ir in ir.functions.items():
        print(f"\nPDG for {func_ir.name}:")
        pdg = build_pdg(func_ir)
        print(f"  Nodes: {pdg.node_count}")
        print(f"  Edges: {pdg.edge_count}")

        # Count edge types
        data_deps = sum(1 for e in pdg.edges if e.type == "data")
        ctrl_deps = sum(1 for e in pdg.edges if e.type == "control")
        call_deps = sum(1 for e in pdg.edges if e.type == "call")
        print(f"  Data dependencies: {data_deps}")
        print(f"  Control dependencies: {ctrl_deps}")
        print(f"  Call dependencies: {call_deps}")


def test_dag_generation(ir):
    """Test DAG generation"""
    print("\n=== Test: DAG Generation ===")

    dag = build_dag(ir)
    print(f"Repository DAG:")
    print(f"  Nodes: {dag.node_count}")
    print(f"  Edges: {dag.edge_count}")

    # Show dependencies
    for edge in dag.edges:
        source_node = next((n for n in dag.nodes if n.id == edge.source), None)
        target_node = next((n for n in dag.nodes if n.id == edge.target), None)
        if source_node and target_node:
            print(f"  {source_node.label} --[{edge.type}]--> {target_node.label}")


def test_service():
    """Test the service layer"""
    print("\n=== Test: Service Layer ===")

    service = get_graph_service()

    # Test with the current backend directory
    backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print(f"Parsing: {backend_path}")

    # Parse (limited to graph_ir folder for speed)
    graph_ir_path = os.path.join(backend_path, "backend", "graph_ir")
    if os.path.exists(graph_ir_path):
        ir = service.parse_repository(graph_ir_path)
        status = service.get_parse_status(graph_ir_path)

        print(f"Parse status:")
        print(f"  Files: {status.file_count}")
        print(f"  Functions: {status.function_count}")
        print(f"  Classes: {status.class_count}")
        print(f"  Errors: {len(status.errors)}")

        # List components
        components = service.list_components(graph_ir_path)
        print(f"\nFound {components.total} components:")
        for comp in components.components[:10]:
            print(f"  - {comp.name} ({comp.type.value})")


def test_json_output(ir):
    """Test JSON serialization"""
    print("\n=== Test: JSON Output ===")

    for func_id, func_ir in list(ir.functions.items())[:1]:
        cfg = build_cfg(func_ir)
        pdg = build_pdg(func_ir)

        # Serialize to JSON
        cfg_json = cfg.model_dump_json(indent=2)
        pdg_json = pdg.model_dump_json(indent=2)

        print(f"\nCFG JSON for {func_ir.name}:")
        print(cfg_json[:500] + "..." if len(cfg_json) > 500 else cfg_json)

        print(f"\nPDG JSON for {func_ir.name}:")
        print(pdg_json[:500] + "..." if len(pdg_json) > 500 else pdg_json)


def main():
    print("=" * 60)
    print("Graph IR System Test")
    print("=" * 60)

    # Test parsing
    ir = test_parse_single_file()

    if ir and ir.functions:
        # Test graph generation
        test_cfg_generation(ir)
        test_pdg_generation(ir)
        test_dag_generation(ir)
        test_json_output(ir)

    # Test service
    test_service()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
