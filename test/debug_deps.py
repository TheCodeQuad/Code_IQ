"""Debug dependency resolution"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.navigator.languages.python.adapter import PythonAdapter

test_code = '''
def helper(x: int) -> int:
    """Helper function"""
    return x * 2

def process(data: int) -> int:
    """Process data using helper"""
    result = helper(data)
    return result + 10
'''

adapter = PythonAdapter()
tree = adapter.parse(test_code)
components = adapter.extract_components(tree, test_code, "test.py", "test")

print("Components extracted:")
for cid, comp in components.items():
    print(f"  {cid}: calls={comp.calls}")

print("\nResolving dependencies...")

# Resolve dependencies
for comp in components.values():
    print(f"\nResolving '{comp.id}':")
    print(f"  Component type: {comp.type.value}")
    print(f"  Calls: {comp.calls}")
    
    # Check if we can find the component node
    from backend.navigator.languages.python.dependencies import find_component_node
    node = find_component_node(tree, comp)
    print(f"  Found node: {node is not None}")
    if node:
        print(f"  Node type: {node.type}")
    
    deps = adapter.resolve_dependencies(comp, tree, test_code, components)
    print(f"  Returned deps: {deps}")
    
    if comp.calls and not deps:
        print(f"  ⚠️  WARNING: Has calls but no dependencies resolved!")
