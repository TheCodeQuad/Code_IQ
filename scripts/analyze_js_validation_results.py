"""
JavaScript Navigator Validation - Type-Aware Detailed Analysis

Performs type-aware analysis on JS validation results, detecting:
  - MODULE fallback misclassification of anonymous functions
  - Per-type field coverage (function vs module vs class vs method etc.)
  - True success rate (against full dataset, not just passed results)
  - Actionable recommendations filtered by component type semantics

Usage:
    python analyze_js_validation_results.py [results_json_file]

Example:
    python analyze_js_validation_results.py data/validation/the-stack/js_navigator_results_500_samples.json
    python analyze_js_validation_results.py data/validation/codesearchnet/js_navigator_results_500_samples.json
"""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Optional

# ── Which fields are expected per JS component type ───────────────────────────
EXPECTED_FIELDS = {
    'function': {
        'parameters', 'calls', 'return_type', 'signature', 'existing_docstring',
        'decorators', 'complexity', 'is_async', 'is_generator', 'source_code',
    },
    'class': {
        'parent_classes', 'decorators', 'existing_docstring', 'signature',
        'methods', 'attributes', 'source_code',
    },
    'module': {
        'imports', 'source_code',
    },
    'method': {
        'parameters', 'calls', 'return_type', 'signature', 'existing_docstring',
        'complexity', 'is_async', 'is_generator', 'source_code',
    },
    'constructor': {
        'parameters', 'calls', 'signature', 'existing_docstring',
        'source_code',
    },
    'field': {
        'signature', 'source_code',
    },
    'static_field': {
        'signature', 'source_code',
    },
    'global_variable': {
        'signature', 'source_code', 'existing_docstring',
    },
    'variable': {
        'signature', 'source_code', 'methods',
    },
}

# Fields that only apply to REST/HTTP framework code
HTTP_FIELDS = {
    'http_method', 'http_path', 'framework', 'path_parameters',
    'query_parameters', 'request_body', 'response_model', 'status_codes', 'tags',
}

# Regex to detect anonymous functions (MODULE fallback victims)
_ANON_FUNC_RE = re.compile(r'^\s*function\s*\(')


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


def _is_anonymous_module(comp: dict) -> bool:
    """Detect an anonymous function that was wrapped as MODULE fallback."""
    if comp.get('type') != 'module':
        return False
    src = comp.get('source_code', '')
    return bool(_ANON_FUNC_RE.match(src))


