"""
Comparative Analysis of CodeSearchNet Java Validation Results

This script analyzes existing Java navigator results JSON and produces:
  - Overall success metrics
  - Component extraction statistics 
  - Failure breakdown by error type
  - Field-level coverage analysis
  - Recommendations for improvement
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any

def load_results(results_file: str) -> Dict[str, Any]:
    """Load validation results from JSON file."""
    path = Path(results_file)
    if not path.exists():
        print(f"❌ Results file not found: {results_file}")
        sys.exit(1)
    
    with open(path, 'r') as f:
        return json.load(f)

def analyze_results(results: Dict[str, Any]):
    """Perform comprehensive comparative analysis."""
    
    print("\n" + "=" * 80)
    print("COMPARATIVE ANALYSIS: Java Navigator on CodeSearchNet")
    print("=" * 80)
    
    # Handle both old and new formats
    validation_results = results.get('results', [])
    
    # If metrics not present, calculate from results
    metrics = results.get('metrics', {})
    if not metrics and validation_results:
        successful = sum(1 for r in validation_results if r.get('status') == 'success')
        failed = len(validation_results) - successful
        metrics = {
            'successful': successful,
            'failed': failed,
            'error_summary': results.get('error_summary', {})
        }
    
    successful = metrics.get('successful', 0)
    failed = metrics.get('failed', 0)
    total = successful + failed if successful or failed else len(validation_results)
    
    # Check if we have data
    if total == 0:
        print("\n❌ No results found in file!")
        print(f"\nFile structure: {list(results.keys())}")
        print(f"Results array has {len(validation_results)} items")
        if validation_results:
            print(f"\nFirst result structure: {list(validation_results[0].keys())}")
        return
    
    print(f"\n📊 OVERALL METRICS")
    print(f"  Total samples tested: {total}")
    if total > 0:
        print(f"  Successful extractions: {successful} ({successful/total*100:.1f}%)")
        print(f"  Failed extractions: {failed} ({failed/total*100:.1f}%)")
    
    # Component extraction stats
    extraction_stats = metrics.get('extraction_stats', {})
    print(f"\n🔍 COMPONENT EXTRACTION STATISTICS")
    if extraction_stats:
        total_components = sum(extraction_stats.values())
        print(f"  Total components: {total_components}")
        for comp_type, count in sorted(extraction_stats.items()):
            pct = count / total_components * 100 if total_components > 0 else 0
            print(f"    {comp_type}: {count} ({pct:.1f}%)")
    else:
        print("  (No extraction data)")
    
    # Error summary
    error_summary = metrics.get('error_summary', results.get('error_summary', {}))
    if error_summary:
        print(f"\n⚠️  ERROR BREAKDOWN (Top Issues)")
        sorted_errors = sorted(error_summary.items(), key=lambda x: x[1], reverse=True)
        for error_type, count in sorted_errors[:10]:
            pct = count / total * 100 if total > 0 else 0
            print(f"  {error_type}: {count} ({pct:.1f}%)")
    
    # Analyze individual results (already extracted earlier)
    
    by_status = defaultdict(list)
    component_counts = []
    field_coverage = defaultdict(list)
    
    for result in validation_results:
        status = result.get('status', 'unknown')
        by_status[status].append(result)
        
        if status == 'success':
            component_counts.append(result.get('component_count', 0))
            
            # Analyze field coverage in components
            for comp_id, comp_data in result.get('components', {}).items():
                if isinstance(comp_data, dict):
                    for field in comp_data.keys():
                        if comp_data[field]:  # Non-empty
                            field_coverage[field].append(1)
                        else:
                            field_coverage[field].append(0)
    
    # Component count statistics
    if component_counts:
        avg_components = sum(component_counts) / len(component_counts)
        max_components = max(component_counts)
        min_components = min(component_counts)
        
        print(f"\n📈 COMPONENT EXTRACTION DEPTH")
        print(f"  Average components per file: {avg_components:.1f}")
        print(f"  Max components in single file: {max_components}")
        print(f"  Min components in single file: {min_components}")
        
        # Distribution
        dist = defaultdict(int)
        for count in component_counts:
            if count == 0:
                dist['0 components'] += 1
            elif count == 1:
                dist['1 component'] += 1
            elif count <= 3:
                dist['2-3 components'] += 1
            elif count <= 5:
                dist['4-5 components'] += 1
            else:
                dist['6+ components'] += 1
        
        print(f"\n  Distribution:")
        for bucket, cnt in sorted(dist.items()):
            pct = cnt / len(component_counts) * 100
            print(f"    {bucket}: {cnt} ({pct:.1f}%)")
    
    # Field coverage
    if field_coverage:
        print(f"\n🎯 FIELD-LEVEL COVERAGE (Success cases only)")
        for field, values in sorted(field_coverage.items()):
            coverage = sum(values) / len(values) * 100
            print(f"  {field}: {coverage:.1f}% populated")
    
    # Sample analysis
    print(f"\n📋 SAMPLE BREAKDOWN")
    for status, results_list in sorted(by_status.items()):
        print(f"  {status.upper()}: {len(results_list)}")
        if status == 'success' and results_list:
            indices = [r.get('sample_index') for r in results_list[:5]]
            print(f"    → Sample indexes: {indices}")
    
    # Generate recommendations
    print(f"\n💡 RECOMMENDATIONS")
    
    if total > 0 and failed / total > 0.5:
        print(f"  🔴 CRITICAL: {failed/total*100:.0f}% failure rate")
        print(f"     - Review error types above")
        if error_summary.get('Not valid Java', 0) > failed * 0.7:
            print(f"     - Most failures: 'Not valid Java' parse errors")
            print(f"     - Issue: Dataset may contain non-Java code or invalid syntax")
            print(f"     - Solution: Improve non-Java detection or filter dataset")
        else:
            print(f"     - Diverse failure types suggest adapter issues")
            print(f"     - Solution: Check adapter for missing component types")
    
    if component_counts and max(component_counts) < 3:
        print(f"  🟡 WARNING: Low component extraction ({max(component_counts)} max)")
        print(f"     - Adapter may be missing nested methods/classes")
        print(f"     - Check extractor for anonymous classes and lambda expressions")
        print(f"     - Verify recursive AST traversal is working")
    
    if field_coverage:
        missing_fields = [f for f, vals in field_coverage.items() if sum(vals) / len(vals) < 0.5]
        if missing_fields:
            print(f"  🟡 WARNING: Poor field coverage: {missing_fields}")
            print(f"     - These fields rarely populated")
            print(f"     - Low value for documentation generation")
    
    if successful == 0 and total > 0:
        print(f"  🔴 CRITICAL: Zero successful extractions")
        print(f"     - Java adapter may not be working properly")
        print(f"     - Check if JavaAdapter is correctly parsing AST")
        print(f"     - Verify CodeSearchNet dataset includes Java samples")
    
    print(f"\n{'=' * 80}\n")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python analyze_java_validation_results.py <results_file.json>")
        print("\nExample:")
        print("  python analyze_java_validation_results.py data/validation/codesearchnet/java_navigator_results_100_samples.json")
        print("\nTo generate results first:")
        print("  python test_navigator_java_codesearchnet.py 100")
        print("\nAvailable results:")
        from pathlib import Path
        results_dir = Path("data/validation/codesearchnet")
        if results_dir.exists():
            json_files = list(results_dir.glob("*.json"))
            if json_files:
                for f in json_files:
                    print(f"  - {f}")
            else:
                print("  (No results files found yet)")
        else:
            print("  (Results directory not found)")
        sys.exit(1)
    
    results_file = sys.argv[1]
    print(f"Loading results from: {results_file}")
    
    results = load_results(results_file)
    analyze_results(results)
