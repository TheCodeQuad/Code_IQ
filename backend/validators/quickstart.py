# """
# QUICK START - Validation System

# This script shows you exactly how to use the validation framework
# with concrete examples for your codebase.

# Just run: python backend/validators/quickstart.py
# """

# import sys
# from pathlib import Path
# from backend.validators.validation_framework import ValidationFramework

# def main():
#     print("\n" + "="*80)
#     print("CODE COMPONENT EXTRACTION VALIDATION - QUICK START")
#     print("="*80)
    
#     print("""
# What is this?
#   This validates that your CodeComponent/IR extraction layer correctly
#   preserves information from the official AST.

#   It compares:
#   - Gold Extractor: Direct AST facts (unbiased ground truth)
#   - Your Adapter: CodeComponent IR (what you built)
  
#   Then measures how well they align.

# Three Validation Tiers:

#   Tier 1: CodeSearchNet (1 minute) ⚡
#     "Does my extractor work on real GitHub code?"
#     Uses published external dataset.
    
#   Tier 2: Directory Scan (5-30 minutes) 📊  
#     "What's my overall quality across all files?"
#     Validates all .py, .js, .java, .ts files in a repo.
    
#   Tier 3: End-to-End (varies) ✨
#     "Does the full pipeline work (parse → extract → docstring)?"
#     Runs the complete system.

# Which one should you run?

#   For QUICK feedback → Tier 1 (1 min)
#   For DETAILED analysis → Tier 2 (5-30 min)
#   For PRODUCTION confidence → All 3 (30-60 min)
# """)
    
#     # Show available test repos
#     repos_dir = Path("backend/repos")
#     test_files_dir = Path("backend/navigator/scanner/test_repo")
    
#     print("\nAvailable test repositories:")
#     repos = []
    
#     if repos_dir.exists():
#         for repo in repos_dir.iterdir():
#             if repo.is_dir():
#                 py_files = list(repo.glob("**/*.py"))
#                 js_files = list(repo.glob("**/*.js"))
#                 java_files = list(repo.glob("**/*.java"))
#                 print(f"  ✓ {repo.name}: {len(py_files)} .py, {len(js_files)} .js, {len(java_files)} .java")
#                 repos.append(repo)
    
#     if test_files_dir.exists():
#         for repo in test_files_dir.iterdir():
#             if repo.is_dir() and "test_repo" in str(repo):
#                 py_files = list(repo.glob("**/*.py"))
#                 js_files = list(repo.glob("**/*.js"))
#                 print(f"  ✓ {repo.name}: {len(py_files)} .py, {len(js_files)} .js")
#                 repos.append(repo)
    
#     if not repos:
#         print("  (No test repositories found)")
    
#     print("\n" + "-" * 80)
#     print("TIER 2 EXAMPLE: Validate a Directory")
#     print("-" * 80)
    
#     if repos:
#         target_repo = repos[0]
#         print(f"\nValidating: {target_repo}")
#         print("(This will scan all code files and measure extraction quality...)\n")
        
#         try:
#             validator = ValidationFramework()
#             validator.validate_directory(str(target_repo))
            
#             print("\n" + "-" * 80)
#             validator.print_summary()
            
#             report_file = "validation_report_quick_sample.json"
#             validator.save_report(report_file)
#             print(f"\nFull report saved: {report_file}")
            
#             print("\n" + "-" * 80)
#             print("INTERPRETING YOUR RESULTS")
#             print("-" * 80)
#             print("""
# F1 Score means:
#   - 0.95+  : Excellent (ready for production)
#   - 0.85+  : Good (some refinement needed)
#   - 0.75+  : Acceptable (significant improvements needed)
#   - <0.75  : Poor (major issues)

# Precision vs Recall:
#   - High precision, low recall → Missing components
#   - Low precision, high recall → Over-extracting components
#   - Balanced (P ≈ R) → System working well

# Field Accuracy:
#   - type, location, signature → Should be very high (>90%)
#   - parameters, modifiers → High (>80%)
#   - calls → Lower is okay (>60%, hard to extract)

# What to do next:
#   1. Look at the report file (validation_report_quick_sample.json)
#   2. Find files with lowest F1 scores
#   3. Manually inspect those files
#   4. Debug the extraction logic
#   5. Re-run validation to verify improvements
# """)
            
#         except Exception as e:
#             print(f"Error during validation: {e}")
#             print("\nTroubleshooting:")
#             print("  - Make sure files are readable")
#             print("  - Check that the repository structure is correct")
#             print("  - Review error messages above for details")
    
#     print("\n" + "-" * 80)
#     print("NEXT STEPS")
#     print("-" * 80)
#     print("""
# 1. To run Tier 1 (CodeSearchNet benchmark):
#    python backend/validators/validation_guide.py 3

# 2. To run full comparison:
#    python backend/validators/validation_guide.py 2

# 3. To see detailed documentation:
#    cat backend/validators/README.md

# 4. To compare your approach vs hybrid:
#    cat backend/validators/APPROACH_COMPARISON.md

# 5. To programmatically use the framework:
#    from backend.validators.validation_framework import ValidationFramework
#    v = ValidationFramework()
#    m = v.validate_file('path/to/file.py')
#    print(f'F1: {m.f1:.2%}')
# """)
    
#     print("\n" + "="*80)
#     print("✅ Validation system is ready! Choose what to run above.")
#     print("="*80 + "\n")


# if __name__ == '__main__':
#     main()
