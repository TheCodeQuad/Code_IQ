#!/usr/bin/env python3
"""Smoke test: build CFG/PDG/HPG for a non-Python component via Navigator IR.

This creates a temporary mini-repo folder with one JS file, runs Navigator parsing
through GraphService, then requests CFG/PDG/HPG.

Run:
  python test_multilang_graphs_smoke.py

Requires: tree-sitter + tree-sitter-languages installed (already in requirements.txt)
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from backend.graph_ir import get_graph_service


def main() -> int:
    base = Path(__file__).parent / ".tmp_multilang_repo"
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)

    js_path = base / "mod.js"
    js_path.write_text(
        """
function foo(x) {
  let y = x + 1;
  if (y > 10) {
    y = y * 2;
  } else {
    y = y - 2;
  }
  return y;
}
""".lstrip(),
        encoding="utf-8",
    )

    service = get_graph_service()
    repo_path = str(base)

    print("[SMOKE] Parsing navigator components...")
    comps = service.parse_repository_components(repo_path, force=True)
    # Find the foo component
    foo_ids = [cid for cid, c in comps.items() if c.name == "foo"]
    if not foo_ids:
        print("[SMOKE] Could not find foo() component")
        return 2

    comp_id = foo_ids[0]
    print("[SMOKE] Using component:", comp_id)

    cfg = service.get_cfg(repo_path, comp_id)
    pdg = service.get_pdg(repo_path, comp_id)
    hpg = service.get_hpg(repo_path, comp_id)

    for label, resp in ("CFG", cfg), ("PDG", pdg), ("HPG", hpg):
        if not resp.success or not resp.data:
            print(f"[SMOKE] {label} failed: {resp.message}")
            return 3
        print(f"[SMOKE] {label}: nodes={len(resp.data.nodes)} edges={len(resp.data.edges)}")

    # Validate dangling edges
    node_ids = {n.id for n in hpg.data.nodes}  # type: ignore[union-attr]
    dangling = [e for e in hpg.data.edges if e.source not in node_ids or e.target not in node_ids]  # type: ignore[union-attr]
    if dangling:
        print("[SMOKE] Dangling edges in HPG:")
        for e in dangling[:10]:
            print("  -", e.id, e.source, "->", e.target, e.type)
        return 4

    print("[SMOKE] ✓ OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
