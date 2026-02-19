import os
import shutil
import subprocess
import re
import stat


# Get the absolute path to the project root (one level up from backend/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

def handle_remove_readonly(func, path, exc_info):
    """
    Error handler for Windows read-only file removal.
    Used with shutil.rmtree to handle git files that are read-only.
    """
    # Check if it's a permission error
    if not os.access(path, os.W_OK):
        # Make the file writable and retry
        os.chmod(path, stat.S_IWRITE)
        func(path)
    else:
        raise

def extract_repo_name(repo_url: str) -> str:
    """
    Extract repository name from GitHub URL.
    
    Handles formats:
    - https://github.com/username/repo-name
    - https://github.com/username/repo-name.git
    - git@github.com:username/repo-name.git
    
    Returns:
        str: Repository name (e.g., 'repo-name')
    """
    # Remove .git suffix if present
    url = repo_url.rstrip('/')
    if url.endswith('.git'):
        url = url[:-4]
    
    # Extract the last part of the URL (repository name)
    # Handle both HTTPS and SSH formats
    if '/' in url:
        repo_name = url.split('/')[-1]
    elif ':' in url:  # SSH format like git@github.com:username/repo
        repo_name = url.split(':')[-1].split('/')[-1]
    else:
        repo_name = url
    
    # Clean up any remaining special characters and make filesystem-safe
    repo_name = re.sub(r'[^\w\-]', '_', repo_name)
    
    return repo_name

def clone_repo(repo_url: str, base_dir=os.path.join(DATA_DIR, "input", "repositories")):
    """
    Clone a GitHub repository and return local path.
    Uses the repository name as the folder name.
    """
    os.makedirs(base_dir, exist_ok=True)

    repo_name = extract_repo_name(repo_url)
    repo_path = os.path.join(base_dir, repo_name)
    
    # If directory already exists, remove it to avoid conflicts
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path, onerror=handle_remove_readonly)

    subprocess.run(
        ["git", "clone", repo_url, repo_path],
        check=True
    )

    return repo_path

