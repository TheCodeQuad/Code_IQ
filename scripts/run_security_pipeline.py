"""
Security-Aware Documentation Pipeline (standalone)

Usage:
    python -m scripts.run_security_pipeline <repo_path> [--output-dir DIR]
    python -m scripts.run_security_pipeline data/input/repositories/MyPythonRepo

This script runs the security-aware documentation pipeline that:
1. Scans code for security vulnerabilities (no LLM required)
2. Generates documentation that includes security warnings
3. Produces a comprehensive security report

OUTPUT STRUCTURE:
    {output_dir}/
    ├── documented_source/{repo_name}/       # Source with security-aware docstrings
    │   ├── src/
    │   │   └── *.py  (with docstrings including security warnings)
    │   └── ...
    ├── {repo_name}_security_docs.json       # Documentation metadata
    ├── {repo_name}_security_profiles.json   # Detailed security profiles
    ├── {repo_name}_security_report.md       # Human-readable security report
    └── {repo_name}_vulnerabilities.json     # Vulnerability-only export

Pipeline stages:
    1.   Navigator          - Parse repository → CodeComponents
    1.5  Copy               - Copy source files for safe insertion
    2.   DAG                - Build dependency graph, topological sort
    3.   SecurityProfiler   - Static vulnerability scanning → SecurityProfile
    3.5  RuntimeProfiler    - Runtime signals (optional, for richer docs)
    4.   Reader             - Code analysis (batched)
    5.   Searcher           - Internal/external context gathering
    6.   SecurityWriter     - LLM docstring generation with security signals
    7.   Verifier           - Quality gate (optional)
    8.   Inserter           - Write docstrings into COPIED source files
    9.   ReportGenerator    - Generate security reports

The pipeline supports Python, JavaScript, TypeScript, and Java.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import networkx as nx

from backend.agents.base_agent import AgentContext, AgentResult, AgentStatus
from backend.agents.reader_agent import ReaderAgent
from backend.agents.runtime_profiler import StaticRuntimeProfiler
from backend.agents.searcher_agent import SearcherAgent
from backend.agents.security_profiler import StaticSecurityProfiler
from backend.agents.security_writer_agent import SecurityWriterAgent
from backend.agents.verifier_agent import VerifierAgent
from backend.models.code_component import CodeComponent, ComponentType
from backend.models.documentation import Documentation
from backend.models.runtime_profile import RuntimeProfile
from backend.models.security_profile import SecurityProfile, Severity
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

logger = get_logger("security_pipeline")

# Component types that have no docstring insertion point
_SKIP_TYPES = {"global_variable", "static_field", "field", "import", "variable"}

# File extensions to copy
_SOURCE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".cpp", ".c", ".h", ".hpp", ".cs"
}


# ======================================================================
# Helper Functions
# ======================================================================

def _print_banner(msg: str) -> None:
    """Print a formatted banner."""
    width = max(len(msg) + 4, 60)
    print("=" * width)
    print(f"  {msg}")
    print("=" * width)


def _comp_type_str(comp: CodeComponent) -> str:
    """Get component type as string."""
    t = comp.type
    return t.value if hasattr(t, "value") else str(t)


def _copy_repository_for_insertion(
    source_repo: Path,
    output_dir: Path,
) -> Path:
    """Copy source code files to output directory for docstring insertion."""
    repo_name = source_repo.name
    dest_repo = output_dir / "documented_source" / repo_name

    if dest_repo.exists():
        shutil.rmtree(dest_repo)

    skip_dirs = {
        "node_modules", "__pycache__", ".git", ".venv", "venv",
        "env", ".env", "dist", "build", ".pytest_cache", ".mypy_cache",
        ".tox", "eggs", "*.egg-info", ".eggs"
    }

    copied_files = 0
    for src_file in source_repo.rglob("*"):
        if src_file.is_dir():
            continue
        if any(skip_dir in src_file.parts for skip_dir in skip_dirs):
            continue
        if src_file.suffix.lower() not in _SOURCE_EXTENSIONS:
            continue

        rel_path = src_file.relative_to(source_repo)
        dest_file = dest_repo / rel_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest_file)
        copied_files += 1

    logger.info(f"Copied {copied_files} source files to {dest_repo}")
    return dest_repo


def _remap_component_paths(
    components: Dict[str, CodeComponent],
    original_repo: Path,
    copied_repo: Path,
) -> None:
    """Update file paths in components to point to copied repository."""
    original_str = str(original_repo.resolve())
    copied_str = str(copied_repo.resolve())

    for comp in components.values():
        if hasattr(comp, 'location') and comp.location:
            original_path = comp.location.file_path
            if original_path and original_str in original_path:
                comp.location.file_path = original_path.replace(original_str, copied_str)
        if hasattr(comp, 'file_path') and comp.file_path:
            if original_str in comp.file_path:
                comp.file_path = comp.file_path.replace(original_str, copied_str)


def _generate_security_report(
    repo_name: str,
    security_profiles: Dict[str, SecurityProfile],
    components: Dict[str, CodeComponent],
    output_path: Path,
) -> None:
    """Generate a human-readable security report in Markdown format."""
    lines = []
    lines.append(f"# Security Report: {repo_name}")
    lines.append(f"\nGenerated: {datetime.now().isoformat()}")
    lines.append("\n---\n")

    # Summary statistics
    total_vulns = sum(len(p.vulnerabilities) for p in security_profiles.values())
    components_with_vulns = sum(1 for p in security_profiles.values() if p.has_vulnerabilities)
    security_relevant = sum(1 for p in security_profiles.values() if p.is_security_relevant)

    # Count by severity
    severity_counts = defaultdict(int)
    for profile in security_profiles.values():
        for vuln in profile.vulnerabilities:
            sev = vuln.severity.value if hasattr(vuln.severity, 'value') else str(vuln.severity)
            severity_counts[sev] += 1

    lines.append("## Executive Summary\n")
    lines.append(f"- **Total Components Analyzed:** {len(components)}")
    lines.append(f"- **Components with Vulnerabilities:** {components_with_vulns}")
    lines.append(f"- **Security-Relevant Components:** {security_relevant}")
    lines.append(f"- **Total Vulnerabilities Found:** {total_vulns}")
    lines.append("")

    if total_vulns > 0:
        lines.append("### Vulnerability Severity Distribution\n")
        lines.append("| Severity | Count |")
        lines.append("|----------|-------|")
        for sev in ["critical", "high", "medium", "low", "info"]:
            if severity_counts[sev] > 0:
                lines.append(f"| {sev.upper()} | {severity_counts[sev]} |")
        lines.append("")

    # Critical and High vulnerabilities detail
    critical_high = []
    for cid, profile in security_profiles.items():
        comp = components.get(cid)
        comp_name = comp.name if comp else cid
        for vuln in profile.vulnerabilities:
            if vuln.severity in (Severity.CRITICAL, Severity.HIGH):
                critical_high.append((comp_name, vuln))

    if critical_high:
        lines.append("## Critical & High Severity Vulnerabilities\n")
        lines.append("These require immediate attention.\n")

        for comp_name, vuln in sorted(critical_high, key=lambda x: x[1].severity.value):
            sev = vuln.severity.value.upper()
            lines.append(f"### [{sev}] {vuln.cwe_id}: {vuln.cwe_name}")
            lines.append(f"\n**Component:** `{comp_name}`")
            if vuln.line_number:
                lines.append(f"**Line:** {vuln.line_number}")
            lines.append(f"\n**Description:** {vuln.description}")
            if vuln.code_snippet:
                lines.append(f"\n**Vulnerable Code:**")
                lines.append(f"```python\n{vuln.code_snippet}\n```")
            lines.append(f"\n**Mitigation:** {vuln.mitigation}")
            if vuln.secure_alternative:
                lines.append(f"\n**Secure Alternative:**")
                lines.append(f"```python\n{vuln.secure_alternative}\n```")
            lines.append("\n---\n")

    # All vulnerabilities by CWE
    if total_vulns > 0:
        lines.append("## Vulnerabilities by Type\n")

        by_cwe = defaultdict(list)
        for cid, profile in security_profiles.items():
            comp = components.get(cid)
            for vuln in profile.vulnerabilities:
                by_cwe[vuln.cwe_id].append((comp, vuln))

        for cwe_id in sorted(by_cwe.keys()):
            vulns = by_cwe[cwe_id]
            first_vuln = vulns[0][1]
            lines.append(f"### {cwe_id}: {first_vuln.cwe_name} ({len(vulns)} instances)")
            lines.append(f"\n{first_vuln.description}\n")

            lines.append("| Component | Line | Severity |")
            lines.append("|-----------|------|----------|")
            for comp, vuln in vulns:
                comp_name = comp.name if comp else "unknown"
                line = vuln.line_number or "-"
                sev = vuln.severity.value if hasattr(vuln.severity, 'value') else str(vuln.severity)
                lines.append(f"| {comp_name} | {line} | {sev.upper()} |")
            lines.append("")

    # Security-relevant components without vulnerabilities
    safe_security_components = [
        (cid, components.get(cid))
        for cid, profile in security_profiles.items()
        if profile.is_security_relevant and not profile.has_vulnerabilities
    ]

    if safe_security_components:
        lines.append("## Security-Relevant Components (No Vulnerabilities Detected)\n")
        lines.append("These components handle security-sensitive operations but passed static analysis.\n")

        for cid, comp in safe_security_components[:20]:  # Limit to 20
            comp_name = comp.name if comp else cid
            profile = security_profiles.get(cid)
            flags = []
            if profile:
                if profile.handles_authentication:
                    flags.append("authentication")
                if profile.handles_authorization:
                    flags.append("authorization")
                if profile.handles_cryptography:
                    flags.append("cryptography")
                if profile.handles_user_input:
                    flags.append("user input")
                if profile.handles_database:
                    flags.append("database")
            lines.append(f"- `{comp_name}`: {', '.join(flags) if flags else 'security-relevant'}")
        lines.append("")

    # Positive security patterns
    all_patterns = set()
    for profile in security_profiles.values():
        all_patterns.update(profile.security_patterns)

    if all_patterns:
        lines.append("## Positive Security Patterns Detected\n")
        lines.append("Good security practices found in the codebase:\n")
        for pattern in sorted(all_patterns):
            readable = pattern.replace("_", " ").replace("uses ", "").title()
            lines.append(f"- {readable}")
        lines.append("")

    # Recommendations
    lines.append("## Recommendations\n")

    if severity_counts.get("critical", 0) > 0:
        lines.append("1. **URGENT:** Address all CRITICAL vulnerabilities immediately")
    if severity_counts.get("high", 0) > 0:
        lines.append("2. **HIGH PRIORITY:** Fix HIGH severity issues within this sprint")
    if total_vulns > 0:
        lines.append("3. Review all flagged code and apply recommended mitigations")
        lines.append("4. Consider adding security-focused code review requirements")
    lines.append("5. Run this scanner regularly as part of CI/CD pipeline")
    lines.append("6. Consider additional dynamic testing (DAST) for runtime validation")
    lines.append("")

    # Write report
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Security report saved to {output_path}")


def _export_vulnerabilities(
    security_profiles: Dict[str, SecurityProfile],
    components: Dict[str, CodeComponent],
    output_path: Path,
) -> None:
    """Export vulnerabilities in a structured JSON format for integration."""
    vulnerabilities = []

    for cid, profile in security_profiles.items():
        comp = components.get(cid)
        comp_name = comp.name if comp else cid
        file_path = ""
        if comp and hasattr(comp, 'location') and comp.location:
            file_path = comp.location.file_path or ""

        for vuln in profile.vulnerabilities:
            vulnerabilities.append({
                "component_id": cid,
                "component_name": comp_name,
                "file_path": file_path,
                "cwe_id": vuln.cwe_id,
                "cwe_name": vuln.cwe_name,
                "category": vuln.category.value if hasattr(vuln.category, 'value') else vuln.category,
                "severity": vuln.severity.value if hasattr(vuln.severity, 'value') else vuln.severity,
                "description": vuln.description,
                "line_number": vuln.line_number,
                "code_snippet": vuln.code_snippet,
                "mitigation": vuln.mitigation,
                "secure_alternative": vuln.secure_alternative,
                "confidence": vuln.confidence,
                "references": vuln.references,
            })

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    vulnerabilities.sort(key=lambda v: severity_order.get(v["severity"], 5))

    output = {
        "scan_timestamp": datetime.now().isoformat(),
        "total_vulnerabilities": len(vulnerabilities),
        "severity_counts": {
            "critical": sum(1 for v in vulnerabilities if v["severity"] == "critical"),
            "high": sum(1 for v in vulnerabilities if v["severity"] == "high"),
            "medium": sum(1 for v in vulnerabilities if v["severity"] == "medium"),
            "low": sum(1 for v in vulnerabilities if v["severity"] == "low"),
            "info": sum(1 for v in vulnerabilities if v["severity"] == "info"),
        },
        "vulnerabilities": vulnerabilities,
    }

    FileHandler.write_json(output_path, output)
    logger.info(f"Vulnerability export saved to {output_path}")


# ======================================================================
# Main Pipeline Function
# ======================================================================

def run_security_pipeline(
    repo_path: str,
    output_dir: Optional[str] = None,
    insert_docstrings: bool = True,
    include_runtime_signals: bool = True,
    skip_llm: bool = False,
    security_scan_only: bool = False,
) -> Dict[str, Any]:
    """
    Run the security-aware documentation pipeline on a repository.

    Args:
        repo_path:              Path to the repository root.
        output_dir:             Output directory for artifacts.
                                Defaults to data/output/security_documentation/
        insert_docstrings:      Whether to insert docstrings into copied source files.
        include_runtime_signals: Include runtime profiler signals in documentation.
        skip_llm:               Skip LLM-based documentation generation.
                                Useful for security-scan-only mode.
        security_scan_only:     Only run security scanner, skip full documentation.
                                Implies skip_llm=True.

    Returns:
        Dict with keys: components, security_profiles, runtime_profiles,
                        documentation, statistics, documented_source_path.
    """
    t0 = time.time()

    if security_scan_only:
        skip_llm = True
        insert_docstrings = False

    repo_path_obj = Path(repo_path).resolve()
    repo_name = repo_path_obj.name

    if not repo_path_obj.exists():
        raise FileNotFoundError(f"Repository not found: {repo_path_obj}")

    out_root = Path(output_dir) if output_dir else (
        _PROJECT_ROOT / "data" / "output" / "security_documentation"
    )
    out_root.mkdir(parents=True, exist_ok=True)

    config = get_config()

    # ── Stage 1: Parse repository ────────────────────────────────────
    _print_banner("Stage 1 / 9: Parsing repository")
    parser = RepositoryParser(str(repo_path_obj))
    components: Dict[str, CodeComponent] = parser.parse()
    logger.info(f"Extracted {len(components)} components from {repo_name}")

    # Normalize to standard CodeComponent
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
    copied_repo_path: Optional[Path] = None
    if insert_docstrings:
        _print_banner("Stage 1.5 / 9: Copying repository for docstring insertion")
        copied_repo_path = _copy_repository_for_insertion(repo_path_obj, out_root)
        _remap_component_paths(components, repo_path_obj, copied_repo_path)
        logger.info(f"Component paths remapped to: {copied_repo_path}")

    # ── Stage 2: Build dependency graph ──────────────────────────────
    _print_banner("Stage 2 / 9: Building dependency graph")
    graph = build_graph_from_components(components)
    graph = resolve_cycles(graph)
    topo_order = topological_sort(graph)

    ordered_components = [components[cid] for cid in topo_order if cid in components]
    logger.info(f"DAG: {len(graph)} nodes, {sum(len(v) for v in graph.values())} edges")

    # ── Stage 3: Security Profiling ──────────────────────────────────
    _print_banner("Stage 3 / 9: Security Vulnerability Scanning")
    security_profiler = StaticSecurityProfiler(str(repo_path_obj))
    security_profiles = security_profiler.profile_components(components)

    total_vulns = sum(len(p.vulnerabilities) for p in security_profiles.values())
    components_with_vulns = sum(1 for p in security_profiles.values() if p.has_vulnerabilities)

    logger.info(
        f"Security scan complete: {total_vulns} vulnerabilities "
        f"in {components_with_vulns}/{len(components)} components"
    )

    # Attach security profiles to components
    for cid, profile in security_profiles.items():
        if cid in components:
            if components[cid].metadata is None:
                components[cid].metadata = {}
            components[cid].metadata["security_profile"] = profile

    # ── Stage 3.5: Runtime Profiling (optional) ──────────────────────
    runtime_profiles: Dict[str, RuntimeProfile] = {}
    if include_runtime_signals and not security_scan_only:
        _print_banner("Stage 3.5 / 9: Runtime Profiling")
        runtime_profiler = StaticRuntimeProfiler(str(repo_path_obj))
        runtime_profiles = runtime_profiler.profile_components(components)

        for cid, profile in runtime_profiles.items():
            if cid in components:
                if components[cid].metadata is None:
                    components[cid].metadata = {}
                components[cid].metadata["runtime_profile"] = profile

        profiled_count = sum(1 for p in runtime_profiles.values() if not p.is_empty)
        logger.info(f"Runtime profiles: {profiled_count} with signals")

    # ── Save Security Reports (early, even if skipping LLM) ──────────
    _print_banner("Stage 9 / 9: Generating Security Reports")

    # Save security profiles JSON
    profiles_path = out_root / f"{repo_name}_security_profiles.json"
    try:
        profiles_serialized = {
            cid: p.to_dict() for cid, p in security_profiles.items()
        }
        FileHandler.write_json(profiles_path, profiles_serialized)
        logger.info(f"Security profiles saved to {profiles_path}")
    except Exception as e:
        logger.warning(f"Failed to save security profiles: {e}")

    # Generate security report
    report_path = out_root / f"{repo_name}_security_report.md"
    try:
        _generate_security_report(repo_name, security_profiles, components, report_path)
    except Exception as e:
        logger.warning(f"Failed to generate security report: {e}")

    # Export vulnerabilities
    vulns_path = out_root / f"{repo_name}_vulnerabilities.json"
    try:
        _export_vulnerabilities(security_profiles, components, vulns_path)
    except Exception as e:
        logger.warning(f"Failed to export vulnerabilities: {e}")

    # Early exit for security-scan-only mode
    if security_scan_only:
        elapsed = time.time() - t0
        stats = {
            "total": len(components),
            "vulnerabilities_found": total_vulns,
            "components_with_vulnerabilities": components_with_vulns,
            "elapsed_seconds": round(elapsed, 2),
        }

        _print_banner("Security Scan Complete")
        print(f"  Repository:            {repo_name}")
        print(f"  Components scanned:    {len(components)}")
        print(f"  Vulnerabilities found: {total_vulns}")
        print(f"  Affected components:   {components_with_vulns}")
        print(f"  Elapsed:               {elapsed:.2f}s")
        print()
        print("  OUTPUT LOCATIONS:")
        print(f"    Security profiles:   {profiles_path}")
        print(f"    Security report:     {report_path}")
        print(f"    Vulnerabilities:     {vulns_path}")
        print()

        return {
            "components": components,
            "security_profiles": security_profiles,
            "runtime_profiles": {},
            "documentation": [],
            "statistics": stats,
            "documented_source_path": None,
        }

    # ── Stage 4-8: Agent pipeline (if not skipping LLM) ──────────────
    if not skip_llm:
        _print_banner("Stage 4-8 / 9: Agent pipeline")

        # Initialize agents
        reader = ReaderAgent()
        searcher = SearcherAgent()
        writer = SecurityWriterAgent()
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

        # Config
        max_verifier_rejections = config.get("agents.verifier_agent.max_rejections", 3)
        project_dag = set(components.keys())

        # Docstring inserter
        inserter: Optional[DocstringInserter] = None
        if insert_docstrings:
            inserter = DocstringInserter(
                backup=False,
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
            "vulnerabilities_found": total_vulns,
            "components_with_vulnerabilities": components_with_vulns,
            "security_docs_generated": 0,
        }

        documented: List[Documentation] = []
        batch_size = 5

        for batch_start in range(0, len(ordered_components), batch_size):
            batch = ordered_components[batch_start : batch_start + batch_size]
            batch_end = min(batch_start + batch_size, len(ordered_components))
            logger.info(f"Reader batch {batch_start // batch_size + 1}: components {batch_start + 1}-{batch_end}")

            # Build contexts
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

            # Process individual components
            for idx, (comp, context) in enumerate(zip(batch, batch_contexts)):
                overall_idx = batch_start + idx + 1
                ctype = _comp_type_str(comp)

                if ctype in _SKIP_TYPES:
                    logger.info(f"[{overall_idx}/{stats['total']}] Skipping {comp.name} (type={ctype})")
                    stats["skipped"] += 1
                    stats["processed"] += 1
                    continue

                # Check security relevance
                sec_profile = security_profiles.get(comp.id)
                has_security_content = (
                    sec_profile and
                    (sec_profile.has_vulnerabilities or sec_profile.is_security_relevant)
                )

                logger.info(
                    f"[{overall_idx}/{stats['total']}] Processing {comp.name} ({ctype})"
                    f"{' [SECURITY]' if has_security_content else ''}"
                )

                # Searcher (if reader requested context)
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

                # Writer
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

                # Verifier loop
                rejection_count = 0
                while rejection_count < max_verifier_rejections:
                    try:
                        verifier_result = verifier.execute(context)
                        if not verifier_result.is_success():
                            break

                        verification = verifier_result.output
                        context.add_result("verifier", verification)

                        if not verification.need_revision:
                            logger.info(f"Verifier accepted {comp.name}")
                            break

                        rejection_count += 1
                        suggestion = getattr(verification, "suggestion", "") or "Improve quality."
                        logger.info(
                            f"Verifier rejected {comp.name} ({rejection_count}/{max_verifier_rejections})"
                        )

                        refined = writer.refine_documentation(context, suggestion)
                        if refined.is_success():
                            documentation = refined.output
                            context.add_result("writer", documentation)
                        verifier.clear_memory()
                    except Exception as e:
                        logger.warning(f"Verifier error for {comp.name}: {e}")
                        break

                # Docstring insertion
                if inserter and documentation and documentation.docstring:
                    try:
                        docstring_data = {
                            "docstring": documentation.docstring,
                            "component_id": documentation.component_id,
                            "component_name": documentation.component_name,
                        }
                        result = inserter.insert_for_component(comp, docstring_data)
                        if result.success:
                            stats["inserted"] += 1
                    except Exception as e:
                        logger.warning(f"Insertion failed for {comp.name}: {e}")

                # Track security docs
                if has_security_content:
                    stats["security_docs_generated"] += 1

                documented.append(documentation)
                stats["successful"] += 1
                stats["processed"] += 1

        # Save documentation JSON
        docs_path = out_root / f"{repo_name}_security_docs.json"
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

    else:
        documented = []
        stats = {
            "total": len(components),
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "skipped": len(components),
            "inserted": 0,
            "vulnerabilities_found": total_vulns,
            "components_with_vulnerabilities": components_with_vulns,
            "security_docs_generated": 0,
        }
        docs_path = None

    # Save runtime profiles (if generated)
    if runtime_profiles:
        runtime_path = out_root / f"{repo_name}_runtime_profiles.json"
        try:
            runtime_serialized = {
                cid: p.to_dict() for cid, p in runtime_profiles.items()
            }
            FileHandler.write_json(runtime_path, runtime_serialized)
            logger.info(f"Runtime profiles saved to {runtime_path}")
        except Exception as e:
            logger.warning(f"Failed to save runtime profiles: {e}")

    elapsed = time.time() - t0
    stats["elapsed_seconds"] = round(elapsed, 2)
    if stats["processed"] > 0:
        stats["success_rate"] = round(
            (stats["successful"] / max(stats["processed"], 1)) * 100, 2
        )
    else:
        stats["success_rate"] = 0

    # Print summary
    _print_banner("Security Documentation Pipeline Complete")
    print(f"  Repository:               {repo_name}")
    print(f"  Total components:         {stats['total']}")
    print(f"  Vulnerabilities found:    {stats['vulnerabilities_found']}")
    print(f"  Affected components:      {stats['components_with_vulnerabilities']}")

    if not skip_llm:
        print(f"  Processed:                {stats['processed']}")
        print(f"  Successful:               {stats['successful']}")
        print(f"  Failed:                   {stats['failed']}")
        print(f"  Security docs generated:  {stats['security_docs_generated']}")
        print(f"  Docstrings inserted:      {stats['inserted']}")
        print(f"  Success rate:             {stats['success_rate']}%")

    print(f"  Elapsed:                  {stats['elapsed_seconds']}s")
    print()
    print("  OUTPUT LOCATIONS:")
    print(f"    Security profiles:      {profiles_path}")
    print(f"    Security report:        {report_path}")
    print(f"    Vulnerabilities:        {vulns_path}")

    if not skip_llm and docs_path:
        print(f"    Documentation JSON:     {docs_path}")

    if copied_repo_path:
        print(f"    Documented source:      {copied_repo_path}")
        print()
        print("  NOTE: Docstrings with security warnings inserted into COPIED files.")
        print("        Original repository files were NOT modified.")
    print()

    return {
        "components": components,
        "security_profiles": security_profiles,
        "runtime_profiles": runtime_profiles,
        "documentation": documented,
        "statistics": stats,
        "documented_source_path": str(copied_repo_path) if copied_repo_path else None,
    }


# ======================================================================
# CLI Entry Point
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Run the security-aware documentation pipeline on a repository.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline with security documentation
  python -m scripts.run_security_pipeline data/input/repositories/MyRepo

  # Security scan only (no LLM, fast)
  python -m scripts.run_security_pipeline data/input/repositories/MyRepo --scan-only

  # Without runtime signals
  python -m scripts.run_security_pipeline data/input/repositories/MyRepo --no-runtime

  # Custom output directory
  python -m scripts.run_security_pipeline /path/to/repo --output-dir ./security_output
""",
    )
    parser.add_argument(
        "repo_path",
        help="Path to the repository to analyze (relative or absolute).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Custom output directory for pipeline artifacts.",
    )
    parser.add_argument(
        "--no-insert",
        action="store_true",
        help="Do not insert docstrings into source files.",
    )
    parser.add_argument(
        "--no-runtime",
        action="store_true",
        help="Skip runtime profiler signals.",
    )
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Only run security scanner, skip LLM documentation generation.",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM-based documentation (still generates security reports).",
    )

    args = parser.parse_args()

    # Resolve relative paths
    repo = Path(args.repo_path)
    if not repo.is_absolute():
        repo = (_PROJECT_ROOT / repo).resolve()

    result = run_security_pipeline(
        repo_path=str(repo),
        output_dir=args.output_dir,
        insert_docstrings=not args.no_insert,
        include_runtime_signals=not args.no_runtime,
        skip_llm=args.skip_llm,
        security_scan_only=args.scan_only,
    )

    # Exit code based on vulnerabilities
    vulns = result["statistics"].get("vulnerabilities_found", 0)
    critical_high = sum(
        1 for p in result["security_profiles"].values()
        for v in p.vulnerabilities
        if v.severity in (Severity.CRITICAL, Severity.HIGH)
    )

    if critical_high > 0:
        sys.exit(2)  # Critical/high vulnerabilities found
    elif vulns > 0:
        sys.exit(1)  # Medium/low vulnerabilities found
    else:
        sys.exit(0)  # Clean


if __name__ == "__main__":
    main()
