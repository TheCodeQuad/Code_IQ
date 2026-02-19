"""
JavaScript Navigator Validation - Detailed Analysis & Error Breakdown

This script performs detailed analysis on the validation results and helps debug issues.

Usage:
    python analyze_js_validation_results.py [results_json_file]
    
Example:
    python analyze_js_validation_results.py data/validation/codesearchnet/js_navigator_results_5_samples.json
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any


class ValidationResultsAnalyzer:
    """Analyze validation results in detail."""
    
    def __init__(self, results_file: str):
        self.results_file = Path(results_file)
        self.data = self._load_results()
    
    def _load_results(self) -> Dict[str, Any]:
        """Load results JSON."""
        if not self.results_file.exists():
            print(f"Error: Results file not found: {self.results_file}")
            sys.exit(1)
        
        with open(self.results_file, 'r') as f:
            return json.load(f)
    
    def run(self):
        """Run comprehensive analysis."""
        print("\n" + "="*80)
        print("JAVASCRIPT NAVIGATOR VALIDATION - DETAILED ANALYSIS")
        print("="*80)
        
        self._analyze_metadata()
        self._analyze_success_rate()
        self._analyze_components()
        self._analyze_errors()
        self._analyze_field_coverage()
        self._generate_recommendations()
    
    def _analyze_metadata(self):
        """Analyze dataset metadata."""
        meta = self.data.get('metadata', {})
        
        print(f"\n📋 METADATA")
        print("-" * 80)
        print(f"Dataset: {meta.get('dataset', 'unknown')}")
        print(f"Samples: {meta.get('max_samples', 0)}")
        print(f"Successful: {meta.get('successful', 0)}")
        print(f"Failed: {meta.get('failed', 0)}")
    
    def _analyze_success_rate(self):
        """Analyze success/failure rate."""
        results = self.data.get('results', [])
        
        successful = [r for r in results if r.get('status') == 'success']
        failed = [r for r in results if r.get('status') == 'failed']
        
        total = len(results)
        success_pct = 100 * len(successful) / max(total, 1)
        
        print(f"\n✅ SUCCESS RATE")
        print("-" * 80)
        print(f"Total: {total}")
        print(f"Successful: {len(successful)} ({success_pct:.1f}%)")
        print(f"Failed: {len(failed)}")
        
        # Health check
        if success_pct == 100:
            print("\n✓ Excellent! All samples processed successfully.")
        elif success_pct >= 80:
            print("\n⚠ Good, but some failures. See error breakdown below.")
        else:
            print(f"\n✗ Low success rate ({success_pct:.1f}%). Critical issues detected.")
    
    def _analyze_components(self):
        """Analyze component extraction."""
        results = self.data.get('results', [])
        successful = [r for r in results if r.get('status') == 'success']
        
        if not successful:
            print("\n❌ COMPONENT EXTRACTION: No successful extractions")
            return
        
        component_counts = [r.get('component_count', 0) for r in successful]
        total_components = sum(component_counts)
        avg_components = total_components / len(successful)
        max_components = max(component_counts)
        min_components = min(component_counts)
        
        print(f"\n🔧 COMPONENT EXTRACTION")
        print("-" * 80)
        print(f"Total components: {total_components}")
        print(f"Per file - min: {min_components}, max: {max_components}, avg: {avg_components:.1f}")
        
        # Distribution
        print(f"\nDistribution:")
        dist = defaultdict(int)
        for c in component_counts:
            dist[c] += 1
        
        for count in sorted(dist.keys()):
            print(f"  {count} components: {dist[count]} files")
        
        # Detailed component analysis
        if successful:
            first = successful[0]
            components = first.get('components', {})
            
            if components:
                print(f"\n📦 Sample component (from {first.get('file_path')}):")
                sample_comp = list(components.values())[0]
                
                # Group fields
                populated_fields = {k: v for k, v in sample_comp.items() if v}
                empty_fields = {k: v for k, v in sample_comp.items() if not v}
                
                print(f"  Populated: {len(populated_fields)} fields")
                for key in sorted(populated_fields.keys())[:10]:
                    val = populated_fields[key]
                    if isinstance(val, str) and len(val) > 50:
                        val = val[:47] + "..."
                    print(f"    ✓ {key}: {val}")
                
                if empty_fields:
                    print(f"  Empty: {len(empty_fields)} fields")
                    for key in sorted(empty_fields.keys())[:5]:
                        print(f"    ✗ {key}: {empty_fields[key]}")
    
    def _analyze_errors(self):
        """Analyze error breakdown."""
        error_summary = self.data.get('error_summary', {})
        results = self.data.get('results', [])
        failed = [r for r in results if r.get('status') == 'failed']
        
        if not error_summary and not failed:
            print(f"\n🎉 ERROR ANALYSIS: No errors!")
            return
        
        print(f"\n⚠️  ERROR BREAKDOWN")
        print("-" * 80)
        
        if error_summary:
            print("Error types:")
            for error_type, count in sorted(error_summary.items(), key=lambda x: -x[1]):
                print(f"  - {error_type}: {count}")
        
        # Sample errors (if any)
        if failed:
            print(f"\nSample failures ({len(failed)} total):")
            for i, result in enumerate(failed[:3], 1):
                print(f"\n  [{i}] {result.get('file_path')} → {result.get('func_name')}")
                error = result.get('error', 'unknown')
                if isinstance(error, str):
                    error_lines = error.split('\n')
                    for line in error_lines[:3]:
                        print(f"      {line}")
    
    def _analyze_field_coverage(self):
        """Analyze field population across components."""
        results = self.data.get('results', [])
        successful = [r for r in results if r.get('status') == 'success']
        
        if not successful:
            return
        
        field_stats = defaultdict(lambda: {'populated': 0, 'total': 0})
        
        for result in successful:
            components = result.get('components', {})
            for comp in components.values():
                for field, value in comp.items():
                    field_stats[field]['total'] += 1
                    if value:  # Truthy check
                        field_stats[field]['populated'] += 1
        
        print(f"\n📊 FIELD COVERAGE")
        print("-" * 80)
        
        # Sort by coverage percentage
        coverage_list = []
        for field, stats in field_stats.items():
            coverage = 100 * stats['populated'] / max(stats['total'], 1)
            coverage_list.append((field, coverage, stats))
        
        coverage_list.sort(key=lambda x: -x[1])
        
        print("Field population rate:")
        for field, coverage, stats in coverage_list[:15]:
            stars = "█" * int(coverage // 10) + "░" * (10 - int(coverage // 10))
            print(f"  {stars} {field:20s} {coverage:6.1f}% ({stats['populated']}/{stats['total']})")
        
        if len(coverage_list) > 15:
            print(f"  ... and {len(coverage_list) - 15} more fields")
    
    def _generate_recommendations(self):
        """Generate actionable recommendations."""
        results = self.data.get('results', [])
        meta = self.data.get('metadata', {})
        
        successful = [r for r in results if r.get('status') == 'success']
        failed = [r for r in results if r.get('status') == 'failed']
        
        print(f"\n💡 RECOMMENDATIONS")
        print("-" * 80)
        
        success_pct = 100 * len(successful) / max(len(results), 1)
        
        if success_pct < 50:
            print("🔴 CRITICAL: Fix fundamental issues first")
            print("  1. Verify tree-sitter JavaScript parser is installed")
            print("     python -m tree_sitter download javascript")
            print("  2. Test basic extraction with minimal example")
            print("  3. Review error messages in stderr")
        
        elif success_pct < 80:
            print("🟡 MODERATE: Some files failing")
            print("  1. Review failed samples in detail")
            print("  2. Check for syntax edge cases")
            print("  3. Improve error handling")
        
        elif success_pct == 100:
            print("✅ EXCELLENT: All samples parsed successfully!")
            
            # Additional checks
            if successful:
                sample = successful[0]
                components = sample.get('components', {})
                if components:
                    comp = list(components.values())[0]
                    populated = sum(1 for v in comp.values() if v)
                    total = len(comp)
                    field_coverage = 100 * populated / max(total, 1)
                    
                    if field_coverage < 50:
                        print("  But: Low field population (check if all features are implemented)")
                    elif field_coverage < 80:
                        print("  Note: Good field population, minor gaps remain")
                    else:
                        print("  Note: Excellent field coverage!")
        
        print(f"\nNext steps:")
        print(f"  1. View full results: {self.results_file}")
        print(f"  2. Scale up testing: python test_navigator_js_codesearchnet.py 20")
        print(f"  3. Compare with gold: python backend/validators/validation_guide.py")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        # Find latest results
        results_dir = Path('data/validation/codesearchnet')
        if results_dir.exists():
            results_files = sorted(results_dir.glob('js_navigator_results_*.json'), reverse=True)
            if results_files:
                results_file = str(results_files[0])
                print(f"Using latest results: {results_file}")
            else:
                print("No results found. Run test first:")
                print("  python test_navigator_js_codesearchnet.py 5")
                sys.exit(1)
        else:
            print("No results found. Run test first:")
            print("  python test_navigator_js_codesearchnet.py 5")
            sys.exit(1)
    else:
        results_file = sys.argv[1]
    
    analyzer = ValidationResultsAnalyzer(results_file)
    analyzer.run()


if __name__ == '__main__':
    main()
