"""
Convert CodeSearchNet JSONL → parseable .js file

Reads javascript_code_comments.jsonl and writes a single .js file where
each sample becomes:

    /**
     * <original comment from CodeSearchNet>
     * @original_repo <repo>
     * @original_name <function_name>
     */
    <code>

The pipeline can then parse this .js file, generate NEW docstrings, and
the validation script can compare original vs generated.

Usage:
    python jsonl_to_js.py [input_jsonl] [output_js]
"""

import json
import sys
import textwrap
from pathlib import Path


def comment_to_jsdoc(comment: str, repo: str, func_name: str) -> str:
    """Wrap the original comment into a JSDoc block with metadata tags."""
    lines = comment.strip().splitlines()
    jsdoc_lines = ["/**"]
    for line in lines:
        jsdoc_lines.append(f" * {line.rstrip()}")
    # Add metadata so we can trace back to the original sample
    jsdoc_lines.append(f" * @original_repo {repo}")
    jsdoc_lines.append(f" * @original_name {func_name}")
    jsdoc_lines.append(" */")
    return "\n".join(jsdoc_lines)


def convert(input_path: str, output_path: str):
    samples = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    print(f"Loaded {len(samples)} samples from {input_path}")

    with open(output_path, "w", encoding="utf-8") as out:
        # File header
        out.write("// =============================================================================\n")
        out.write("// Auto-generated from CodeSearchNet JavaScript dataset\n")
        out.write(f"// Total functions: {len(samples)}\n")
        out.write("// Each function has its ORIGINAL comment as a JSDoc block above it.\n")
        out.write("// Feed this file through the Code_IQ pipeline to generate NEW docstrings,\n")
        out.write("// then compare original vs generated.\n")
        out.write("// =============================================================================\n")
        out.write("'use strict';\n\n")

        for i, sample in enumerate(samples):
            code = sample.get("code", "")
            comment = sample.get("comment", "")
            repo = sample.get("repo", "unknown")
            func_name = sample.get("function_name", "unknown")

            # Section divider
            out.write(f"// --- [{i+1}/{len(samples)}] {func_name} ({repo}) ---\n\n")

            # Original comment as JSDoc
            if comment:
                jsdoc = comment_to_jsdoc(comment, repo, func_name)
                out.write(jsdoc + "\n")
            else:
                out.write(f"/** @original_repo {repo} @original_name {func_name} */\n")

            # The actual code
            out.write(code + "\n\n")

        out.write("// === END OF FILE ===\n")

    print(f"Wrote {len(samples)} functions to {output_path}")


def main():
    default_input = Path(__file__).parent / "data" / "validation" / "codesearchnet" / "javascript_code_comments.jsonl"
    default_output = Path(__file__).parent / "data" / "validation" / "codesearchnet" / "codesearchnet_javascript.js"

    input_path = sys.argv[1] if len(sys.argv) > 1 else str(default_input)
    output_path = sys.argv[2] if len(sys.argv) > 2 else str(default_output)

    convert(input_path, output_path)


if __name__ == "__main__":
    main()
