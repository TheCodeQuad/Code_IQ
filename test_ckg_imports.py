#!/usr/bin/env python
"""Quick test that CKG builder imports correctly"""
import sys

try:
    from backend.graph_ir.ckg_builder import build_ckg, export_to_json
    from backend.graph_ir.models import RepositoryIR, ModuleIR, FunctionIR
    print("✓ All CKG imports successful")
    print("✓ build_ckg function available")
    print("✓ export_to_json function available")
    sys.exit(0)
except Exception as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)
