"""
Extract JavaScript Code + Comments from CodeSearchNet Dataset

This script:
1. Loads the CodeSearchNet dataset from Hugging Face (config 'pair')
2. Filters only JavaScript samples
3. Extracts 'code' and 'docstring' for each function/module
4. Saves results as a JSON Lines (.jsonl) file

Usage:
    python extract_js_codesearchnet.py [max_samples]

Example:
    python extract_js_codesearchnet.py 100  # Extract 100 samples
"""

import sys
import json
from pathlib import Path
from datasets import load_dataset

# -----------------------------
# Configuration
# -----------------------------
OUTPUT_DIR = Path("data/validation/codesearchnet")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "javascript_code_comments.jsonl"


def extract_js_code(max_samples: int = 100):
    """Extract JavaScript code + docstrings from CodeSearchNet dataset."""
    print(f"Loading CodeSearchNet dataset (config='javascript') with max_samples={max_samples} ...")

    # Use the original code_search_net dataset which has per-language configs
    # and rich metadata (repo, func_name, language, etc.).
    # The 'sentence-transformers/codesearchnet' "pair" config only has
    # 'code' and 'comment' columns with NO language field.
    dataset = load_dataset(
        "code_search_net",
        "javascript",
        split="train",
        streaming=True,
    )

    count = 0
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f_out:
        for sample in dataset:
            if count >= max_samples:
                break

            # Extract code and docstring using correct field names
            code = sample.get("func_code_string", "")
            comment = sample.get("func_documentation_string", "")
            repo = sample.get("repository_name") or "unknown"
            func_name = sample.get("func_name") or "unknown"

            # Skip if code is empty
            if not code or not code.strip():
                continue

            # Build JSON object
            json_obj = {
                "repo": repo,
                "function_name": func_name,
                "code": code,
                "comment": comment or ""
            }

            # Write as JSON line
            f_out.write(json.dumps(json_obj, ensure_ascii=False) + "\n")
            count += 1

            # Progress
            if count % 10 == 0:
                print(f"  Extracted {count} samples ...")

    print(f"\nExtraction complete! Total samples saved: {count}")
    print(f"Output file: {OUTPUT_FILE}")


def main():
    # Default max_samples
    max_samples = 100

    # Override if argument provided
    if len(sys.argv) > 1:
        try:
            max_samples = int(sys.argv[1])
        except ValueError:
            print(f"Invalid max_samples value: {sys.argv[1]}")
            sys.exit(1)

    extract_js_code(max_samples=max_samples)


if __name__ == "__main__":
    main()