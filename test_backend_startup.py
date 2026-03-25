#!/usr/bin/env python
"""Test backend startup."""

import sys
import traceback

try:
    print("Loading backend.app...")
    from backend.app import app
    print("✓ Backend app loaded successfully")
    
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    analysis_routes = [r for r in routes if "analysis" in r]
    print(f"✓ Total routes: {len(routes)}")
    print(f"✓ Analysis routes: {len(analysis_routes)}")
    for route in sorted(analysis_routes):
        print(f"  - {route}")
    
    print("\n✓ Ready to start uvicorn!")
    print(f"\nRun: python -m uvicorn backend.app:app --reload")
    
except Exception as e:
    print(f"✗ Error loading backend: {e}")
    traceback.print_exc()
    sys.exit(1)
