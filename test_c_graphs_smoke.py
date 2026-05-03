#!/usr/bin/env python3
"""Smoke test: C language support — adapter, extraction, and graph generation.

Creates a temporary mini-repo with C files, runs Navigator parsing
through GraphService, then requests CFG/PDG/HPG for a C function.

Run:
  python test_c_graphs_smoke.py

Requires: tree-sitter + tree-sitter-languages installed (already in requirements.txt)
"""

from __future__ import annotations

import os
import sys
import shutil
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# Phase 0: verify tree-sitter can parse C
# ---------------------------------------------------------------------------
def phase0_treesitter():
    print("\n" + "=" * 60)
    print("[PHASE 0] Verify tree-sitter C parser")
    print("=" * 60)
    from backend.navigator.treesitter.parser_factory import get_ts_parser

    parser = get_ts_parser("c")
    tree = parser.parse(b"int main() { return 0; }")
    root = tree.root_node
    print(f"  Root type : {root.type}")
    print(f"  Children  : {root.child_count}")
    assert root.type == "translation_unit", f"Unexpected root type: {root.type}"
    print("  ✓ tree-sitter C parser works")
    return True


# ---------------------------------------------------------------------------
# Phase 1: verify CAdapter registration + parse
# ---------------------------------------------------------------------------
def phase1_adapter():
    print("\n" + "=" * 60)
    print("[PHASE 1] CAdapter registration & component extraction")
    print("=" * 60)
    from backend.navigator.languages.adapter_registry import AdapterRegistry

    registry = AdapterRegistry()
    adapter = registry.get_adapter_for_file("example.c")
    assert adapter is not None, "No adapter found for .c files"
    assert adapter.language == "c", f"Expected language 'c', got '{adapter.language}'"
    print(f"  Adapter for .c  : {adapter.__class__.__name__} (language={adapter.language})")

    adapter_h = registry.get_adapter_for_file("example.h")
    assert adapter_h is not None, "No adapter found for .h files"
    print(f"  Adapter for .h  : {adapter_h.__class__.__name__} (language={adapter_h.language})")

    # Parse a small C snippet
    source = r"""
#include <stdio.h>
#include <stdlib.h>

/** A 2D point. */
typedef struct {
    double x;
    double y;
} Point;

/** Compute distance between two points. */
double distance(Point *a, Point *b) {
    double dx = a->x - b->x;
    double dy = a->y - b->y;
    return sqrt(dx * dx + dy * dy);
}

/** Create a new point on the heap. */
Point *make_point(double x, double y) {
    Point *p = (Point *)malloc(sizeof(Point));
    if (p) {
        p->x = x;
        p->y = y;
    }
    return p;
}

/** Simple factorial. */
int factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}

enum Color {
    RED,
    GREEN,
    BLUE
};

int global_counter = 0;
"""

    tree = adapter.parse(source)
    components = adapter.extract_components(tree, source, "test.c", "test")

    print(f"\n  Components extracted: {len(components)}")
    for cid, comp in sorted(components.items()):
        ctype = getattr(comp.type, "value", comp.type)
        print(f"    {ctype:20s}  {cid}")

    # Verify key components exist
    assert "test.distance" in components, "Missing function: distance"
    assert "test.make_point" in components, "Missing function: make_point"
    assert "test.factorial" in components, "Missing function: factorial"
    assert "test.Point" in components, "Missing struct/typedef: Point"
    assert "test.Color" in components, "Missing enum: Color"
    print("\n  ✓ All expected components found")

    # Verify parameters
    dist = components["test.distance"]
    print(f"\n  distance() params: {[(p.name, p.type_hint) for p in dist.parameters]}")
    assert len(dist.parameters) == 2, f"Expected 2 params, got {len(dist.parameters)}"

    fact = components["test.factorial"]
    print(f"  factorial() params: {[(p.name, p.type_hint) for p in fact.parameters]}")
    assert len(fact.parameters) == 1, f"Expected 1 param, got {len(fact.parameters)}"

    # Verify docstrings
    assert dist.existing_docstring is not None, "distance() should have a docstring"
    print(f"  distance() docstring: {dist.existing_docstring[:50]}...")

    # Verify return type
    assert dist.return_type == "double", f"Expected return type 'double', got '{dist.return_type}'"
    print(f"  distance() return_type: {dist.return_type}")

    print("\n  ✓ Parameter, docstring, and return type extraction works")
    return components, tree, source


# ---------------------------------------------------------------------------
# Phase 2: dependency resolution
# ---------------------------------------------------------------------------
def phase2_dependencies(components, tree, source):
    print("\n" + "=" * 60)
    print("[PHASE 2] Dependency resolution")
    print("=" * 60)
    from backend.navigator.languages.c.adapter import CAdapter

    adapter = CAdapter()
    for cid, comp in components.items():
        deps = adapter.resolve_dependencies(comp, tree, source, components)
        if deps:
            print(f"  {cid} depends on: {deps}")

    # make_point should depend on Point (it uses Point type)
    mp = components["test.make_point"]
    mp_deps = adapter.resolve_dependencies(mp, tree, source, components)
    print(f"\n  make_point deps: {mp_deps}")
    # Point should be in make_point's deps (type usage)
    assert "test.Point" in mp_deps, f"make_point should depend on Point, got {mp_deps}"
    print("  ✓ make_point depends on Point")

    print("\n  ✓ Dependency resolution works")


