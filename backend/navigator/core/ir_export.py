import json
import os

from backend.utils.paths import DATA_ROOT

DATA_DIR = str(DATA_ROOT)

def convert_to_serializable(obj):
    """Convert non-serializable objects to JSON-serializable types"""
    if isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]
    return obj

def export_ir(components, repo_id: str | None = None, out_dir=os.path.join(DATA_DIR, "intermediate", "navigator_output")):
    os.makedirs(out_dir, exist_ok=True)

    filename = f"ir_{repo_id}.json" if repo_id else "ir.json"
    ir_path = os.path.join(out_dir, filename)

    with open(ir_path, "w", encoding="utf-8") as f:
        # Convert components to dict and ensure all sets are converted to lists
        ir_data = {}
        for cid, comp in components.items():
            comp_dict = comp.to_dict()
            ir_data[cid] = convert_to_serializable(comp_dict)
        
        json.dump(
            ir_data,
            f,
            indent=2
        )

    print(f"[OK] IR written to {ir_path}")

