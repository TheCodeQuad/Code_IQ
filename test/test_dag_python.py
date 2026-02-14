"""
Test DAG generation for Python repository
"""
import sys
import os
import json

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.navigator.core.repository_parser import RepositoryParser
from backend.navigator.core.topo import build_graph_from_components, topological_sort

def test_python_dag():
    """Test DAG generation on Python code"""
    
    # Create a test Python file with dependencies
    test_code = '''
def helper(x: int) -> int:
    """Helper function"""
    return x * 2

def process(data: int) -> int:
    """Process data using helper"""
    result = helper(data)
    return result + 10

class Calculator:
    """Calculator class"""
    
    def compute(self, value: int) -> int:
        """Compute using helper"""
        return helper(value)
    
    def run(self, value: int) -> int:
        """Run computation"""
        computed = self.compute(value)
        return process(computed)

async def main(value: int) -> int:
    """Main entry point"""
    calc = Calculator()
    result = calc.run(value)
    return result
'''
    
    # Write test file
    test_dir = os.path.join(os.path.dirname(__file__), 'temp_test')
    os.makedirs(test_dir, exist_ok=True)
    
    test_file = os.path.join(test_dir, 'dag_test.py')
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_code)
    
    print(f"Created test file: {test_file}\n")
    
    # Parse repository
    parser = RepositoryParser(test_dir)
    components = parser.parse()
    
    print(f"Extracted {len(components)} components\n")
    
    # Show components with dependencies
    print("=" * 80)
    print("COMPONENTS WITH DEPENDENCIES")
    print("=" * 80)
    for cid, comp in sorted(components.items()):
        print(f"\nID: {cid}")
        print(f"  Type: {comp.type.value}")
        print(f"  Calls: {comp.calls}")
        print(f"  Depends on: {comp.depends_on}")
    
    # Build DAG
    print("\n" + "=" * 80)
    print("DAG STRUCTURE")
    print("=" * 80)
    dag = build_graph_from_components(components)
    
    for node, dependencies in sorted(dag.items()):
        if dependencies:
            print(f"\n{node}")
            print(f"  → depends on: {list(dependencies)}")
        else:
            print(f"\n{node}")
            print(f"  → no dependencies (leaf node)")
    
    # Perform topological sort
    print("\n" + "=" * 80)
    print("TOPOLOGICAL ORDER")
    print("=" * 80)
    try:
        sorted_ids = topological_sort(dag)
        print("\nExecution order (bottom-up):")
        for i, cid in enumerate(sorted_ids, 1):
            comp = components.get(cid)
            if comp:
                print(f"{i}. {cid} ({comp.type.value})")
    except Exception as e:
        print(f"Error in topological sort: {e}")
    
    # Check for cycles
    print("\n" + "=" * 80)
    print("CYCLE DETECTION")
    print("=" * 80)
    
    def has_cycle(graph):
        """Check if graph has cycles"""
        visited = set()
        rec_stack = set()
        
        def visit(node):
            if node in rec_stack:
                return True  # Cycle detected
            if node in visited:
                return False
            
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if visit(neighbor):
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in graph:
            if node not in visited:
                if visit(node):
                    return True
        return False
    
    if has_cycle(dag):
        print("⚠️  CYCLE DETECTED in DAG!")
    else:
        print("✅ No cycles detected - valid DAG")
    
    # Save DAG
    dag_path = os.path.join(test_dir, 'dag_python.json')
    dag_serializable = {k: list(v) for k, v in dag.items()}
    
    with open(dag_path, 'w', encoding='utf-8') as f:
        json.dump(dag_serializable, f, indent=2)
    
    print(f"\n✅ Saved DAG to: {dag_path}")
    
    # Statistics
    print("\n" + "=" * 80)
    print("STATISTICS")
    print("=" * 80)
    
    leaf_nodes = [k for k, v in dag.items() if not v]
    root_nodes = [k for k in dag.keys() if not any(k in deps for deps in dag.values())]
    
    print(f"Total nodes: {len(dag)}")
    print(f"Leaf nodes (no dependencies): {len(leaf_nodes)}")
    print(f"Root nodes (not depended on): {len(root_nodes)}")
    print(f"\nLeaf nodes: {leaf_nodes}")
    print(f"Root nodes: {root_nodes}")

if __name__ == "__main__":
    test_python_dag()
