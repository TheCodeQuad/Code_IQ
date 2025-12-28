import os
import shutil
import subprocess
import uuid

def clone_repo(repo_url: str, base_dir="repos"):
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
