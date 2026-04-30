#!/usr/bin/env python3
"""
Repository-Specific Docstring Truthfulness Evaluator

Evaluates truthfulness for a specific repository, loading only that repo's writer output.

Usage:
    python evaluate_repository_truthfulness.py --repo testrepo --output data/validation/truthfulness
    python evaluate_repository_truthfulness.py --repo my_repo --no-llm --output results/
"""

import json
import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.evaluator.truthfulness_comprehensive import ComprehensiveTruthfulnessEvaluator
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Evaluate docstring truthfulness for a specific repository'
    )
    parser.add_argument(
        '--repo', '-r',
        type=str,
        required=True,
        help='Repository name (e.g., testrepo, my_repo) - will look for {repo}_writer_output.json'
    )
    parser.add_argument(
        '--writer-dir',
        type=str,
        default='data/intermediate/agent_output/writer',
        help='Directory containing writer output files'
    )
    parser.add_argument(
        '--navigator-dir',
        type=str,
        default='data/intermediate/navigator_output',
        help='Directory containing navigator output (dependency graphs)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data/validation/truthfulness',
        help='Directory to save evaluation results'
    )
    parser.add_argument(
        '--no-llm',
        action='store_true',
        help='Use regex-based extraction only (faster but less accurate)'
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    writer_dir = Path(args.writer_dir) if Path(args.writer_dir).is_absolute() else project_root / args.writer_dir
    navigator_dir = Path(args.navigator_dir) if Path(args.navigator_dir).is_absolute() else project_root / args.navigator_dir
    output_dir = Path(args.output) if Path(args.output).is_absolute() else project_root / args.output
    
    print("=" * 80)
    print(f"Repository Truthfulness Evaluation: {args.repo}")
    print("=" * 80)
    print(f"Writer output dir:   {writer_dir}")
    print(f"Navigator dir:       {navigator_dir}")
    print(f"Output dir:          {output_dir}")
    print(f"Using LLM:           {'No (regex only)' if args.no_llm else 'Yes (llama.cpp)'}")
    print("=" * 80)
    print()
    
    # Initialize evaluator
    evaluator = ComprehensiveTruthfulnessEvaluator(
        navigator_output_dir=str(navigator_dir),
        writer_output_dir=str(writer_dir),
        use_llm=not args.no_llm,
        llm_mode="llama_cpp",
        repository_name=args.repo
    )
    
    # Evaluate all docstrings from writer output for this repository
    print(f"Loading and evaluating docstrings for repository: {args.repo}")
    results = evaluator.evaluate_repository_writer_output(args.repo)
    
    if not results:
        print(f"❌ No docstrings found for repository '{args.repo}'")
        print(f"\nSearching for writer output files in {writer_dir}...")
        writer_files = list(writer_dir.glob("*writer_output.json"))
        if writer_files:
            print(f"Available writer output files:")
            for f in writer_files[:10]:
                print(f"  - {f.name}")
        else:
            print("No writer output files found!")
        return 1
    
    print(f"[OK] Evaluated {len(results)} docstrings")
    
    # Generate summary
    summary = evaluator.generate_summary_report(results)
    
    print(f"\n[SUMMARY] Metrics:")
    print(f"  Total Docstrings:        {summary.total_docstrings_analyzed}")
    print(f"  Total Mentions:          {summary.total_components_mentioned}")
    print(f"  Existing Components:     {summary.existing_components}")
    print(f"  Cross-file References:   {summary.cross_file_mentions}")
    print(f"  Avg Existence Ratio:     {summary.avg_existence_ratio:.1%}")
    print(f"  Avg Hallucination Rate:  {summary.avg_hallucination_rate:.1%}")
    print(f"  Avg Mentions Per Doc:    {summary.avg_mentions_per_doc:.2f}")
    
    # Language breakdown
    if summary.by_language:
        print(f"\n[BREAKDOWN] By Language:")
        for lang, stats in summary.by_language.items():
            print(f"  - {lang}: {stats['docstrings']} docs, {stats['mentions']} mentions, {stats['avg_existence_ratio']:.1%} existence")
    
    # Save results
    output_dir.mkdir(parents=True, exist_ok=True)
    
    json_file = output_dir / f"{args.repo}_truthfulness_results.json"
    md_file = output_dir / f"{args.repo}_truthfulness_report.md"
    
    print(f"\n[SAVING] Results...")
    evaluator.save_results_json(results, json_file)
    evaluator.generate_markdown_report(results, md_file)
    
    print(f"\n[DONE] Evaluation complete!")
    print(f"   Results: {json_file}")
    print(f"   Report:  {md_file}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
