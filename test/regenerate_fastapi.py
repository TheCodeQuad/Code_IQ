"""Regenerate FastAPI IR and DAG with fixed dependencies"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.navigator.core.repository_parser import RepositoryParser
from backend.navigator.core.topo import build_graph_from_components

fastapi_repo = r"C:\Users\Sachi\OneDrive\Desktop\Projects\CODE_IQ\Code_IQ\data\input\repositories\fastapi"
output_dir = r"C:\Users\Sachi\OneDrive\Desktop\Projects\CODE_IQ\Code_IQ\data\intermediate\navigator_output"

print("Parsing FastAPI repository with corrected dependency resolution...")
parser = RepositoryParser(fastapi_repo)
components = parser.parse()

print(f"✓ Extracted {len(components)} components\n")

# Verify the fix
user_answer = components.get("app.db.models.UserAnswer")
if user_answer and "app.db.models.Answer" in user_answer.depends_on:
    print("✓ UserAnswer correctly depends on Answer\n")
else:
    print("⚠ Warning: UserAnswer dependency may not be correct\n")

# Save IR
ir_path = os.path.join(output_dir, 'ir_fastapi.json')
ir_data = {cid: comp.to_dict() for cid, comp in components.items()}

with open(ir_path, 'w', encoding='utf-8') as f:
    json.dump(ir_data, f, indent=2)

print(f"✅ Saved IR to: ir_fastapi.json")

# Generate and save DAG
dag = build_graph_from_components(components)
dag_path = os.path.join(output_dir, 'dag_fastapi.json')
dag_serializable = {k: list(v) for k, v in dag.items()}

with open(dag_path, 'w', encoding='utf-8') as f:
    json.dump(dag_serializable, f, indent=2)

print(f"✅ Saved DAG to: dag_fastapi.json")

# Clean up any "_fixed" files if they exist
fixed_ir = os.path.join(output_dir, 'ir_fastapi_fixed.json')
fixed_dag = os.path.join(output_dir, 'dag_fastapi_fixed.json')

if os.path.exists(fixed_ir):
    os.remove(fixed_ir)
    print(f"\n🗑️  Removed: ir_fastapi_fixed.json")

if os.path.exists(fixed_dag):
    os.remove(fixed_dag)
    print(f"🗑️  Removed: dag_fastapi_fixed.json")

print(f"\n✅ Complete! Only the main files exist now.")
