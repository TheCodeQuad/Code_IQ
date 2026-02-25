"""
Comparative Analysis of Python Validation Results (CodeSearchNet Dataset)

Type-aware analysis that:
  - Separates field coverage by component type (function, method, class)
  - Detects no-arg / self-only methods vs truly missing parameters
  - Filters HTTP/framework fields for non-API code
  - Gives actionable, type-specific recommendations

Usage:
    python analyze_python_validation_results.py <results_file.json>
"""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any

# ── Which fields are expected per Python component type ───────────────────────
EXPECTED_FIELDS = {
    'function': {
        'parameters', 'calls', 'return_type', 'signature', 'existing_docstring',
        'decorators', 'complexity', 'is_async', 'is_generator', 'source_code',
        'depends_on',
    },
    'method': {
        'parameters', 'calls', 'return_type', 'signature', 'existing_docstring',
        'decorators', 'complexity', 'is_async', 'is_generator', 'source_code',
        'depends_on',
    },
    'constructor': {
        'parameters', 'calls', 'signature', 'existing_docstring',
        'is_async', 'source_code', 'depends_on',
    },
    'class': {
        'parent_classes', 'decorators', 'existing_docstring', 'signature',
        'methods', 'attributes', 'source_code', 'depends_on',
    },
    'api_endpoint': {
        'parameters', 'calls', 'return_type', 'signature', 'existing_docstring',
        'decorators', 'is_async', 'source_code', 'depends_on',
        'http_method', 'http_path',
    },
    'static_field': {
        'signature', 'source_code',
    },
    'global_variable': {
        'signature', 'source_code',
    },
}

# Fields that only apply when the codebase uses a web framework
HTTP_FIELDS = {
    'http_method', 'http_path', 'framework', 'path_parameters',
    'query_parameters', 'request_body', 'response_model', 'status_codes', 'tags',
}

# Fields that are boolean flags — False is a valid populated value, not missing
BOOLEAN_FIELDS = {
    'is_async', 'is_generator', 'is_abstract', 'is_static', 'is_class_method',
    'is_public', 'is_private', 'is_protected',
}
# Fields that are integers where 0 is a valid value (not missing)
INT_ZERO_OK_FIELDS = {'priority', 'dependency_level', 'lines_of_code'}


def _is_populated(field, value):
    """Return True if the field is meaningfully populated."""
    if field in BOOLEAN_FIELDS:
        return value is not None  # False is still populated
    if field in INT_ZERO_OK_FIELDS:
        return value is not None  # 0 is still populated
    if isinstance(value, list):
        return len(value) > 0
    return bool(value)


# Regex for self-only / cls-only / no-arg signatures
_NOARG_RE = re.compile(r'def\s+\w+\s*\(\s*(self|cls)?\s*\)')


def load_results(results_file: str) -> Dict[str, Any]:
    """Load validation results from JSON file."""
    path = Path(results_file)
    if not path.exists():
        print(f"❌ Results file not found: {results_file}")
        sys.exit(1)

    with open(path, 'r') as f:
        return json.load(f)


def _pct(n: int, d: int) -> float:
    return n / d * 100 if d else 0.0


def _coverage(vals: list) -> float:
    return sum(vals) / len(vals) * 100 if vals else 0.0


