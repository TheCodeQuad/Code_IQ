import os

def scan_files(repo_path, extensions):
    for root, _, files in os.walk(repo_path):
        for f in files:
            if f.endswith(tuple(extensions)):
                yield os.path.join(root, f)
