import json
import os

def export_ir(components, out_dir="output"):
    os.makedirs(out_dir, exist_ok=True)

    ir_path = os.path.join(out_dir, "ir.json")

    with open(ir_path, "w", encoding="utf-8") as f:
        json.dump(
            {cid: comp.to_dict() for cid, comp in components.items()},
            f,
            indent=2
        )

    print(f"[OK] IR written to {ir_path}")
