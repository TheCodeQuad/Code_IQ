"""
COMPLETE VALIDATION GUIDE - All Approaches

This script demonstrates all 3 validation approaches:
1. File-by-file validation (gold vs adapter)
2. Directory validation with aggregation
3. CodeSearchNet benchmark validation

Run this to understand the validation system.
"""

import json
from pathlib import Path
from backend.validators.validation_framework import ValidationFramework
from backend.validators.codesearchnet_validator import CodeSearchNetValidator


def approach_1_single_file():
    """
    Approach 1: Validate a single file
    
    This compares:
    - Gold extractor output (raw AST facts)
    - Your adapter's CodeComponent output (normalized IR)
    
    Metrics:
    - Component count: how many components found?
    - Precision/Recall: how well did alignment work?
    - F1: harmonic mean
    - Field accuracy: how well is each field preserved?
    """
    print("\n" + "=" * 80)
    print("APPROACH 1: Single File Validation")
    print("=" * 80)
    
    validator = ValidationFramework()
    
    # Choose a test file
    test_file = "backend/navigator/scanner/test_repo/Token_Orchestrator-master/src/helpers.py"
    
    if Path(test_file).exists():
        print(f"Validating: {test_file}")
        
        metrics = validator.validate_file(test_file)
        
        print(f"\nResults:")
        print(f"  Gold Components: {metrics.total_gold_components}")
        print(f"  IR Components: {metrics.total_ir_components}")
        print(f"  Matched: {metrics.matched_components}")
        print(f"\n  Precision: {metrics.precision:.2%}")
        print(f"  Recall: {metrics.recall:.2%}")
        print(f"  F1: {metrics.f1:.2%}")
        print(f"\nField-Level Accuracy:")
        for field, accuracy in metrics.field_accuracy.items():
            print(f"  - {field}: {accuracy:.1f}%")
        
        if metrics.missing:
            print(f"\nMissing (in gold, not in IR):")
            for m in metrics.missing[:5]:
                print(f"  - {m}")
        
        if metrics.extra:
            print(f"\nExtra (in IR, not in gold):")
            for e in metrics.extra[:5]:
                print(f"  - {e}")
    else:
        print(f"Test file not found: {test_file}")


def approach_2_directory():
    """
    Approach 2: Validate entire directory
    
    This:
    - Walks all .py, .js, .java, .ts files
    - Validates each one
    - Aggregates statistics by language
    - Produces a JSON report with fine-grained results
    
    Output format:
    {
        'summary': {
            'languages': 3,
            'total_files': 45,
            'overall_f1': 0.92
        },
        'by_language': {
            'python': {
                'avg_f1': 0.94,
                'avg_precision': 0.96,
                'avg_recall': 0.92,
                'files': [...]
            },
            'javascript': {...}
        }
    }
    """
    print("\n" + "=" * 80)
    print("APPROACH 2: Directory Validation with Aggregation")
    print("=" * 80)
    
    validator = ValidationFramework()
    
    # Choose directory
    test_dir = "backend/repos"
    
    if Path(test_dir).exists():
        print(f"Validating directory: {test_dir}")
        print("(This may take a few minutes)\n")
        
        validator.validate_directory(test_dir)
        validator.print_summary()
        validator.save_report("validation_report_aggregated.json")
        
        print("\nReport saved to: validation_report_aggregated.json")
    else:
        print(f"Directory not found: {test_dir}")


def approach_3_codesearchnet():
    """
    Approach 3: Validate against CodeSearchNet
    
    This:
    - Downloads ~100 code snippets from CodeSearchNet (free, published dataset)
    - Runs both gold extractor and your adapter on the same code
    - Compares extraction results
    - Gives you external, unbiased benchmark
    
    Why this matters:
    - CodeSearchNet functions are real GitHub code
    - Already has ground truth annotations
    - Validates you're extracting correctly in the wild
    - Better than just internal validation
    
    Metrics:
    - Component discovery: did you find the functions?
    - Parameter accuracy: did you get params right?
    - Call accuracy: did you capture function calls?
    """
    print("\n" + "=" * 80)
    print("APPROACH 3: CodeSearchNet Benchmark Validation")
    print("=" * 80)
    
    csn_validator = CodeSearchNetValidator()
    
    print("\nValidating against CodeSearchNet (external benchmark)...")
    print("(Downloading ~50 samples, this will take 30-60 seconds)\n")
    
    try:
        # Validate on Python first (most complete in CodeSearchNet)
        result = csn_validator.validate_against_codesearchnet('python', max_samples=50)
        
        print(f"Language: {result['language'].upper()}")
        print(f"Samples tested: {result['successfully_parsed']}/{result['samples_tested']}")
        print(f"\nMetrics:")
        print(f"  Precision: {result.get('avg_precision', 0):.2%}")
        print(f"  Recall: {result.get('avg_recall', 0):.2%}")
        print(f"  F1: {result.get('avg_f1', 0):.2%}")
        
        print(f"\nSample Results (first 5):")
        for sample in result['samples'][:5]:
            print(f"  {sample['name']}: F1={sample['f1']:.2%}")
        
        # Save
        with open('validation_codesearchnet.json', 'w') as f:
            json.dump(result, f, indent=2)
        
        print("\nReport saved to: validation_codesearchnet.json")
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nNote: CodeSearchNet validation requires 'requests' package.")
        print("Run: pip install requests")


