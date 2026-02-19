"""
Test Python IR generation on a real repository  
"""
import sys
import os
import json

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.navigator.core.repository_parser import RepositoryParser

def test_real_python_repo():
    """Test on actual Python repository"""
    
    # Use the backend folder itself as test repository
    repo_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'agents')
    
    print(f"Parsing Python repository: {repo_path}\n")
    
    # Parse repository
    parser = RepositoryParser(repo_path)
    components = parser.parse()
    
    print(f"Extracted {len(components)} components\n")
    
    # Show sample components
    count = 0
    for cid, comp in components.items():
        if count >= 5:
            break
        
        print(f"ID: {cid}")
        print(f"  Type: {comp.type.value}")
        print(f"  Signature: {comp.signature}")
        print(f"  Parameters: {[p.name for p in comp.parameters]}")
        print(f"  Decorators: {comp.decorators}")
        print(f"  Depends on: {comp.depends_on[:3] if len(comp.depends_on) > 3 else comp.depends_on}")
        print()
        count += 1
    
    # Save IR
    output_dir = os.path.join(os.path.dirname(__file__), 'temp_test')
    os.makedirs(output_dir, exist_ok=True)
    
    ir_path = os.path.join(output_dir, 'ir_agents.json')
    ir_data = {cid: comp.to_dict() for cid, comp in components.items()}
    
    with open(ir_path, 'w', encoding='utf-8') as f:
        json.dump(ir_data, f, indent=2)
    
    print(f"\nSaved IR to: {ir_path}")
    
    # Show statistics
    types_count = {}
    for comp in components.values():
        types_count[comp.type.value] = types_count.get(comp.type.value, 0) + 1
    
    print("\nComponent Statistics:")
    for typ, count in sorted(types_count.items()):
        print(f"  {typ}: {count}")

if __name__ == "__main__":
    test_real_python_repo()
