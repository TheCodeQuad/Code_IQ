"""
Comparative Analysis of CodeSearchNet Java Validation Results

This script analyzes existing Java navigator results JSON and produces:
  - Overall success metrics
  - Component extraction statistics 
  - Failure breakdown by error type
  - Type-aware field-level coverage analysis
  - Actionable recommendations (filtered by component type semantics)
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any

# ── Which fields are expected per component type ──────────────────────────────
# Used to avoid false-positive "poor coverage" warnings.
# A field is only evaluated against types where it semantically applies.
EXPECTED_FIELDS = {
    'method':      {'parameters', 'calls', 'return_type', 'signature', 'existing_docstring',
                    'decorators', 'complexity', 'is_async', 'source_code'},
    'constructor': {'parameters', 'calls', 'signature', 'existing_docstring',
                    'decorators', 'complexity', 'source_code'},
    'class':       {'parent_classes', 'decorators', 'existing_docstring', 'signature',
                    'methods', 'attributes', 'source_code'},
    'field':       {'return_type', 'signature', 'existing_docstring', 'decorators',
                    'source_code'},
    'static_field': {'return_type', 'signature', 'existing_docstring', 'decorators',
                     'source_code'},
}

# Fields that only apply when the codebase uses a web framework
HTTP_FIELDS = {'http_method', 'http_path', 'framework', 'path_parameters',
               'query_parameters', 'request_body', 'response_model', 'status_codes', 'tags'}

# Fields that are language-specific and do not apply to Java
JAVA_IRRELEVANT_FIELDS = {'is_async', 'is_generator'}


def load_results(results_file: str) -> Dict[str, Any]:
    """Load validation results from JSON file."""
    path = Path(results_file)
    if not path.exists():
        print(f"❌ Results file not found: {results_file}")
        sys.exit(1)
    
    with open(path, 'r') as f:
        return json.load(f)


def _coverage(vals: list) -> float:
    """Return percentage of truthy values."""
    return sum(vals) / len(vals) * 100 if vals else 0.0


def analyze_results(results: Dict[str, Any]):
    """Perform comprehensive, type-aware comparative analysis."""
    
    print("\n" + "=" * 80)
    print("COMPARATIVE ANALYSIS: Java Navigator on CodeSearchNet")
    print("=" * 80)
    
    # ── Resolve metrics ───────────────────────────────────────────────────────
    validation_results = results.get('results', [])
    
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
    
    if total == 0:
        print("\n❌ No results found in file!")
        print(f"\nFile structure: {list(results.keys())}")
        print(f"Results array has {len(validation_results)} items")
        if validation_results:
            print(f"\nFirst result structure: {list(validation_results[0].keys())}")
        return
    
    # ── Overall metrics ───────────────────────────────────────────────────────
    print(f"\n📊 OVERALL METRICS")
    print(f"  Total samples tested: {total}")
    if total > 0:
        print(f"  Successful extractions: {successful} ({successful/total*100:.1f}%)")
        print(f"  Failed extractions: {failed} ({failed/total*100:.1f}%)")
    
    # ── Component extraction stats ────────────────────────────────────────────
    extraction_stats = metrics.get('extraction_stats', {})
    total_components = sum(extraction_stats.values()) if extraction_stats else 0
    print(f"\n🔍 COMPONENT EXTRACTION STATISTICS")
    if extraction_stats:
        print(f"  Total components: {total_components}")
        for comp_type, count in sorted(extraction_stats.items()):
            pct = count / total_components * 100 if total_components > 0 else 0
            print(f"    {comp_type}: {count} ({pct:.1f}%)")
    else:
        print("  (No extraction data)")
    
    # ── Error summary ─────────────────────────────────────────────────────────
    error_summary = metrics.get('error_summary', results.get('error_summary', {}))
    if error_summary:
        print(f"\n⚠️  ERROR BREAKDOWN (Top Issues)")
        sorted_errors = sorted(error_summary.items(), key=lambda x: x[1], reverse=True)
        for error_type, count in sorted_errors[:10]:
            pct = count / total * 100 if total > 0 else 0
            print(f"  {error_type}: {count} ({pct:.1f}%)")
    
    # ── Walk results: per-type field coverage ─────────────────────────────────
    by_status = defaultdict(list)
    component_counts = []
    field_coverage_all = defaultdict(list)          # all types combined
    field_by_type = defaultdict(lambda: defaultdict(list))  # per-type
    
    for result in validation_results:
        status = result.get('status', 'unknown')
        by_status[status].append(result)
        
        if status == 'success':
            component_counts.append(result.get('component_count', 0))
            
            for comp_id, comp_data in result.get('components', {}).items():
                if not isinstance(comp_data, dict):
                    continue
                comp_type = comp_data.get('type', 'unknown')
                for field, value in comp_data.items():
                    has_value = bool(value) if not isinstance(value, list) else len(value) > 0
                    populated = 1 if has_value else 0
                    field_coverage_all[field].append(populated)
                    field_by_type[comp_type][field].append(populated)
    
    # ── Component count statistics ────────────────────────────────────────────
    if component_counts:
        avg_components = sum(component_counts) / len(component_counts)
        max_components = max(component_counts)
        min_components = min(component_counts)
        
        print(f"\n📈 COMPONENT EXTRACTION DEPTH")
        print(f"  Average components per file: {avg_components:.1f}")
        print(f"  Max components in single file: {max_components}")
        print(f"  Min components in single file: {min_components}")
        
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
    
    # ── Aggregate field coverage (kept for backwards compat) ──────────────────
    if field_coverage_all:
        print(f"\n🎯 FIELD-LEVEL COVERAGE (all types combined)")
        for field, values in sorted(field_coverage_all.items()):
            coverage = _coverage(values)
            print(f"  {field}: {coverage:.1f}% populated")
    
    # ── NEW: Per-type field coverage ──────────────────────────────────────────
    if field_by_type:
        print(f"\n🎯 FIELD-LEVEL COVERAGE BY COMPONENT TYPE")
        important_fields = ['parameters', 'calls', 'return_type', 'decorators',
                            'existing_docstring', 'parent_classes', 'signature',
                            'complexity', 'source_code']
        for comp_type in ['method', 'class', 'field', 'constructor', 'static_field']:
            type_data = field_by_type.get(comp_type)
            if not type_data:
                continue
            n = len(type_data.get('id', type_data.get('name', [])))
            print(f"\n  {comp_type.upper()} ({n} components):")
            for field in important_fields:
                if field in type_data:
                    cov = _coverage(type_data[field])
                    expected = field in EXPECTED_FIELDS.get(comp_type, set())
                    if not expected:
                        tag = "─"    # not applicable for this type
                    elif cov >= 80:
                        tag = "✅"
                    elif cov >= 40:
                        tag = "⚠️"
                    else:
                        tag = "❌"
                    suffix = " (N/A)" if not expected else ""
                    print(f"    {tag} {field}: {cov:.1f}%{suffix}")
    
    # ── Sample analysis ───────────────────────────────────────────────────────
    print(f"\n📋 SAMPLE BREAKDOWN")
    for status, results_list in sorted(by_status.items()):
        print(f"  {status.upper()}: {len(results_list)}")
        if status == 'success' and results_list:
            indices = [r.get('sample_index') for r in results_list[:5]]
            print(f"    → Sample indexes: {indices}")
    
    # ── Smart recommendations ─────────────────────────────────────────────────
    print(f"\n💡 RECOMMENDATIONS")
    has_recommendation = False
    
    # 1. High failure rate
    if total > 0 and failed / total > 0.5:
        has_recommendation = True
        print(f"  🔴 CRITICAL: {failed/total*100:.0f}% failure rate")
        print(f"     - Review error types above")
        if error_summary.get('Not valid Java', 0) > failed * 0.7:
            print(f"     - Most failures: 'Not valid Java' parse errors")
            print(f"     - Issue: Dataset may contain non-Java code or invalid syntax")
            print(f"     - Solution: Improve non-Java detection or filter dataset")
        else:
            print(f"     - Diverse failure types suggest adapter issues")
            print(f"     - Solution: Check adapter for missing component types")
    
    # 2. Low component extraction
    if component_counts and max(component_counts) < 3:
        has_recommendation = True
        print(f"  🟡 WARNING: Low component extraction ({max(component_counts)} max)")
        print(f"     - Adapter may be missing nested methods/classes")
        print(f"     - Check extractor for anonymous classes and lambda expressions")
        print(f"     - Verify recursive AST traversal is working")
    
    # 3. Type-aware field analysis — only flag fields that SHOULD exist for a type
    real_issues = []
    for comp_type, type_data in field_by_type.items():
        expected = EXPECTED_FIELDS.get(comp_type, set())
        for field in expected:
            if field in type_data:
                cov = _coverage(type_data[field])
                if cov < 50:
                    # skip Java-irrelevant fields
                    if field in JAVA_IRRELEVANT_FIELDS:
                        continue
                    n = len(type_data.get('id', type_data.get('name', [])))
                    real_issues.append((comp_type, field, cov, n))
    
    if real_issues:
        has_recommendation = True
        print(f"  🟡 TYPE-AWARE FIELD COVERAGE ISSUES:")
        for comp_type, field, cov, n in sorted(real_issues, key=lambda x: x[2]):
            print(f"     - {comp_type}.{field}: {cov:.1f}% (of {n} {comp_type}s)")
        
        # Specific actionable advice
        method_params = next((cov for ct, f, cov, _ in real_issues if ct == 'method' and f == 'parameters'), None)
        if method_params is not None and method_params < 60:
            print(f"     → Methods: {100 - method_params:.0f}% missing parameters")
            print(f"       Check: varargs (...), generic types, complex signatures")
        
        class_parents = next((cov for ct, f, cov, _ in real_issues if ct == 'class' and f == 'parent_classes'), None)
        if class_parents is not None and class_parents < 50:
            print(f"     → Classes: {100 - class_parents:.0f}% missing parent_classes")
            print(f"       Check: extends/implements extraction in extractor")
        
        docstring_issues = [(ct, cov) for ct, f, cov, _ in real_issues if f == 'existing_docstring']
        if docstring_issues:
            types_str = ', '.join(f"{ct} ({cov:.0f}%)" for ct, cov in docstring_issues)
            print(f"     → JavaDoc extraction low for: {types_str}")
            print(f"       Check: get_javadoc() function in extractor.py")
    
    # 4. HTTP fields — only warn if web patterns detected
    if field_by_type:
        has_http_content = any(
            _coverage(type_data.get('http_method', [0])) > 0
            for type_data in field_by_type.values()
        )
        if not has_http_content:
            print(f"\n  ℹ️  NOTE: HTTP/API fields (http_method, framework, etc.) are all 0%")
            print(f"     This is EXPECTED — dataset contains general Java code, not REST APIs")
            print(f"     These fields activate for Spring/JAX-RS annotated code")
    
    # 5. Java-irrelevant fields
    java_na = [f for f in JAVA_IRRELEVANT_FIELDS if f in field_coverage_all]
    if java_na:
        print(f"\n  ℹ️  NOTE: {java_na} are 0% — Java does not have these features")
    
    # 6. Zero successful extractions
    if successful == 0 and total > 0:
        has_recommendation = True
        print(f"  🔴 CRITICAL: Zero successful extractions")
        print(f"     - Java adapter may not be working properly")
        print(f"     - Check if JavaAdapter is correctly parsing AST")
        print(f"     - Verify CodeSearchNet dataset includes Java samples")
    
    if not has_recommendation:
        print(f"  ✅ No critical issues found")
    
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
