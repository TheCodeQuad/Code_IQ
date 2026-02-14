"""Debug parameter extraction"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.navigator.languages.python.adapter import PythonAdapter

test_code = '''
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b
'''

adapter = PythonAdapter()
tree = adapter.parse(test_code)
root = tree.root_node

def print_tree(node, indent=0):
    """Print tree structure"""
    print("  " * indent + f"{node.type} [{node.start_byte}:{node.end_byte}]")
    if node.type == "identifier":
        print("  " * indent + f"  -> {node.text.decode()}")
    for child in node.children:
        print_tree(child, indent + 1)

print("Tree structure:")
print_tree(root)

# Find function node
for child in root.children:
    if child.type == "function_definition":
        print("\n\nFunction node found:")
        print(f"Type: {child.type}")
        
        params = child.child_by_field_name("parameters")
        print(f"\nParameters node: {params}")
        if params:
            print(f"Parameters type: {params.type}")
            print(f"Parameters text: {params.text.decode()}")
            print(f"\nParameter children:")
            for i, p in enumerate(params.children):
                print(f"  Child {i}: type={p.type}, text={p.text.decode()}")
                
                if p.type == "typed_parameter":
                    name_node = p.child_by_field_name("name")
                    type_node = p.child_by_field_name("type")
                    print(f"    name_node: {name_node}")
                    print(f"    type_node: {type_node}")
                    
                    print(f"    Children of typed_parameter:")
                    for j, c in enumerate(p.children):
                        print(f"      {j}: type={c.type}, text={c.text.decode()}")
