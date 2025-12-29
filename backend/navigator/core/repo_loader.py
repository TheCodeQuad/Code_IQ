import os
import shutil
import subprocess
import uuid


# Get the absolute path to the project root (one level up from backend/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

def clone_repo(repo_url: str, base_dir=os.path.join(DATA_DIR, "input", "repositories")):
    """
    Clone a GitHub repository and return local path.
    """
    os.makedirs(base_dir, exist_ok=True)

    repo_id = uuid.uuid4().hex[:8]
    repo_path = os.path.join(base_dir, repo_id)

    subprocess.run(
        ["git", "clone", repo_url, repo_path],
        check=True
    )

    return repo_path

