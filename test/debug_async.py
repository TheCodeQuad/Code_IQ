"""Debug async detection"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.navigator.languages.python.adapter import PythonAdapter

test_code = '''
async def async_function(data: list) -> dict:
    """Example async function"""
    result = {}
    return result
'''

adapter = PythonAdapter()
tree = adapter.parse(test_code)
root = tree.root_node

# Find function node
for child in root.children:
    if child.type in ("function_definition", "async_function_definition"):
        print(f"Function node type: {child.type}")
        print(f"Is async: {child.type == 'async_function_definition'}")
        
        name = child.child_by_field_name("name")
        if name:
            print(f"Function name: {name.text.decode()}")
        
        print(f"\nChildren:")
        for i, c in enumerate(child.children):
            print(f"  {i}: type={c.type}, text={c.text.decode()[:20]}")
