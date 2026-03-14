import json
import os

from backend.utils.paths import DATA_ROOT

DATA_DIR = str(DATA_ROOT)

def export_dag(dag, repo_id: str | None = None, out_dir=os.path.join(DATA_DIR, "intermediate", "navigator_output")):
    os.makedirs(out_dir, exist_ok=True)

    filename = f"dag_{repo_id}.json" if repo_id else "dag.json"
    dag_path = os.path.join(out_dir, filename)

    with open(dag_path, "w", encoding="utf-8") as f:
        json.dump(
            {k: list(v) for k, v in dag.items()},
            f,
            indent=2
        )

    print(f"[OK] DAG written to {dag_path}")

