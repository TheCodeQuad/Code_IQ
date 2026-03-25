#!/usr/bin/env python3
"""
Integration Test: Comprehensive Docstring Truthfulness Evaluator

This script demonstrates and tests the new truthfulness evaluation system.

Features Tested:
- Component extraction from docstrings
- Component existence validation  
- Cross-file reference detection
- Hallucination detection
- Statistics generation
- Report generation

Usage:
    python test_truthfulness_evaluator.py
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.evaluator.truthfulness_comprehensive import ComprehensiveTruthfulnessEvaluator
from backend.eval_truthfulness_multi_system import MultiSystemTruthfulnessEvaluator
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def test_single_docstring_evaluation():
    """Test evaluating a single docstring"""
    print("\n" + "="*80)
    print("TEST 1: Single Docstring Evaluation")
    print("="*80)
    
    evaluator = ComprehensiveTruthfulnessEvaluator(
        navigator_output_dir="data/intermediate/navigator_output",
        use_llm=False,  # Use regex only for testing
        llm_mode="llama_cpp",
        cache_graphs=True
    )
    
    # Test docstring with real components
    docstring_python = """
    User authentication handler.
    
    This methods uses the `User` class for validation and the `is_adult()` 
    method to check age restrictions. The `__init__` constructor must be 
    called before using this authentication handler.
    """
    
    result = evaluator.evaluate_docstring(
        component_id="auth.authenticate_user",
        docstring=docstring_python,
        file_path="src/auth.py",
        repository_name="testrepo",
        language="python"
    )
    
    print(f"\nComponent ID: {result.component_id}")
    print(f"Repository: {result.repository}")
    print(f"File Path: {result.file_path}")
    print(f"Language: {result.language}")
    print(f"\nMentioned Components: {len(result.mentioned_components)}")
    
    for mention in result.mentioned_components:
        status = "✅ EXISTS" if mention.exists else "❌ HALLUCINATION"
        cross_file = " (cross-file)" if mention.is_cross_file else ""
        print(f"  - {mention.name}: {status}{cross_file}")
    
    print(f"\nMetrics:")
    print(f"  Total Mentions: {result.total_mentions}")
    print(f"  Existing: {result.existing_mentions}")
    print(f"  Existence Ratio: {result.existence_ratio:.1%}")
    print(f"  Hallucination Rate: {result.hallucination_rate:.1%}")
    print(f"  Cross-file References: {result.cross_file_mentions}")
    
    return result


def test_batch_evaluation():
    """Test evaluating multiple docstrings"""
    print("\n" + "="*80)
    print("TEST 2: Batch Evaluation")
    print("="*80)
    
    evaluator = ComprehensiveTruthfulnessEvaluator(
        navigator_output_dir="data/intermediate/navigator_output",
        use_llm=False,
        llm_mode="llama_cpp",
        cache_graphs=True
    )
    
    # Create multiple test components
    test_components = [
        {
            "component_id": "eval.User",
            "docstring": "Represents a user. Calls `__init__` and `is_adult()`.",
            "file_path": "eval.py",
            "repository": "testrepo",
            "language": "python"
        },
        {
            "component_id": "eval.User.__init__",
            "docstring": "Initialize a User with a name and age. Uses validation.",
            "file_path": "eval.py",
            "repository": "testrepo",
            "language": "python"
        },
        {
            "component_id": "eval.User.is_adult",
            "docstring": "Check if user is an `adult` using age >= 18.",
            "file_path": "eval.py",
            "repository": "testrepo",
            "language": "python"
        }
    ]
    
    results = evaluator.evaluate_batch(test_components)
    
    print(f"\nEvaluated {len(results)} components")
    
    for i, result in enumerate(results, 1):
        print(f"\n  {i}. {result.component_id}")
        print(f"     Existence: {result.existence_ratio:.1%}, Hallucination: {result.hallucination_rate:.1%}")
    
    return results


def test_summary_generation():
    """Test generating summary statistics"""
    print("\n" + "="*80)
    print("TEST 3: Summary Statistics Generation")
    print("="*80)
    
    evaluator = ComprehensiveTruthfulnessEvaluator(
        navigator_output_dir="data/intermediate/navigator_output",
        use_llm=False,
        llm_mode="llama_cpp"
    )
    
    # Generate summary for batch evaluation
    test_components = [
        {
            "component_id": "eval.User",
            "docstring": "User class with `__init__` method.",
            "file_path": "eval.py",
            "repository": "testrepo",
            "language": "python"
        },
        {
            "component_id": "eval.User.is_adult",
            "docstring": "Check if user age >= 18 using `is_adult_checker`.",
            "file_path": "eval.py",
            "repository": "testrepo",
            "language": "python"
        }
    ]
    
    results = evaluator.evaluate_batch(test_components)
    summary = evaluator.generate_summary_report(results)
    
    print(f"\nSummary Statistics:")
    print(f"  Total Docstrings: {summary.total_docstrings_analyzed}")
    print(f"  Total Mentions: {summary.total_components_mentioned}")
    print(f"  Existing: {summary.existing_components}")
    print(f"  Cross-file: {summary.cross_file_mentions}")
    print(f"  Avg Existence: {summary.avg_existence_ratio:.1%}")
    print(f"  Avg Hallucination: {summary.avg_hallucination_rate:.1%}")
    print(f"  Avg Mentions/Doc: {summary.avg_mentions_per_doc:.2f}")
    
    if summary.by_language:
        print(f"\n  By Language:")
        for lang, stats in summary.by_language.items():
            print(f"    - {lang}: {stats['docstrings']} docs, {stats['mentions']} mentions, {stats['avg_existence_ratio']:.1%} existence")
    
    return summary


def test_multi_system_evaluation():
    """Test multi-system comparative evaluation"""
    print("\n" + "="*80)
    print("TEST 4: Multi-System Comparative Evaluation")
    print("="*80)
    
    # Create test data with multiple systems
    test_data = {
        "system_1": [
            {
                "component_id": "eval.User",
                "docstring": "User class using `__init__` and `is_adult` methods.",
                "file_path": "eval.py",
                "repository": "testrepo",
                "language": "python"
            }
        ],
        "system_2": [
            {
                "component_id": "eval.User",
                "docstring": "User class with authentication and age validation.",
                "file_path": "eval.py",
                "repository": "testrepo",
                "language": "python"
            }
        ]
    }
    
    # Save test data to temp file
    test_file = Path("test_truthfulness_input.json")
    with open(test_file, 'w') as f:
        json.dump(test_data, f)
    
    try:
        multi_evaluator = MultiSystemTruthfulnessEvaluator(
            input_file=str(test_file),
            navigator_output_dir="data/intermediate/navigator_output",
            use_llm=False,
            llm_mode="llama_cpp"
        )
        
        all_results = multi_evaluator.evaluate_all_systems()
        
        print(f"\nEvaluated {len(all_results)} systems:")
        for system, results in all_results.items():
            print(f"  - {system}: {len(results)} components")
        
        # Generate reports
        output_dir = Path("test_truthfulness_output")
        print(f"\nGenerating reports to {output_dir}...")
        multi_evaluator.generate_comparative_report(all_results, output_dir)
        
        print(f"✅ Reports generated:")
        print(f"   - {output_dir}/truthfulness_detailed_results.json")
        print(f"   - {output_dir}/truthfulness_comparative_report.md")
        
        return all_results
    
    finally:
        test_file.unlink(missing_ok=True)


def test_component_extraction():
    """Test component extraction from docstrings"""
    print("\n" + "="*80)
    print("TEST 5: Component Extraction")
    print("="*80)
    
    evaluator = ComprehensiveTruthfulnessEvaluator(
        navigator_output_dir="data/intermediate/navigator_output",
        use_llm=False
    )
    
    test_docstrings = [
        ("Python", "Calls `User()` and `is_adult()` to validate user."),
        ("JavaScript", "Uses `this.validate()` and `User.check()` methods."),
        ("Java", "Calls `User.validate()` for authentication."),
    ]
    
    print("\nComponent Extraction Results:")
    
    for language, docstring in test_docstrings:
        components = evaluator.extract_components_from_docstring(docstring, language)
        print(f"\n  {language}:")
        print(f"    Input: {docstring}")
        print(f"    Extracted: {components}")


def test_cross_file_detection():
    """Test cross-file reference detection"""
    print("\n" + "="*80)
    print("TEST 6: Cross-File Reference Detection")
    print("="*80)
    
    evaluator = ComprehensiveTruthfulnessEvaluator(
        navigator_output_dir="data/intermediate/navigator_output",
        use_llm=False
    )
    
    # Load dependency graph
    component_db = evaluator.load_dependency_graph("testrepo")
    
    print(f"\nLoaded {len(component_db)} components for testrepo")
    
    # Show some components
    print("\nSample components:")
    for i, (comp_id, comp_data) in enumerate(list(component_db.items())[:5], 1):
        comp_type = comp_data.get("type", "unknown")
        location = comp_data.get("location", {})
        file_path = location.get("file_path", "unknown") if isinstance(location, dict) else "unknown"
        print(f"  {i}. {comp_id} ({comp_type}) in {Path(file_path).name if file_path != 'unknown' else 'unknown'}")


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("COMPREHENSIVE TRUTHFULNESS EVALUATOR - INTEGRATION TESTS")
    print("="*80)
    
    try:
        # Run tests
        test_component_extraction()
        test_cross_file_detection()
        test_single_docstring_evaluation()
        test_batch_evaluation()
        test_summary_generation()
        test_multi_system_evaluation()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("="*80)
        
        print("\nNext Steps:")
        print("1. Review the generated reports:")
        print("   - test_truthfulness_output/truthfulness_comparative_report.md")
        print("2. Integrate with your evaluation pipeline")
        print("3. Run on your actual datasets")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