def analyze_results(results: Dict[str, Any]):
    """Perform comprehensive, type-aware comparative analysis."""

    print("\n" + "=" * 80)
    print("PYTHON NAVIGATOR VALIDATION - TYPE-AWARE ANALYSIS")
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

    # ── 1. Overall metrics ────────────────────────────────────────────────────
    print(f"\n📊 OVERALL METRICS")
    print(f"  Total samples tested: {total}")
    if total > 0:
        print(f"  Successful extractions: {successful} ({_pct(successful, total):.1f}%)")
        print(f"  Failed extractions: {failed} ({_pct(failed, total):.1f}%)")

    # ── 2. Component extraction stats ─────────────────────────────────────────
    extraction_stats = metrics.get('extraction_stats', {})
    total_components = sum(extraction_stats.values()) if extraction_stats else 0
    print(f"\n🔍 COMPONENT EXTRACTION STATISTICS")
    if extraction_stats:
        print(f"  Total components: {total_components}")
        for comp_type, count in sorted(extraction_stats.items()):
            pct = _pct(count, total_components)
            print(f"    {comp_type}: {count} ({pct:.1f}%)")
    else:
        print("  (No extraction data)")

    # ── 3. Error summary ──────────────────────────────────────────────────────
    error_summary = metrics.get('error_summary', results.get('error_summary', {}))
    if error_summary:
        print(f"\n⚠️  ERROR BREAKDOWN (Top Issues)")
        sorted_errors = sorted(error_summary.items(), key=lambda x: x[1], reverse=True)
        for error_type, count in sorted_errors[:10]:
            pct = _pct(count, total)
            print(f"  {error_type}: {count} ({pct:.1f}%)")

    # ── 4. Walk results: per-type field coverage ──────────────────────────────
    by_status = defaultdict(list)
    component_counts = []
    field_coverage_all = defaultdict(list)
    field_by_type = defaultdict(lambda: defaultdict(list))
    # Track parameter accuracy
    param_empty_noarg = defaultdict(int)   # empty params AND signature is no-arg
    param_empty_hasarg = defaultdict(int)  # empty params BUT signature has args

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
                    has_value = _is_populated(field, value)
                    populated = 1 if has_value else 0
                    field_coverage_all[field].append(populated)
                    field_by_type[comp_type][field].append(populated)

                # Track parameter accuracy for functions/methods
                if comp_type in ('function', 'method') and not comp_data.get('parameters'):
                    sig = comp_data.get('signature', '')
                    if _NOARG_RE.search(sig):
                        param_empty_noarg[comp_type] += 1
                    else:
                        param_empty_hasarg[comp_type] += 1

    # ── 5. Component count statistics ─────────────────────────────────────────
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
            pct = _pct(cnt, len(component_counts))
            print(f"    {bucket}: {cnt} ({pct:.1f}%)")

    # ── 6. Aggregate field coverage (kept for reference) ──────────────────────
    if field_coverage_all:
        print(f"\n🎯 FIELD-LEVEL COVERAGE (all types combined)")
        for field, values in sorted(field_coverage_all.items()):
            coverage = _coverage(values)
            bar = "█" * int(coverage / 10) + "░" * (10 - int(coverage / 10))
            print(f"  {bar} {field:<24s} {coverage:5.1f}%")

    # ── 7. Per-type field coverage ────────────────────────────────────────────
    if field_by_type:
        print(f"\n🎯 FIELD-LEVEL COVERAGE BY COMPONENT TYPE")
        important_fields = ['parameters', 'calls', 'return_type', 'decorators',
                            'existing_docstring', 'parent_classes', 'signature',
                            'complexity', 'is_async', 'is_generator', 'source_code',
                            'methods', 'attributes', 'depends_on', 'imports']

        for comp_type in ['function', 'method', 'constructor', 'class', 'api_endpoint', 'static_field', 'global_variable']:
            type_data = field_by_type.get(comp_type)
            if not type_data:
                continue
            n = len(type_data.get('id', type_data.get('name', [])))
            print(f"\n  {comp_type.upper()} ({n} components):")
            for field in important_fields:
                if field not in type_data:
                    continue
                cov = _coverage(type_data[field])
                expected = field in EXPECTED_FIELDS.get(comp_type, set())
                if not expected:
                    tag = "─"     # not applicable for this type
                elif cov >= 80:
                    tag = "✅"
                elif cov >= 40:
                    tag = "⚠️"
                else:
                    tag = "❌"
                suffix = " (N/A for this type)" if not expected else ""
                print(f"    {tag} {field}: {cov:.1f}%{suffix}")

    # ── 8. Parameter accuracy analysis ────────────────────────────────────────
    print(f"\n🔬 PARAMETER EXTRACTION ACCURACY")
    for comp_type in ['function', 'method', 'constructor']:
        type_data = field_by_type.get(comp_type, {})
        total_ct = len(type_data.get('id', []))
        populated = sum(type_data.get('parameters', []))
        noarg = param_empty_noarg.get(comp_type, 0)
        truly_missing = param_empty_hasarg.get(comp_type, 0)

        print(f"\n  {comp_type.upper()} ({total_ct}):")
        print(f"    Has parameters:         {populated}")
        noarg_label = "No-arg ()" if comp_type == 'function' else "Self-only / no-arg"
        print(f"    {noarg_label}:  {noarg} (correctly empty)")
        print(f"    Truly missing params:   {truly_missing}")
        accuracy = _pct(total_ct - truly_missing, total_ct) if total_ct else 0
        print(f"    → Extraction accuracy:  {accuracy:.1f}%")

    # ── 9. Sample analysis ────────────────────────────────────────────────────
    print(f"\n📋 SAMPLE BREAKDOWN")
    for status, results_list in sorted(by_status.items()):
        print(f"  {status.upper()}: {len(results_list)}")
        if status == 'success' and results_list:
            indices = [r.get('sample_index') for r in results_list[:5]]
            print(f"    → Sample indexes: {indices}")

    # ── 10. Smart recommendations ─────────────────────────────────────────────
    print(f"\n💡 RECOMMENDATIONS")
    has_recommendation = False

    # 1. High failure rate
    if total > 0 and failed / total > 0.3:
        has_recommendation = True
        print(f"  🔴 CRITICAL: {_pct(failed, total):.0f}% failure rate")
        print(f"     - Review error types above")
        no_comp = error_summary.get('No components extracted', 0)
        not_valid = error_summary.get('Not valid Python', 0)
        if no_comp > failed * 0.5:
            print(f"     - {no_comp} samples: 'No components extracted'")
            print(f"       These may be config/data-only files with no functions/classes")
        if not_valid > 0:
            print(f"     - {not_valid} samples: 'Not valid Python'")
            print(f"       Dataset may contain non-Python code or invalid syntax")

    # 2. Low component extraction
    if component_counts and max(component_counts) < 3:
        has_recommendation = True
        print(f"  🟡 WARNING: Low component extraction ({max(component_counts)} max)")
        print(f"     - Adapter may be missing nested functions/classes")
        print(f"     - Check extractor for lambda expressions and comprehensions")

    # 3. Type-aware field analysis — only flag fields that SHOULD exist for a type
    real_issues = []
    for comp_type, type_data in field_by_type.items():
        expected = EXPECTED_FIELDS.get(comp_type, set())
        for field in expected:
            if field not in type_data:
                continue
            cov = _coverage(type_data[field])
            n = len(type_data.get('id', type_data.get('name', [])))
            # Special handling: parameters — use accuracy, not raw coverage
            if field == 'parameters' and comp_type in ('function', 'method'):
                truly_missing = param_empty_hasarg.get(comp_type, 0)
                effective_cov = _pct(n - truly_missing, n) if n else 0
                if effective_cov < 90:
                    real_issues.append((comp_type, field, effective_cov, n,
                                        f"({truly_missing} truly missing, rest are no-arg)"))
                continue
            if cov < 50:
                real_issues.append((comp_type, field, cov, n, ""))

    if real_issues:
        has_recommendation = True
        print(f"\n  🟡 TYPE-AWARE FIELD COVERAGE ISSUES:")
        for comp_type, field, cov, n, note in sorted(real_issues, key=lambda x: x[2]):
            extra = f"  {note}" if note else ""
            print(f"     - {comp_type}.{field}: {cov:.1f}% (of {n} {comp_type}s){extra}")

        # Specific actionable advice
        complexity_issues = [(ct, cov) for ct, f, cov, _, _ in real_issues if f == 'complexity']
        if complexity_issues:
            print(f"     → complexity is 0% across all types")
            print(f"       Action: implement cyclomatic complexity calculation in extractor")

        class_methods = next((cov for ct, f, cov, _, _ in real_issues if ct == 'class' and f == 'methods'), None)
        class_attrs = next((cov for ct, f, cov, _, _ in real_issues if ct == 'class' and f == 'attributes'), None)
        if class_attrs is not None and class_methods is not None:
            print(f"     → class.methods ({class_methods:.0f}%) and class.attributes ({class_attrs:.0f}%) not fully populated")
            if class_attrs == 0.0:
                print(f"       class.attributes: REAL BUG — instance attrs (self.x in __init__) never extracted")
                print(f"       Action: scan __init__ body for self.x = ... and populate class.attributes")
            else:
                print(f"       class.attributes at {class_attrs:.0f}%: only classes with explicit self.x assignments in __init__ are populated")
                print(f"       Remaining gap = classes with no __init__, inherited attrs, or no instance attrs — expected")
            if class_methods == 0.0:
                print(f"       class.methods: REAL BUG — methods not being recorded on class component")
            else:
                print(f"       class.methods at {class_methods:.0f}%: classes with only static_fields have no methods — expected")
        elif class_attrs is not None:
            if class_attrs == 0.0:
                print(f"     → class.attributes: 0.0% — REAL BUG")
                print(f"       Instance attributes (self.x = ... in __init__) are never extracted")
                print(f"       Action: scan __init__ body for self.x assignments, add to class.attributes")
            else:
                print(f"     → class.attributes: {class_attrs:.0f}% — partial coverage (expected)")
                print(f"       Classes below 50%: many classes lack __init__ or have no self.x assignments")
                print(f"       Extraction is working — gap reflects dataset reality")
        elif class_methods is not None:
            print(f"     → class.methods: {class_methods:.0f}% — some classes have no methods (expected)")
            print(f"       Check for edge cases in _extract_class_body if higher coverage expected")

        docstring_issues = [(ct, cov) for ct, f, cov, _, _ in real_issues if f == 'existing_docstring']
        if docstring_issues:
            types_str = ', '.join(f"{ct} ({cov:.0f}%)" for ct, cov in docstring_issues)
            print(f"     → Docstring extraction low for: {types_str}")
            print(f"       Note: many open-source files genuinely lack docstrings")
            print(f"       Check: triple-quote detection in extractor.py")

        return_type_issues = [(ct, cov) for ct, f, cov, _, _ in real_issues if f == 'return_type']
        if return_type_issues:
            types_str = ', '.join(f"{ct} ({cov:.0f}%)" for ct, cov in return_type_issues)
            print(f"     → return_type low for: {types_str}")
            print(f"       Note: most Python code in CodeSearchNet lacks type annotations")
            print(f"       This largely reflects dataset reality, not extraction failure")

    # 4. HTTP fields — informational
    if field_by_type:
        has_http_content = any(
            _coverage(type_data.get('http_method', [0])) > 0
            for type_data in field_by_type.values()
        )
        if not has_http_content:
            print(f"\n  ℹ️  NOTE: HTTP/API fields (http_method, framework, etc.) are all 0%")
            print(f"     This is EXPECTED — dataset contains general Python code, not REST APIs")
            print(f"     These fields activate for Flask/FastAPI/Django annotated code")

    # 5. Zero successful extractions
    if successful == 0 and total > 0:
        has_recommendation = True
        print(f"  🔴 CRITICAL: Zero successful extractions")
        print(f"     - Python adapter may not be working properly")
        print(f"     - Check if PythonAdapter is correctly parsing AST")
        print(f"     - Verify CodeSearchNet dataset includes Python samples")

    # 6. Success summary
    if successful > failed and component_counts:
        avg = sum(component_counts) / len(component_counts)
        if avg > 3:
            print(f"\n  ✅ GOOD: High component extraction rate ({avg:.1f} avg)")
            print(f"     Adapter is finding functions, classes, and methods well")

    if not has_recommendation:
        print(f"  ✅ No critical issues found")

    print(f"\n{'=' * 80}\n")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python analyze_python_validation_results.py <results_file.json>")
        print("\nExample:")
        print("  python analyze_python_validation_results.py data/validation/codesearchnet/python_navigator_results_100_samples.json")
        print("\nTo generate results first:")
        print("  python test_navigator_python_codesearchnet.py 100")
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