def analyze_results(data: Dict[str, Any]):
    """Perform comprehensive, type-aware analysis."""

    print("\n" + "=" * 80)
    print("JAVASCRIPT NAVIGATOR VALIDATION - TYPE-AWARE ANALYSIS")
    print("=" * 80)

    meta = data.get('metadata', {})
    all_results = data.get('results', [])
    error_summary = data.get('error_summary', {})

    # ── Resolve counts ────────────────────────────────────────────────────────
    max_samples = meta.get('max_samples', len(all_results))
    meta_successful = meta.get('successful', 0)
    meta_failed = meta.get('failed', 0)

    successful = [r for r in all_results if r.get('status') == 'success']
    failed = [r for r in all_results if r.get('status') == 'failed']

    total_attempted = max_samples if max_samples else (len(successful) + len(failed))
    actual_failed = meta_failed if meta_failed else len(failed)

    # ── 1. TRUE SUCCESS RATE ──────────────────────────────────────────────────
    print(f"\n📋 DATASET OVERVIEW")
    print("-" * 80)
    print(f"  Dataset: {meta.get('dataset', 'unknown')}")
    print(f"  Samples attempted: {total_attempted}")
    print(f"  Extraction succeeded: {len(successful)} ({_pct(len(successful), total_attempted):.1f}%)")
    print(f"  Extraction failed: {actual_failed} ({_pct(actual_failed, total_attempted):.1f}%)")

    if total_attempted > len(successful) + len(failed):
        omitted = total_attempted - len(successful) - len(failed)
        if omitted > 0:
            print(f"  Not in results array: {omitted} (non-JS / parse errors excluded by test runner)")

    dataset_name = meta.get('dataset', 'unknown')
    is_codesearchnet = 'codesearchnet' in dataset_name.lower()
    is_the_stack = 'the-stack' in dataset_name.lower() or 'stack' in dataset_name.lower()

    if _pct(len(successful), total_attempted) < 20:
        print(f"\n  ⚠️  NOTE: Only {_pct(len(successful), total_attempted):.1f}% of samples succeeded.")
        if is_codesearchnet:
            print(f"     CodeSearchNet 'javascript' split is multi-language — most samples are")
            print(f"     non-JS or invalid snippets that correctly fail at parse time.")
        elif is_the_stack:
            print(f"     the-stack samples may contain parse errors or non-standard syntax.")
        else:
            print(f"     Many samples may not be valid JavaScript.")
        print(f"     The {len(successful)} that passed ARE valid JavaScript.")

    if not successful:
        print("\n❌ No successful extractions to analyze.")
        return

    # ── 2. COMPONENT TYPE BREAKDOWN ───────────────────────────────────────────
    type_counts = defaultdict(int)
    anon_module_count = 0
    all_components = []

    for result in successful:
        for comp_id, comp in result.get('components', {}).items():
            if not isinstance(comp, dict):
                continue
            all_components.append(comp)
            ctype = comp.get('type', 'unknown')
            type_counts[ctype] += 1
            if _is_anonymous_module(comp):
                anon_module_count += 1

    total_components = len(all_components)
    module_count = type_counts.get('module', 0)
    func_count = type_counts.get('function', 0)

    print(f"\n🔧 COMPONENT EXTRACTION")
    print("-" * 80)
    print(f"  Total components: {total_components}")
    print(f"  Avg per file: {total_components / len(successful):.1f}")
    print(f"\n  Type breakdown:")
    for ctype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {ctype:12s}: {count:4d} ({_pct(count, total_components):.1f}%)")

    # ── 3. ANONYMOUS FUNCTION / MODULE FALLBACK DETECTION ─────────────────────
    if anon_module_count > 0:
        print(f"\n🚨 ANONYMOUS FUNCTION DETECTION")
        print("-" * 80)
        print(f"  MODULE-type components: {module_count}")
        print(f"  Of those, anonymous functions (MODULE fallback): {anon_module_count} ({_pct(anon_module_count, module_count):.1f}%)")
        print(f"\n  ⚠️  These are anonymous `function() {{...}}` snippets that the extractor")
        print(f"     could not classify, so they received a MODULE wrapper with:")
        print(f"       - name = repo name (not actual function name)")
        print(f"       - parameters = [] (actual params lost)")
        print(f"       - calls = [] (actual calls lost)")
        print(f"       - signature = 'module ...' (not real signature)")
        print(f"\n  Impact: {_pct(anon_module_count, total_components):.1f}% of all components have degraded extraction.")
        print(f"  Root cause: extractor.py walk() only matches named declarations.")
        print(f"  Fix: Add function_expression / arrow_function handling in walk().")

    # ── 4. ERROR BREAKDOWN ────────────────────────────────────────────────────
    if error_summary:
        print(f"\n⚠️  ERROR BREAKDOWN")
        print("-" * 80)
        for error_type, count in sorted(error_summary.items(), key=lambda x: -x[1]):
            print(f"  {error_type}: {count}")

    if failed:
        print(f"\n  Sample failures ({len(failed)} in results array):")
        for i, result in enumerate(failed[:3], 1):
            idx = result.get('sample_index', '?')
            err = str(result.get('error', 'unknown'))[:80]
            etype = result.get('error_type', '')
            print(f"    [{i}] sample_{idx}.js  ({etype}) {err}")

    # ── 5. PER-TYPE FIELD COVERAGE ────────────────────────────────────────────
    field_by_type = defaultdict(lambda: defaultdict(list))

    for comp in all_components:
        ctype = comp.get('type', 'unknown')
        for field, value in comp.items():
            has_value = bool(value) if not isinstance(value, list) else len(value) > 0
            field_by_type[ctype][field].append(1 if has_value else 0)

    important_fields = [
        'parameters', 'calls', 'return_type', 'signature', 'existing_docstring',
        'decorators', 'complexity', 'is_async', 'is_generator', 'imports',
        'parent_classes', 'methods', 'attributes', 'depends_on',
    ]

    print(f"\n📊 FIELD-LEVEL COVERAGE BY COMPONENT TYPE")
    print("-" * 80)

    all_known_types = ['function', 'class', 'method', 'constructor',
                        'global_variable', 'variable', 'field', 'static_field', 'module']
    for ctype in all_known_types:
        type_data = field_by_type.get(ctype)
        if not type_data:
            continue
        n = len(type_data.get('id', type_data.get('name', [])))
        expected = EXPECTED_FIELDS.get(ctype, set())

        print(f"\n  {ctype.upper()} ({n} components):")
        for field in important_fields:
            if field not in type_data:
                continue
            cov = _coverage(type_data[field])
            is_expected = field in expected
            if not is_expected:
                tag = "─"
            elif cov >= 80:
                tag = "✅"
            elif cov >= 40:
                tag = "⚠️"
            else:
                tag = "❌"
            suffix = " (N/A for this type)" if not is_expected else ""
            print(f"    {tag} {field:22s} {cov:5.1f}%{suffix}")

    # ── 6. AGGREGATE FIELD COVERAGE (all types) ───────────────────────────────
    print(f"\n📊 AGGREGATE FIELD COVERAGE (all {total_components} components)")
    print("-" * 80)

    field_stats = defaultdict(lambda: {'populated': 0, 'total': 0})
    for comp in all_components:
        for field, value in comp.items():
            field_stats[field]['total'] += 1
            if (value if not isinstance(value, list) else len(value) > 0):
                field_stats[field]['populated'] += 1

    coverage_list = []
    for field, stats in field_stats.items():
        cov = _pct(stats['populated'], stats['total'])
        coverage_list.append((field, cov, stats))
    coverage_list.sort(key=lambda x: -x[1])

    for field, cov, stats in coverage_list:
        bar = "█" * int(cov // 10) + "░" * (10 - int(cov // 10))
        print(f"  {bar} {field:22s} {cov:5.1f}% ({stats['populated']}/{stats['total']})")

    # ── 7. SMART RECOMMENDATIONS ──────────────────────────────────────────────
    print(f"\n💡 RECOMMENDATIONS")
    print("-" * 80)
    has_rec = False

    # 7a. Low overall extraction rate
    if _pct(len(successful), total_attempted) < 20:
        print(f"  ℹ️  Dataset extraction rate is {_pct(len(successful), total_attempted):.1f}%.")
        if is_codesearchnet:
            print(f"     This is normal for CodeSearchNet — most samples are non-JS snippets.")
            print(f"     Consider: Use a JS-only dataset (e.g. bigcode/the-stack) for higher yield.\n")
        elif is_the_stack:
            print(f"     Some the-stack files may contain syntax errors or non-standard JS.\n")
        else:
            print(f"     Many samples may not be valid JavaScript.\n")

    # 7b. Anonymous function / MODULE fallback
    if anon_module_count > 0:
        has_rec = True
        pct = _pct(anon_module_count, total_components)
        print(f"  🔴 CRITICAL: {anon_module_count} anonymous functions ({pct:.0f}% of components) hit MODULE fallback")
        print(f"     All extraction fields (params, calls, signature) are empty for these.")
        print(f"     Fix in backend/navigator/languages/javascript/extractor.py:")
        print(f"       1. In walk(), add matching for `function_expression` nodes")
        print(f"       2. In walk(), add matching for anonymous `arrow_function` outside variable_declarator")
        print(f"       3. Auto-generate names from context (parent property, callback arg, etc.)\n")

    # 7c. Type-specific field issues (only for fields EXPECTED for that type)
    real_issues = []
    for ctype, type_data in field_by_type.items():
        expected = EXPECTED_FIELDS.get(ctype, set())
        n = len(type_data.get('id', type_data.get('name', [])))
        for field in expected:
            if field in type_data:
                cov = _coverage(type_data[field])
                if cov < 50:
                    real_issues.append((ctype, field, cov, n))

    if real_issues:
        has_rec = True
        print(f"  🟡 TYPE-AWARE FIELD COVERAGE ISSUES:")
        for ctype, field, cov, n in sorted(real_issues, key=lambda x: x[2]):
            print(f"     {ctype}.{field}: {cov:.1f}% (of {n} {ctype}s)")

        # Specific advice
        func_return = next((cov for ct, f, cov, _ in real_issues if ct == 'function' and f == 'return_type'), None)
        if func_return is not None and func_return < 10:
            print(f"\n     → function.return_type at {func_return:.0f}%: JS is dynamically typed")
            print(f"       This is expected unless JSDoc @returns tags or TypeScript annotations exist")

        func_docstring = next((cov for ct, f, cov, _ in real_issues if ct == 'function' and f == 'existing_docstring'), None)
        if func_docstring is not None and func_docstring < 30:
            print(f"     → function.existing_docstring at {func_docstring:.0f}%: JSDoc comments")
            if is_codesearchnet:
                print(f"       CodeSearchNet strips surrounding context; docstrings often in 'comment' field")
            elif is_the_stack:
                print(f"       the-stack preserves full files; check if extractor finds /** ... */ blocks")
            print(f"       Check: extractor may need to search preceding lines for /** ... */")

        module_issues = [(f, cov) for ct, f, cov, _ in real_issues if ct == 'module']
        if module_issues:
            print(f"     → module.* fields are empty because modules are fallback wrappers")
            print(f"       Fixing the anonymous function detection (above) will resolve this")

    # 7d. HTTP fields note
    http_present = any(
        _coverage(field_by_type.get(ct, {}).get('http_method', [0])) > 0
        for ct in field_by_type
    )
    if not http_present:
        print(f"\n  ℹ️  HTTP/API fields (http_method, framework, etc.) are all 0%")
        print(f"     EXPECTED — dataset is general JS code, not Express/Koa/Fastify endpoints")

    # 7e. Overall quality for real functions (excluding module fallback)
    if func_count > 0:
        func_data = field_by_type.get('function', {})
        func_params = _coverage(func_data.get('parameters', []))
        func_calls = _coverage(func_data.get('calls', []))
        print(f"\n  ✅ ACTUAL FUNCTION EXTRACTION QUALITY (excluding MODULE fallback):")
        print(f"     function.parameters: {func_params:.1f}%")
        print(f"     function.calls:      {func_calls:.1f}%")
        if func_params >= 80 and func_calls >= 80:
            print(f"     → Named function extraction is GOOD.")
            print(f"     → The main issue is anonymous function handling, not extraction logic.")

    if not has_rec:
        print(f"  ✅ No critical issues found.")

    print(f"\n{'=' * 80}\n")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        # Search both the-stack and codesearchnet directories for latest results
        results_file = None
        for results_dir_name in ['the-stack', 'codesearchnet']:
            results_dir = Path('data/validation') / results_dir_name
            if results_dir.exists():
                results_files = sorted(results_dir.glob('js_navigator_results_*.json'), reverse=True)
                if results_files:
                    results_file = str(results_files[0])
                    print(f"Using latest results: {results_file}")
                    break

        if not results_file:
            print("No results found. Run test first:")
            print("  python test_navigator_js_codesearchnet.py 10")
            sys.exit(1)
    else:
        results_file = sys.argv[1]

    data = load_results(results_file)
    analyze_results(data)


if __name__ == '__main__':
    main()
