import json
import os

# Get the absolute path to the project root (one level up from backend/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

def export_ir(components, repo_id: str | None = None, out_dir=os.path.join(DATA_DIR, "intermediate", "navigator_output")):
    os.makedirs(out_dir, exist_ok=True)

    filename = f"ir_{repo_id}.json" if repo_id else "ir.json"
    ir_path = os.path.join(out_dir, filename)

    with open(ir_path, "w", encoding="utf-8") as f:
        json.dump(
            {cid: comp.to_dict() for cid, comp in components.items()},
            f,
            indent=2
        )

    print(f"[OK] IR written to {ir_path}")