# ---------------------------------------------------------------------------
# Phase 3: graph generation (CFG, PDG, HPG) via GraphService
# ---------------------------------------------------------------------------
def phase3_graphs():
    print("\n" + "=" * 60)
    print("[PHASE 3] Graph generation (CFG / PDG / HPG) for C code")
    print("=" * 60)
    from backend.graph_ir import get_graph_service

    base = Path(__file__).parent / ".tmp_c_repo"
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)

    c_path = base / "math_utils.c"
    c_path.write_text(r"""
#include <stdio.h>

/**
 * Compute the greatest common divisor using Euclid's algorithm.
 */
int gcd(int a, int b) {
    while (b != 0) {
        int temp = b;
        b = a % b;
        a = temp;
    }
    return a;
}

/**
 * Check if a number is prime.
 */
int is_prime(int n) {
    if (n <= 1) {
        return 0;
    }
    for (int i = 2; i * i <= n; i++) {
        if (n % i == 0) {
            return 0;
        }
    }
    return 1;
}

/**
 * Fibonacci using iteration.
 */
int fibonacci(int n) {
    if (n <= 0) return 0;
    if (n == 1) return 1;
    int a = 0;
    int b = 1;
    int result = 0;
    for (int i = 2; i <= n; i++) {
        result = a + b;
        a = b;
        b = result;
    }
    return result;
}
""".lstrip(), encoding="utf-8")

    service = get_graph_service()
    repo_path = str(base)

    print("\n  Parsing navigator components...")
    comps = service.parse_repository_components(repo_path, force=True)

    print(f"  Found {len(comps)} components:")
    for cid, comp in sorted(comps.items()):
        ctype = getattr(comp.type, "value", comp.type)
        print(f"    {ctype:20s}  {cid}  (lines {comp.location.start_line}-{comp.location.end_line})")

    # Find the gcd component
    target_funcs = ["gcd", "is_prime", "fibonacci"]
    for func_name in target_funcs:
        func_ids = [cid for cid, c in comps.items() if c.name == func_name]
        if not func_ids:
            print(f"\n  ✗ Could not find {func_name}() component")
            return False

        comp_id = func_ids[0]
        print(f"\n  --- Generating graphs for {func_name}() [{comp_id}] ---")

        cfg = service.get_cfg(repo_path, comp_id)
        pdg = service.get_pdg(repo_path, comp_id)
        hpg = service.get_hpg(repo_path, comp_id)

        for label, resp in [("CFG", cfg), ("PDG", pdg), ("HPG", hpg)]:
            if not resp.success or not resp.data:
                print(f"  ✗ {label} failed: {resp.message}")
                return False
            print(f"  {label}: nodes={len(resp.data.nodes):3d}  edges={len(resp.data.edges):3d}")

        # Validate no dangling edges in HPG
        node_ids = {n.id for n in hpg.data.nodes}
        dangling = [
            e for e in hpg.data.edges
            if e.source not in node_ids or e.target not in node_ids
        ]
        if dangling:
            print(f"  ✗ Dangling edges in HPG for {func_name}:")
            for e in dangling[:5]:
                print(f"      {e.id}: {e.source} -> {e.target} ({e.type})")
            return False
        print(f"  ✓ No dangling edges in HPG")

    # Also test DAG
    print("\n  --- Generating DAG (dependency graph) ---")
    dag = service.get_dag(repo_path)
    if dag.success and dag.data:
        print(f"  DAG: nodes={len(dag.data.nodes):3d}  edges={len(dag.data.edges):3d}")
        print(f"  ✓ DAG generated successfully")
    else:
        print(f"  ✗ DAG failed: {dag.message}")
        return False

    # Cleanup
    shutil.rmtree(base, ignore_errors=True)

    print("\n  ✓ All graphs generated successfully for C code")
    return True


# ---------------------------------------------------------------------------
# Phase 4: multilang IR adapter
# ---------------------------------------------------------------------------
def phase4_multilang_ir():
    print("\n" + "=" * 60)
    print("[PHASE 4] Multi-language IR adapter for C")
    print("=" * 60)
    from backend.graph_ir.multilang_ir_adapter import (
        function_ir_from_code_component,
        extract_statements_from_snippet,
    )

    snippet = """\
int factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}"""

    stmts = extract_statements_from_snippet(snippet, language="c", start_line=1)
    print(f"  Statements extracted: {len(stmts)}")
    for s in stmts:
        print(f"    L{s.line:3d} {s.type.value:15s}  {s.code[:60]}")

    assert len(stmts) >= 3, f"Expected at least 3 statements, got {len(stmts)}"
    print("\n  ✓ C statement extraction works")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 60)
    print("  C Language Support — Smoke Test")
    print("=" * 60)

    try:
        # Phase 0: tree-sitter
        if not phase0_treesitter():
            return 1

        # Phase 1: adapter + extraction
        components, tree, source = phase1_adapter()

        # Phase 2: dependencies
        phase2_dependencies(components, tree, source)

        # Phase 3: full graph generation
        if not phase3_graphs():
            return 2

        # Phase 4: multilang IR
        phase4_multilang_ir()

        print("\n" + "=" * 60)
        print("  ✅ ALL PHASES PASSED — C language support is working!")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n  ✗ EXCEPTION: {e}")
        traceback.print_exc()
        return 99


if __name__ == "__main__":
    raise SystemExit(main())
