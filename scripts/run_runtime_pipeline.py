"""
Runtime-Aware Documentation Pipeline (standalone)

Usage:
    python -m scripts.run_runtime_pipeline <repo_path> [--output-dir DIR]
    python -m scripts.run_runtime_pipeline data/input/repositories/MyPythonRepo

This script runs the full runtime-aware documentation pipeline
**without** touching pipeline.py, app.py, or main.py.

OUTPUT STRUCTURE:
    {output_dir}/
    ├── documented_source/{repo_name}/   # Copied source with inserted docstrings
    │   ├── src/
    │   │   └── *.py  (with docstrings inserted)
    │   └── ...
    ├── {repo_name}_runtime_docs.json    # JSON documentation metadata
    └── {repo_name}_runtime_profiles.json # Runtime profiles (exceptions, side effects)

    NOTE: Original repository files are NEVER modified.
          Docstrings are inserted into the copied source files only.

Pipeline stages:
    1.   Navigator  — parse repository → CodeComponents
    1.5  Copy       — copy source files to output directory (for safe insertion)
    2.   DAG        — build dependency graph, topological sort
    3.   Profiler   — StaticRuntimeProfiler → attaches RuntimeProfile
    4.   Reader     — code analysis (batched)
    5.   Searcher   — internal/external context gathering
    6.   RuntimeWriterAgent — LLM docstring generation with runtime signals
    7.   Verifier   — quality gate (optional, controlled by config)
    8.   Inserter   — write docstrings into COPIED source files

Only **Python** components are enriched with runtime profiles in this
phase-1 implementation.  Non-Python components pass through with the
standard (non-runtime) Writer flow — they are not skipped.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Ensure project root is on sys.path regardless of how the script is invoked
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import networkx as nx

from backend.agents.base_agent import AgentContext, AgentResult, AgentStatus
from backend.agents.reader_agent import ReaderAgent
from backend.agents.runtime_profiler import StaticRuntimeProfiler
from backend.agents.runtime_writer_agent import RuntimeWriterAgent
from backend.agents.searcher_agent import SearcherAgent
from backend.agents.verifier_agent import VerifierAgent
from backend.models.code_component import CodeComponent, ComponentType
from backend.models.documentation import Documentation
from backend.models.runtime_profile import RuntimeProfile
from backend.navigator.core.repository_parser import RepositoryParser
from backend.navigator.core.topo import (
    build_graph_from_components,
    dependency_first_dfs,
    resolve_cycles,
    topological_sort,
)
from backend.utils.config_handler import get_config
from backend.utils.docstring_inserter import DocstringInserter
from backend.utils.file_handler import FileHandler
from backend.utils.logger import get_logger

logger = get_logger("runtime_pipeline")

# Component types that have no docstring insertion point
_SKIP_TYPES = {"global_variable", "static_field", "field", "import", "variable"}

# File extensions to copy (source code files only)
_SOURCE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".cpp", ".c", ".h", ".hpp", ".cs"
}


def _copy_repository_for_insertion(
    source_repo: Path,
    output_dir: Path,
) -> Path:
    """
    Copy source code files from the repository to the output directory.

    Only copies files with recognized source code extensions to avoid
    copying large binary files, node_modules, venvs, etc.

    Args:
        source_repo: Path to the original repository
        output_dir: Base output directory

    Returns:
        Path to the copied repository root
    """
    repo_name = source_repo.name
    dest_repo = output_dir / "documented_source" / repo_name

    # Remove existing copy if present
    if dest_repo.exists():
        shutil.rmtree(dest_repo)

    # Directories to skip
    skip_dirs = {
        "node_modules", "__pycache__", ".git", ".venv", "venv",
        "env", ".env", "dist", "build", ".pytest_cache", ".mypy_cache",
        ".tox", "eggs", "*.egg-info", ".eggs"
    }

    copied_files = 0

    for src_file in source_repo.rglob("*"):
        # Skip directories
        if src_file.is_dir():
            continue

        # Skip files in excluded directories
        if any(skip_dir in src_file.parts for skip_dir in skip_dirs):
            continue

        # Only copy source code files
        if src_file.suffix.lower() not in _SOURCE_EXTENSIONS:
            continue

        # Calculate relative path and destination
        rel_path = src_file.relative_to(source_repo)
        dest_file = dest_repo / rel_path

        # Create parent directories
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        # Copy file
        shutil.copy2(src_file, dest_file)
        copied_files += 1

    logger.info(f"Copied {copied_files} source files to {dest_repo}")
    return dest_repo


def _remap_component_paths(
    components: Dict[str, CodeComponent],
    original_repo: Path,
    copied_repo: Path,
) -> None:
    """
    Update file paths in components to point to the copied repository location.

    Modifies components in-place.

    Args:
        components: Dictionary of component ID to CodeComponent
        original_repo: Path to the original repository
        copied_repo: Path to the copied repository
    """
    original_str = str(original_repo.resolve())
    copied_str = str(copied_repo.resolve())

    for comp in components.values():
        if hasattr(comp, 'location') and comp.location:
            original_path = comp.location.file_path
            if original_path and original_str in original_path:
                new_path = original_path.replace(original_str, copied_str)
                comp.location.file_path = new_path

        # Also update file_path if it exists as a direct attribute
        if hasattr(comp, 'file_path') and comp.file_path:
            if original_str in comp.file_path:
                comp.file_path = comp.file_path.replace(original_str, copied_str)


# ======================================================================
# Helpers
# ======================================================================

def _comp_type_str(comp: CodeComponent) -> str:
    t = comp.type
    return t.value if hasattr(t, "value") else str(t)


def _print_banner(msg: str) -> None:
    width = max(len(msg) + 4, 60)
    print("=" * width)
    print(f"  {msg}")
    print("=" * width)


# ======================================================================
# Main pipeline function
# ======================================================================

def run_runtime_pipeline(
    repo_path: str,
    output_dir: Optional[str] = None,
    insert_docstrings: bool = True,
    skip_non_python: bool = False,
) -> Dict:
    """
    Run the runtime-aware documentation pipeline on a repository.

    When insert_docstrings is True (default), the pipeline:
    1. Copies the repository source files to {output_dir}/documented_source/{repo_name}/
    2. Generates docstrings with runtime signals (exceptions, side effects, etc.)
    3. Inserts docstrings into the COPIED files (original files are NOT modified)
    4. Saves JSON outputs for profiles and documentation metadata

    Args:
        repo_path:          Path to the repository root.
        output_dir:         Where to save pipeline artefacts.
                            Defaults to ``data/output/runtime_documentation/``.
        insert_docstrings:  Whether to copy repo and insert docstrings into copied files.
        skip_non_python:    If True, only process Python files (skip JS/TS/Java).

    Returns:
        Dict with keys: components, profiles, documentation, statistics, documented_source_path.
    """
    t0 = time.time()

    repo_path_obj = Path(repo_path).resolve()
    repo_name = repo_path_obj.name
    if not repo_path_obj.exists():
        raise FileNotFoundError(f"Repository not found: {repo_path_obj}")

    out_root = Path(output_dir) if output_dir else (
        _PROJECT_ROOT / "data" / "output" / "runtime_documentation"
    )
    out_root.mkdir(parents=True, exist_ok=True)

    config = get_config()

    # ── Stage 1: Parse repository ────────────────────────────────────
    _print_banner("Stage 1 / 8: Parsing repository")
    parser = RepositoryParser(str(repo_path_obj))
    components: Dict[str, CodeComponent] = parser.parse()
    logger.info(f"Extracted {len(components)} components from {repo_name}")

    # Normalise to standard CodeComponent
    for cid, nav_comp in list(components.items()):
        if not isinstance(nav_comp, CodeComponent):
            comp_type = nav_comp.type
            if not isinstance(comp_type, ComponentType):
                comp_type = ComponentType(comp_type)
            components[cid] = CodeComponent(
                id=getattr(nav_comp, "id", cid),
                name=getattr(nav_comp, "name", cid),
                type=comp_type,
                location=getattr(nav_comp, "location", None),
                source_code=getattr(nav_comp, "source_code", ""),
                signature=getattr(nav_comp, "signature", ""),
                parameters=getattr(nav_comp, "parameters", []),
                return_type=getattr(nav_comp, "return_type", None),
                decorators=getattr(nav_comp, "decorators", []),
                parent_classes=getattr(nav_comp, "parent_classes", []),
                methods=getattr(nav_comp, "methods", []),
                attributes=getattr(nav_comp, "attributes", []),
                existing_docstring=getattr(nav_comp, "existing_docstring", None),
                calls=getattr(nav_comp, "calls", []),
                imports=getattr(nav_comp, "imports", []),
                depends_on=getattr(nav_comp, "depends_on", []),
                complexity=getattr(nav_comp, "complexity", None),
                lines_of_code=getattr(nav_comp, "lines_of_code", 0),
                language=getattr(nav_comp, "language", "python"),
                is_async=getattr(nav_comp, "is_async", False),
                is_generator=getattr(nav_comp, "is_generator", False),
                is_abstract=getattr(nav_comp, "is_abstract", False),
                is_static=getattr(nav_comp, "is_static", False),
                is_class_method=getattr(nav_comp, "is_class_method", False),
                priority=getattr(nav_comp, "priority", 0),
                dependency_level=getattr(nav_comp, "dependency_level", 0),
                metadata=getattr(nav_comp, "metadata", {}),
            )

    # ── Stage 1.5: Copy repository for docstring insertion ───────────
    # Copy source files to output directory so original files are NOT modified
    copied_repo_path: Optional[Path] = None
    if insert_docstrings:
        _print_banner("Stage 1.5 / 8: Copying repository for docstring insertion")
        copied_repo_path = _copy_repository_for_insertion(repo_path_obj, out_root)
        _remap_component_paths(components, repo_path_obj, copied_repo_path)
        logger.info(f"Component paths remapped to: {copied_repo_path}")

    # ── Stage 2: Build dependency graph ──────────────────────────────
    _print_banner("Stage 2 / 8: Building dependency graph")
    graph = build_graph_from_components(components)
    graph = resolve_cycles(graph)
    topo_order = topological_sort(graph)
    dfs_order = dependency_first_dfs(graph)

    ordered_components = [components[cid] for cid in topo_order if cid in components]
    logger.info(f"DAG: {len(graph)} nodes, {sum(len(v) for v in graph.values())} edges")

    # ── Stage 3: Static Runtime Profiling (Python only) ──────────────
    _print_banner("Stage 3 / 8: Static Runtime Profiling (Python)")
    profiler = StaticRuntimeProfiler(str(repo_path_obj))
    profiles = profiler.profile_components(components)

    profiled_count = sum(1 for p in profiles.values() if not p.is_empty)
    logger.info(
        f"Runtime profiles: {len(profiles)} total, "
        f"{profiled_count} with signals"
    )

    # ── Stage 4-7: Agent pipeline (Reader → Searcher → Writer → Verifier)
    _print_banner("Stage 4-7 / 8: Agent pipeline")

    # Initialise agents
    reader = ReaderAgent()
    searcher = SearcherAgent()
    writer = RuntimeWriterAgent()
    verifier = VerifierAgent()

    reader.set_component_map(list(components.values()))

    # Build NetworkX graph for searcher
    nx_graph = nx.DiGraph()
    nx_graph.add_nodes_from(graph.keys())
    for src, targets in graph.items():
        for tgt in targets:
            nx_graph.add_edge(src, tgt)
    searcher.set_repository_data(
        all_components=ordered_components,
        dependency_graph=nx_graph,
    )

    # Config knobs
    max_verifier_rejections = config.get("agents.verifier_agent.max_rejections", 3)
    project_dag = set(components.keys())

    # Docstring inserter (no backup needed - we're working on a copy)
    inserter: Optional[DocstringInserter] = None
    if insert_docstrings:
        inserter = DocstringInserter(
            backup=False,  # No backup needed since we're inserting into copied files
            replace_existing=config.get("system.pipeline.replace_existing_docstrings", False),
        )

    # Stats
    stats = {
        "total": len(ordered_components),
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "skipped": 0,
        "inserted": 0,
        "runtime_enriched": 0,
    }

    documented: List[Documentation] = []

    # ── Sequential processing (batch reader, individual writer) ──────
    batch_size = 5

    for batch_start in range(0, len(ordered_components), batch_size):
        batch = ordered_components[batch_start : batch_start + batch_size]
        batch_end = min(batch_start + batch_size, len(ordered_components))
        logger.info(f"Reader batch {batch_start // batch_size + 1}: components {batch_start + 1}-{batch_end}")

        # Build contexts for entire batch
        batch_contexts: List[AgentContext] = []
        for comp in batch:
            ctx = AgentContext(
                component=comp,
                metadata={
                    "previous_docs": [],
                    "timestamp": datetime.now().isoformat(),
                    "accumulated_context": {"internal": [], "external": []},
                    "project_dag": project_dag,
                    "calibration_history": {
                        "total_searcher_calls": 0,
                        "empty_searcher_results": 0,
                        "total_internal_found": 0,
                        "total_external_found": 0,
                        "rejection_count": 0,
                    },
                },
            )
            batch_contexts.append(ctx)

        # Batch reader
        try:
            reader.process_batch(batch_contexts)
        except Exception as e:
            logger.error(f"Reader batch failed: {e}", exc_info=True)
            stats["failed"] += len(batch)
            stats["processed"] += len(batch)
            continue

        # Individual component processing
        for idx, (comp, context) in enumerate(zip(batch, batch_contexts)):
            overall_idx = batch_start + idx + 1
            ctype = _comp_type_str(comp)

            # Skip components without valid docstring positions
            if ctype in _SKIP_TYPES:
                logger.info(f"[{overall_idx}/{stats['total']}] Skipping {comp.name} (type={ctype})")
                stats["skipped"] += 1
                stats["processed"] += 1
                continue

            # Skip non-Python if requested
            if skip_non_python and comp.language != "python":
                logger.info(f"[{overall_idx}/{stats['total']}] Skipping non-Python: {comp.name}")
                stats["skipped"] += 1
                stats["processed"] += 1
                continue

            logger.info(f"[{overall_idx}/{stats['total']}] Processing {comp.name} ({ctype})")

            # ── Searcher (if reader requested context) ───────────────
            reader_output = context.get_result("reader")
            needs_ctx = False
            if reader_output:
                raw = reader_output if isinstance(reader_output, str) else getattr(reader_output, "xml_output", "")
                needs_ctx = "<INFO_NEED>true</INFO_NEED>" in raw.lower() if raw else False

            if needs_ctx:
                try:
                    searcher_result = searcher.execute(context)
                    if searcher_result.is_success():
                        context.add_result("searcher", searcher_result.output)
                except Exception as e:
                    logger.warning(f"Searcher failed for {comp.name}: {e}")

            # ── Writer ───────────────────────────────────────────────
            try:
                writer_result = writer.execute(context)
                if not writer_result.is_success():
                    logger.warning(f"Writer failed for {comp.name}: {writer_result.error}")
                    stats["failed"] += 1
                    stats["processed"] += 1
                    continue

                documentation = writer_result.output
                context.add_result("writer", documentation)
            except Exception as e:
                logger.error(f"Writer error for {comp.name}: {e}")
                stats["failed"] += 1
                stats["processed"] += 1
                continue

            # ── Verifier loop ────────────────────────────────────────
            rejection_count = 0
            while rejection_count < max_verifier_rejections:
                try:
                    verifier_result = verifier.execute(context)
                    if not verifier_result.is_success():
                        break  # accept current documentation

                    verification = verifier_result.output
                    context.add_result("verifier", verification)

                    if not verification.need_revision:
                        logger.info(f"Verifier accepted {comp.name}")
                        break

                    rejection_count += 1
                    suggestion = getattr(verification, "suggestion", "") or "Improve quality."
                    logger.info(
                        f"Verifier rejected {comp.name} ({rejection_count}/{max_verifier_rejections}): "
                        f"{suggestion[:100]}"
                    )

                    refined = writer.refine_documentation(context, suggestion)
                    if refined.is_success():
                        documentation = refined.output
                        context.add_result("writer", documentation)
                    verifier.clear_memory()
                except Exception as e:
                    logger.warning(f"Verifier error for {comp.name}: {e}")
                    break

            # ── Docstring insertion ──────────────────────────────────
            if inserter and documentation and documentation.docstring:
                try:
                    # DocstringInserter.insert_for_component expects docstring_data dict
                    docstring_data = {
                        "docstring": documentation.docstring,
                        "component_id": documentation.component_id,
                        "component_name": documentation.component_name,
                    }
                    result = inserter.insert_for_component(comp, docstring_data)
                    if result.success:
                        stats["inserted"] += 1
                    else:
                        logger.debug(f"Insertion skipped for {comp.name}: {result.message}")
                except Exception as e:
                    logger.warning(f"Insertion failed for {comp.name}: {e}")

            # Track runtime enrichment
            profile = profiles.get(comp.id)
            if profile and not profile.is_empty:
                stats["runtime_enriched"] += 1

            documented.append(documentation)
            stats["successful"] += 1
            stats["processed"] += 1

    # ── Stage 8: Save outputs ────────────────────────────────────────
    _print_banner("Stage 8 / 8: Saving outputs")

    # Save documentation JSON
    docs_path = out_root / f"{repo_name}_runtime_docs.json"
    try:
        serialized = {}
        for doc in documented:
            if hasattr(doc, "to_dict"):
                serialized[doc.component_id] = doc.to_dict()
            else:
                serialized[doc.component_id] = FileHandler.serialize_component(doc)
        FileHandler.write_json(docs_path, serialized)
        logger.info(f"Documentation saved to {docs_path}")
    except Exception as e:
        logger.warning(f"Failed to save docs: {e}")

    # Save runtime profiles JSON
    profiles_path = out_root / f"{repo_name}_runtime_profiles.json"
    try:
        profiles_serialized = {
            cid: p.to_dict() for cid, p in profiles.items()
        }
        FileHandler.write_json(profiles_path, profiles_serialized)
        logger.info(f"Profiles saved to {profiles_path}")
    except Exception as e:
        logger.warning(f"Failed to save profiles: {e}")

    elapsed = time.time() - t0
    stats["elapsed_seconds"] = round(elapsed, 2)
    stats["success_rate"] = round(
        (stats["successful"] / max(stats["processed"], 1)) * 100, 2
    )

    # Print summary
    _print_banner("Runtime-Aware Pipeline Complete")
    print(f"  Repository:           {repo_name}")
    print(f"  Total components:     {stats['total']}")
    print(f"  Processed:            {stats['processed']}")
    print(f"  Successful:           {stats['successful']}")
    print(f"  Failed:               {stats['failed']}")
    print(f"  Skipped:              {stats['skipped']}")
    print(f"  Runtime-enriched:     {stats['runtime_enriched']}")
    print(f"  Docstrings inserted:  {stats['inserted']}")
    print(f"  Success rate:         {stats['success_rate']}%")
    print(f"  Elapsed:              {stats['elapsed_seconds']}s")
    print()
    print("  OUTPUT LOCATIONS:")
    print(f"    JSON docs:          {docs_path}")
    print(f"    JSON profiles:      {profiles_path}")
    if copied_repo_path:
        print(f"    Documented source:  {copied_repo_path}")
        print()
        print("  NOTE: Docstrings were inserted into the COPIED source files above.")
        print("        Original repository files were NOT modified.")
    print()

    return {
        "components": components,
        "profiles": profiles,
        "documentation": documented,
        "statistics": stats,
        "documented_source_path": str(copied_repo_path) if copied_repo_path else None,
    }


# ======================================================================
# CLI entry point
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Run the runtime-aware documentation pipeline on a Python repository.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.run_runtime_pipeline data/input/repositories/MyRepo
  python -m scripts.run_runtime_pipeline /absolute/path/to/repo --no-insert
  python -m scripts.run_runtime_pipeline data/input/repositories/MyRepo --python-only
""",
    )
    parser.add_argument(
        "repo_path",
        help="Path to the repository to document (relative or absolute).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Custom output directory for pipeline artefacts.",
    )
    parser.add_argument(
        "--no-insert",
        action="store_true",
        help="Do not insert docstrings into source files.",
    )
    parser.add_argument(
        "--python-only",
        action="store_true",
        help="Only process Python components (skip JS/TS/Java).",
    )

    args = parser.parse_args()

    # Resolve relative paths from project root
    repo = Path(args.repo_path)
    if not repo.is_absolute():
        repo = (_PROJECT_ROOT / repo).resolve()

    result = run_runtime_pipeline(
        repo_path=str(repo),
        output_dir=args.output_dir,
        insert_docstrings=not args.no_insert,
        skip_non_python=args.python_only,
    )

    # Exit code
    sys.exit(0 if result["statistics"]["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
