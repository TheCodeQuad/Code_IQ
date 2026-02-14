import os
import sys
from pathlib import Path
import json
import traceback

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "backend" / "output"

def main():
    # Ensure project root is on sys.path for "backend.*" imports
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    print("Navigator runner (no agents)")
    print("Enter repository path (e.g., data/input/repositories/reponame):")
    user_path = input("> ").strip()

    if not user_path:
        print("No path provided. Exiting.")
        return

    # Resolve to absolute path; treat non-absolute as relative to project root
    repo_path = Path(user_path)
    if not repo_path.is_absolute():
        repo_path = PROJECT_ROOT / repo_path
    repo_path = repo_path.resolve()

    if not repo_path.exists():
        print(f"Repository path does not exist: {repo_path}")
        return

    repo_name = repo_path.name
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ir_path = OUTPUT_DIR / f"ir_{repo_name}.json"
    dag_path = OUTPUT_DIR / f"dag_{repo_name}.json"

    try:
        from backend.navigator.core.repository_parser import RepositoryParser
        from backend.navigator.core.dag import build_dag
    except Exception as e:
        print(f"Failed to import navigator core modules: {e}")
        return

    print(f"[Navigator] Parsing repository: {repo_path}")
    try:
        parser = RepositoryParser(str(repo_path))
        components = parser.parse()
    except Exception as e:
        print(f"Parsing failed: {e}")
        traceback.print_exc()
        return

    # Write IR with desired filename
    print(f"[Navigator] Writing IR -> {ir_path}")
    try:
        ir_dict = {cid: comp.to_dict() for cid, comp in components.items()}
        with open(ir_path, "w", encoding="utf-8") as f:
            json.dump(ir_dict, f, indent=2)
    except Exception as e:
        print(f"IR write failed: {e}")
        return

    # Build and write DAG with desired filename
    print(f"[Navigator] Building DAG and writing -> {dag_path}")
    try:
        dag = build_dag(components)
        dag_serializable = {k: list(v) for k, v in dag.items()}
        with open(dag_path, "w", encoding="utf-8") as f:
            json.dump(dag_serializable, f, indent=2)
    except Exception as e:
        print(f"DAG write failed: {e}")
        return

    print("[Navigator] Done.")

if __name__ == "__main__":
    main()