#!/usr/bin/env python3
"""Test repo-specific truthfulness evaluation"""

from backend.unified_evaluator import UnifiedEvaluator

print("[TEST] Repo-Specific Component Loading")
print("=" * 50)

try:
    evaluator = UnifiedEvaluator('testrepo')
    print("[INFO] Initialized evaluator for testrepo")
    
    results = evaluator.evaluate_all()
    print("[SUCCESS] Evaluation completed")
    
    print("\nResults Summary:")
    print(f"  Overall Score: {results['overall']:.1%}")
    print(f"  Completeness: {results['completeness_score']:.1%}")
    print(f"  Helpfulness: {results['helpfulness_score']:.2f}/5")
    print(f"  Truthfulness: {results['truthfulness_score']:.1%}")
    
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
