"""
Test script to verify Python IR generation
"""
import sys
import os
import json

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.navigator.languages.python.adapter import PythonAdapter
from backend.navigator.core.repository_parser import RepositoryParser
from backend.navigator.languages.adapter_registry import AdapterRegistry

def test_simple_python_file():
    """Test IR generation on a simple Python file"""
    
    # Create a test Python file
    test_code = '''
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

def multiply(x: int, y: int) -> int:
    """Multiply two numbers"""
    result = add(x, x) * y
    return result

class Calculator:
    """A simple calculator class"""
    
    def __init__(self):
        """Initialize calculator"""
        self.history = []
    
    def calculate(self, operation: str, a: int, b: int) -> int:
        """Perform calculation"""
        if operation == "add":
            return add(a, b)
        elif operation == "multiply":
            return multiply(a, b)
        return 0

async def async_function(data: list) -> dict:
    """Example async function"""
    result = {}
    for item in data:
        result[item] = multiply(item, 2)
    return result
'''
    
    # Write test file
    test_dir = os.path.join(os.path.dirname(__file__), 'temp_test')
    os.makedirs(test_dir, exist_ok=True)
    
    test_file = os.path.join(test_dir, 'sample.py')
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_code)
    
    print(f"Created test file: {test_file}\n")
    
    # Parse with PythonAdapter
    adapter = PythonAdapter()
    
    with open(test_file, 'r', encoding='utf-8') as f:
        source = f.read()
    
    tree = adapter.parse(source)
    components = adapter.extract_components(tree, source, test_file, "sample")
    
    print(f"Extracted {len(components)} components:\n")
    
    # Display each component
    for cid, comp in components.items():
        print(f"ID: {cid}")
        print(f"  Name: {comp.name}")
        print(f"  Type: {comp.type.value}")
        print(f"  Signature: {comp.signature}")
        print(f"  Parameters: {[p.name for p in comp.parameters]}")
        print(f"  Return Type: {comp.return_type}")
        print(f"  Decorators: {comp.decorators}")
        print(f"  Calls: {comp.calls}")
        print(f"  Imports: {comp.imports}")
        print(f"  Is Async: {comp.is_async}")
        print(f"  Is Generator: {comp.is_generator}")
        print(f"  Lines of Code: {comp.lines_of_code}")
        print(f"  Docstring: {comp.existing_docstring[:50] if comp.existing_docstring else None}...")
        print()
    
    # Save IR JSON
    ir_output = os.path.join(test_dir, 'ir_sample.json')
    ir_data = {cid: comp.to_dict() for cid, comp in components.items()}
    
    with open(ir_output, 'w', encoding='utf-8') as f:
        json.dump(ir_data, f, indent=2)
    
    print(f"\nSaved IR to: {ir_output}")
    
    # Show sample IR entry
    if components:
        first_key = list(components.keys())[0]
        print(f"\nSample IR entry for '{first_key}':")
        print(json.dumps(ir_data[first_key], indent=2))
    
    # Cleanup
    import shutil
    # shutil.rmtree(test_dir)
    print(f"\nTest directory kept for inspection: {test_dir}")

if __name__ == "__main__":
    test_simple_python_file()
