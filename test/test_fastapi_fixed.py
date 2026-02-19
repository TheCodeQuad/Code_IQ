"""Test FastAPI repository IR generation with fixed dependency resolution"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.navigator.core.repository_parser import RepositoryParser

fastapi_repo = r"C:\Users\Sachi\OneDrive\Desktop\Projects\CODE_IQ\Code_IQ\data\input\repositories\fastapi"

print("Parsing FastAPI repository...")
parser = RepositoryParser(fastapi_repo)
components = parser.parse()

print(f"Extracted {len(components)} components\n")

# Check specific components
print("="*80)
print("CHECKING app.db.models.Answer and app.db.models.UserAnswer")
print("="*80)

answer = components.get("app.db.models.Answer")
user_answer = components.get("app.db.models.UserAnswer")

if answer:
    print(f"\n✓ Answer found")
    print(f"  ID: {answer.id}")
    print(f"  Type: {answer.type.value}")
    print(f"  Depends on: {answer.depends_on}")
else:
    print("✗ Answer not found")

if user_answer:
    print(f"\n✓ UserAnswer found")
    print(f"  ID: {user_answer.id}")
    print(f"  Type: {user_answer.type.value}")
    print(f"  Source:\n    {user_answer.source_code.replace(chr(10), chr(10) + '    ')}")
    print(f"  Depends on: {user_answer.depends_on}")
    
    if "app.db.models.Answer" in user_answer.depends_on:
        print(f"\n✅ SUCCESS: UserAnswer correctly depends on Answer!")
    else:
        print(f"\n❌ FAILED: UserAnswer should depend on Answer")
        print(f"   Expected: ['app.db.models.Answer']")
        print(f"   Got: {user_answer.depends_on}")
else:
    print("✗ UserAnswer not found")

# Save updated IR
output_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'intermediate', 'navigator_output')
os.makedirs(output_dir, exist_ok=True)

ir_path = os.path.join(output_dir, 'ir_fastapi_fixed.json')
ir_data = {cid: comp.to_dict() for cid, comp in components.items()}

with open(ir_path, 'w', encoding='utf-8') as f:
    json.dump(ir_data, f, indent=2)

print(f"\n✅ Saved updated IR to: ir_fastapi_fixed.json")

# Generate DAG
from backend.navigator.core.topo import build_graph_from_components

dag = build_graph_from_components(components)

dag_path = os.path.join(output_dir, 'dag_fastapi_fixed.json')
dag_serializable = {k: list(v) for k, v in dag.items()}

with open(dag_path, 'w', encoding='utf-8') as f:
    json.dump(dag_serializable, f, indent=2)

print(f"✅ Saved updated DAG to: dag_fastapi_fixed.json")

# Check DAG entry
if "app.db.models.UserAnswer" in dag:
    print(f"\nDAG entry for UserAnswer:")
    print(f"  Depends on: {list(dag['app.db.models.UserAnswer'])}")
