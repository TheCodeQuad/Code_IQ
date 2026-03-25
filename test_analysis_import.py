#!/usr/bin/env python
"""Test if analysis_routes can be imported without errors."""

try:
    from backend.routes.analysis_routes import router
    print("✓ analysis_routes imported successfully")
    
    routes = [r.path for r in router.routes if hasattr(r, "path")]
    print(f"✓ Router has {len(routes)} endpoints:")
    for route in sorted(routes):
        print(f"  - {route}")
    
except Exception as e:
    print(f"✗ Failed to import analysis_routes: {e}")
    import traceback
    traceback.print_exc()
