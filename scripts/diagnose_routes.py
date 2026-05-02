#!/usr/bin/env python
"""Detailed diagnosis of why analysis routes might not be loading."""

import sys
import traceback

print("=" * 60)
print("BACKEND DIAGNOSTICS")
print("=" * 60)

try:
    print("\n1. Importing analysis_routes module...")
    from backend.routes import analysis_routes
    print("   [OK] analysis_routes module imported")
    print("   [OK] router object exists: " + str(hasattr(analysis_routes, 'router')))
    
    if hasattr(analysis_routes, 'router'):
        router = analysis_routes.router
        print("   [OK] Router prefix: " + str(router.prefix))
        print("   [OK] Router tags: " + str(router.tags))
        routes = [r.path for r in router.routes if hasattr(r, "path")]
        print("   [OK] Router has " + str(len(routes)) + " routes:")
        for route in sorted(routes):
            print("        - " + route)
    
    print("\n2. Importing FastAPI app...")
    from backend.app import app
    print("   [OK] FastAPI app imported")
    
    print("\n3. Checking registered routers in app.routes...")
    all_routes = [r.path for r in app.routes if hasattr(r, "path")]
    analysis_routes_in_app = [r for r in all_routes if "analysis" in r]
    print("   [OK] Total routes in app: " + str(len(all_routes)))
    print("   [OK] Analysis routes in app: " + str(len(analysis_routes_in_app)))
    
    if not analysis_routes_in_app:
        print("   [ERROR] WARNING: No analysis routes found in app!")
        print("   [ERROR] -> Router is not registered properly")
        print("\n   Checking route list (first 10):")
        for idx, r in enumerate(all_routes[:10]):
            print("        Route: " + str(r))
    else:
        print("   [OK] Analysis routes ARE in the app:")
        for route in sorted(analysis_routes_in_app):
            print("        - " + route)
    
    print("\n" + "=" * 60)
    print("DIAGNOSIS COMPLETE")
    print("=" * 60)
    
except Exception as e:
    print("\n[ERROR] Exception: " + str(e))
    print("\nFull traceback:")
    traceback.print_exc()
    sys.exit(1)