def approach_comparative_analysis():
    """
    Approach 4: Comparative Analysis (Optional)
    
    This compares extraction quality across:
    - Different languages
    - Different file sizes
    - Different complexity levels
    
    Helps identify if your adapter is:
    - Language-dependent (works better for Python than JS?)
    - Size-dependent (fails on large files?)
    - Complexity-dependent (misses complex code?)
    """
    print("\n" + "=" * 80)
    print("APPROACH 4: Comparative Analysis")
    print("=" * 80)
    
    print("""
This approach would analyze:
    1. F1 by language: Which languages have lowest F1?
       - Indicates language-specific extraction bugs
    
    2. F1 by file size: Does quality degrade on large files?
       - Indicates scalability issues
    
    3. F1 by complexity: Does complexity matter?
       - Some languages/patterns fail on nested structures
    
    4. Field accuracy: Which fields are least accurate?
       - Prioritize improvements on weak fields
    
To implement:
    - After running approach_2, analyze validation_report_aggregated.json
    - Group results by language, file size, complexity metrics
    - Look for patterns in F1 scores
    """)


def generate_recommendations(report_path: str = "validation_report_aggregated.json"):
    """
    Read validation report and generate improvement recommendations.
    """
    print("\n" + "=" * 80)
    print("INTERPRETATION & RECOMMENDATIONS")
    print("=" * 80)
    
    print("""
Quality Targets:

    F1 Score:
    ├─ 0.95+  : Excellent - minimal issues
    ├─ 0.85+  : Good - some edge cases
    ├─ 0.75+  : Acceptable - needs improvement
    └─ <0.75  : Poor - significant issues

    Field Accuracy:
    ├─ type:       Should be >99% (fundamental)
    ├─ location:   Should be >95% (line numbers can vary)
    ├─ signature:  Should be >90% (whitespace differences)
    ├─ parameters: Should be >85% (type inference limits)
    ├─ modifiers:  Should be >90% (fairly stable)
    └─ calls:      Should be >70% (hard to extract universally)

Common Issues:

    Low Precision (few false positives):
    - IR finding components gold doesn't
    - Usually: global variable detection being too greedy
    - Fix: Be more selective in variable extraction

    Low Recall (missing components):
    - IR missing components gold finds
    - Usually: nested functions, lambdas, inline functions
    - Fix: Walk the entire AST more thoroughly

    Low Field Accuracy for 'calls':
    - Hard to distinguish calls from variable access
    - Language-specific syntax (method chaining, etc.)
    - Consider pragmatism: capture high-confidence calls only

    Inconsistent across languages:
    - Each language has unique patterns
    - Python: decorators, class methods vs functions
    - JS: arrow functions, hoisting, dynamic nature
    - Java: annotations, nested classes, overloading

Next Steps:

    1. Run approach_2 on your repos
    2. Identify languages/files with low F1
    3. Manually inspect missing/extra components
    4. Debug gold extractor vs adapter extraction
    5. Fix adapter logic incrementally
    6. Re-run validation to verify improvements
    7. Aim for F1 > 0.90 before production use
    """)


if __name__ == '__main__':
    import sys
    
    print("\n" + "🔍 CODE COMPONENT EXTRACTION VALIDATION" + "\n")
    
    if len(sys.argv) > 1:
        approach = sys.argv[1]
        
        if approach == '1':
            approach_1_single_file()
        elif approach == '2':
            approach_2_directory()
        elif approach == '3':
            approach_3_codesearchnet()
        elif approach == '4':
            approach_comparative_analysis()
        elif approach == 'all':
            approach_1_single_file()
            approach_2_directory()
            try:
                approach_3_codesearchnet()
            except Exception as e:
                print(f"\nCodeSearchNet validation skipped: {e}")
            approach_comparative_analysis()
            generate_recommendations()
        else:
            print(f"Unknown approach: {approach}")
    else:
        print("Usage:")
        print("  python validation_guide.py 1    # Single file validation")
        print("  python validation_guide.py 2    # Directory validation")
        print("  python validation_guide.py 3    # CodeSearchNet validation")
        print("  python validation_guide.py 4    # Comparative analysis")
        print("  python validation_guide.py all  # Run all approaches")
        print("")
        print("Or import programmatically:")
        print("  from backend.validators import ValidationFramework")
        print("  validator = ValidationFramework()")
        print("  validator.validate_directory('path')")
