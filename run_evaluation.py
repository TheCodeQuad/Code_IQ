#!/usr/bin/env python
"""
Entry point to run evaluation on leetcode documentation
Run from project root: python run_evaluation.py --input <path-to-json>
"""
import sys
import json
import argparse
from pathlib import Path

# Set up paths to handle both import styles
project_root = Path(__file__).parent
backend_root = project_root / "backend"

# Insert in order: backend first (for `from evaluator.*`), then project root (for `from backend.*`)
sys.path.insert(0, str(backend_root))
sys.path.insert(0, str(project_root))

from backend.unified_evaluator import UnifiedEvaluator

def main():
    parser = argparse.ArgumentParser(
        description="Evaluate AI-generated documentation"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to documentation JSON file"
    )
    parser.add_argument(
        "--repo",
        default="leetcode",
        help="Repository name (default: leetcode)"
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: data/validation/{repo})"
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    print(f"[INFO] Loading documentation from: {input_path}")
    with open(input_path) as f:
        docs = json.load(f)
    print(f"[INFO] Loaded {len(docs)} documented components")
    
    # Run evaluator
    print("\n[INFO] Starting unified evaluation (completeness + helpfulness + truthfulness)...")
    evaluator = UnifiedEvaluator(args.repo)
    
    try:
        results = evaluator.evaluate_all()
        
        print("\n[SUCCESS] Evaluation completed!")
        
        # Show summary
        if "completeness" in results:
            print(f"\n[COMPLETENESS] Overall score: {results['completeness']['summary'].get('overall_score', 'N/A')}")
        if "truthfulness" in results:
            print(f"[TRUTHFULNESS] Existence ratio: {results['truthfulness']['summary'].get('avg_existence_ratio', 'N/A')}")
        if "helpfulness" in results:
            print(f"[HELPFULNESS] Average score: {results['helpfulness']['summary'].get('average_score', 'N/A')}")
        
        # Save results
        output_dir = Path(args.output_dir or f"data/validation/{args.repo}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / "evaluation_results.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n[INFO] Full results saved to: {output_file}")
        
        return 0
        
    except Exception as e:
        print(f"\n[ERROR] Evaluation failed: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
