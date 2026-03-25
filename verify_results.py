#!/usr/bin/env python3
"""Verify repo-specific component loading results"""

import json
from pathlib import Path

results_file = Path('data/validation/testrepo/unified_evaluation_results.json')
with open(results_file) as f:
    results = json.load(f)

print("=" * 60)
print("EVALUATION RESULTS WITH REPO-SPECIFIC COMPONENT LOADING")
print("=" * 60)
print()
print("Overall Score:", f"{results['overall_score']:.1%}")
print("  Completeness:  ", f"{results['completeness_score']:.1%}")
print("  Helpfulness:   ", f"{results['helpfulness_score']:.2f}/5.0")
print("  Truthfulness:  ", f"{results['truthfulness_score']:.1%}")
print()
print("Truthfulness Details:")
if 'truthfulness_results' in results:
    truth = results['truthfulness_results']
    print(f"  Summary accuracy:              {truth.get('summary', {}).get('overall_accuracy', 'N/A')}")
    print(f"  Components with mentions:      {truth.get('summary', {}).get('total_components', 'N/A')}")
    print(f"  Accurate components:           {truth.get('summary', {}).get('accurate_components', 'N/A')}")
    print(f"  Components with hallucination: {truth.get('summary', {}).get('components_with_issues', 'N/A')}")
