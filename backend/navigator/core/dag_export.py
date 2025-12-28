import json
import os

def export_dag(dag, out_dir="output"):
    os.makedirs(out_dir, exist_ok=True)

    dag_path = os.path.join(out_dir, "dag.json")

    with open(dag_path, "w", encoding="utf-8") as f:
        json.dump(
            {k: list(v) for k, v in dag.items()},
            f,
            indent=2
        )

    print(f"[OK] DAG written to {dag_path}")
