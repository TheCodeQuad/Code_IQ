# run_eval.py
# Multi-language completeness evaluation CLI
# Uses Tree-sitter for ALL languages: Python, Java, JavaScript, TypeScript
# Same flow for all languages - no special cases
#
# USAGE:
#   python run_eval.py path/to/File.java
#   python run_eval.py path/to/file.py
#   python run_eval.py path/to/file.js
#   python run_eval.py path/to/mixed/sources/

import sys
import argparse
from pathlib import Path
from tree_sitter import Parser
from tree_sitter_languages import get_language

# Extractors for all 4 languages - same pattern for all
from navigator.languages.java.extractor import extract_components as java_extract
from navigator.languages.javascript.extractor import extract_components as js_extract
from navigator.languages.typescript.extractor import extract_components as ts_extract
from navigator.languages.python.extractor import extract_components as python_extract

# Evaluator - only multilang now, no more ast-based special case
from eval_completeness import run_multilang_evaluation, print_multilang_results


# ================================================================
# LANGUAGE DETECTION
# ================================================================

SUPPORTED_EXTENSIONS = {
    ".java": "java",
    ".js":   "javascript",
    ".ts":   "typescript",
    ".py":   "python",
}


def detect_language(file_path: str) -> str:
    """Detect language from file extension."""
    return SUPPORTED_EXTENSIONS.get(Path(file_path).suffix.lower(), None)


# ================================================================
# PARSER FACTORY
# Same tree_sitter_languages approach for all languages
# ================================================================

def get_parser(language: str) -> Parser:
    """
    Get a tree-sitter parser for the specified language.
    Uses tree_sitter_languages which supports java, javascript,
    typescript, python out of the box.
    """
    parser = Parser()
    lang = get_language(language)
    parser.set_language(lang)
    return parser


# ================================================================
# EXTRACTOR ROUTER
# Same flow for all 4 languages
# ================================================================

EXTRACTORS = {
    "java":       java_extract,
    "javascript": js_extract,
    "typescript": ts_extract,
    "python":     python_extract,
}

# tree_sitter_languages uses these names for parsers
PARSER_NAMES = {
    "java":       "java",
    "javascript": "javascript",
    "typescript": "typescript",
    "python":     "python",
}


def process_file(file_path: str, verbose: bool = False) -> dict:
    """
    Process a single file and extract components.
    Uses Tree-sitter for ALL languages - same flow for everything.

    Args:
        file_path: Path to the source file
        verbose: Enable verbose output

    Returns:
        Dictionary mapping component_id -> CodeComponent
    """
    language = detect_language(file_path)

    if not language:
        if verbose:
            print(f"⚠️  Skipping unsupported file: {file_path}")
        return {}

    if not Path(file_path).exists():
        print(f"❌ File not found: {file_path}")
        return {}

    # Read source
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        source = f.read()

    if not source.strip():
        if verbose:
            print(f"⚠️  Empty file: {file_path}")
        return {}

    module_path = Path(file_path).stem

    if verbose:
        print(f"📄 Processing [{language.upper()}]: {Path(file_path).name}")

    # Parse with tree-sitter (same for all languages)
    try:
        parser = get_parser(PARSER_NAMES[language])
        tree = parser.parse(bytes(source, "utf8"))
    except Exception as e:
        print(f"❌ Parser error for {file_path}: {e}")
        return {}

    # Extract components (same pattern for all languages)
    extractor = EXTRACTORS[language]
    try:
        components = extractor(tree, source, file_path, module_path)
    except Exception as e:
        print(f"❌ Extractor error for {file_path}: {e}")
        return {}

    if verbose:
        print(f"   ✓ Extracted {len(components)} components")

    return components


# ================================================================
# DIRECTORY PROCESSING
# ================================================================

def process_directory(directory: Path, verbose: bool = False) -> dict:
    """
    Recursively process all supported files in a directory.

    Args:
        directory: Path to the directory
        verbose: Enable verbose output

    Returns:
        Dictionary of all extracted components across all files
    """
    all_components = {}
    print(f"📂 Scanning directory: {directory}")

    files_found = 0
    for file_path in sorted(directory.rglob("*")):
        if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            files_found += 1
            components = process_file(str(file_path), verbose=verbose)
            all_components.update(components)

    print(f"   ✓ Scanned {files_found} supported files")
    print(f"   ✓ Total components extracted: {len(all_components)}")
    return all_components


# ================================================================
# CLI ENTRY POINT
# ================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Multi-language docstring completeness evaluator (Java, JS, TS, Python)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_eval.py MyClass.java
  python run_eval.py src/main/java/
  python run_eval.py my_module.py
  python run_eval.py src/ -v
        """
    )

    parser.add_argument(
        "path",
        help="File or directory path to evaluate"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show per-file extraction details"
    )

    args = parser.parse_args()
    target = Path(args.path)

    if not target.exists():
        print(f"❌ Path not found: {args.path}")
        sys.exit(1)

    # Extract components
    all_components = {}

    if target.is_file():
        all_components = process_file(str(target), verbose=args.verbose)

    elif target.is_dir():
        all_components = process_directory(target, verbose=args.verbose)

    # Evaluate
    if not all_components:
        print("\n⚠️  No components found to evaluate.")
        sys.exit(0)

    print(f"\n{'='*60}")
    print(f"  Running completeness evaluation...")
    print(f"{'='*60}\n")

    results = run_multilang_evaluation(all_components)
    print_multilang_results(results)


if __name__ == "__main__":
    main()