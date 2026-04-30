"""
Script to run truthfulness evaluation on generated docstrings.

This script evaluates whether components mentioned in generated docstrings
actually exist in the repository and are contextually correct.

Usage:
    python eval_truthfulness.py
    python eval_truthfulness.py --repo testrepo
    python eval_truthfulness.py --repo testrepo --no-llm
    python eval_truthfulness.py --repo testrepo --llm-mode llama_cpp
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.evaluator.truthfulness_comprehensive import ComprehensiveTruthfulnessEvaluator
from backend.utils.logger import get_logger
from backend.utils.paths import DATA_ROOT

logger = get_logger(__name__)


def main():
    """Main entry point for truthfulness evaluation"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Evaluate truthfulness of generated docstrings'
    )
    parser.add_argument(
        '--repo', '-r',
        type=str,
        default=None,
        help='Repository name to evaluate (e.g., testrepo). If not provided, evaluates all repos.'
    )
    parser.add_argument(
        '--writer-dir',
        type=str,
        default=str(DATA_ROOT / 'intermediate' / 'agent_output' / 'writer'),
        help='Directory containing writer output JSON files'
    )
    parser.add_argument(
        '--navigator-dir',
        type=str,
        default=str(DATA_ROOT / 'intermediate' / 'navigator_output'),
        help='Directory containing navigator output (DAGs, components)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=str(DATA_ROOT / 'validation' / 'truthfulness'),
        help='Directory to save evaluation results'
    )
    parser.add_argument(
        '--llm-mode',
        type=str,
        default='llama_cpp',
        help='Local LLM to use for component extraction. Only llama_cpp is supported.'
    )
    parser.add_argument(
        '--no-llm',
        action='store_true',
        default=False,
        help='Disable LLM and use regex-based extraction only (faster but less accurate)'
    )
    
    args = parser.parse_args()
    
    # Use LLM by default unless --no-llm is specified
    use_llm = not args.no_llm
    
    # Resolve paths
    writer_dir = Path(args.writer_dir)
    if not writer_dir.is_absolute():
        writer_dir = project_root / writer_dir

    navigator_dir = Path(args.navigator_dir)
    if not navigator_dir.is_absolute():
        navigator_dir = project_root / navigator_dir

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir
    
    print("=" * 80)
    print("Docstring Truthfulness Evaluation")
    print("=" * 80)
    print(f"Writer output:   {writer_dir}")
    print(f"Navigator dir:   {navigator_dir}")
    print(f"Output dir:      {output_dir}")
    print(f"Repository:      {args.repo if args.repo else 'All repositories'}")
    print(f"Using LLM:       {'Yes' if use_llm else 'No (regex-only)'}")
    if use_llm:
        print(f"LLM Mode:        {args.llm_mode}")
    print("=" * 80)
    print()
    
    # Create evaluator
    evaluator = ComprehensiveTruthfulnessEvaluator(
        navigator_output_dir=str(navigator_dir),
        writer_output_dir=str(writer_dir),
        use_llm=use_llm,
        llm_mode=args.llm_mode,
        repository_name=args.repo
    )
    
    # Run evaluation
    if args.repo:
        print(f"Starting evaluation for repository: {args.repo}")
        results = evaluator.evaluate_repository_writer_output(args.repo)
        repo_label = args.repo
    else:
        print("Starting evaluation for all repositories...")
        # Load all writer output files
        writer_files = list(writer_dir.glob("*_writer_output.json"))
        logger.info(f"Found {len(writer_files)} writer output files")
        
        all_results = []
        for writer_file in writer_files:
            # Extract repository name from filename
            repo_name = writer_file.stem.replace('_writer_output', '').replace('_output', '')
            logger.info(f"Processing {repo_name}...")
            
            try:
                repo_results = evaluator.evaluate_repository_writer_output(repo_name)
                all_results.extend(repo_results)
            except Exception as e:
                logger.error(f"Error processing {repo_name}: {e}")
        
        results = all_results
        repo_label = "all_repositories"
    
    if not results:
        print(f"❌ No docstrings found")
        return 1
    
    print(f"✅ Evaluated {len(results)} docstrings")
    
    # Generate summary
    summary = evaluator.generate_summary_report(results)
    
    print(f"\n📊 Summary Metrics:")
    print(f"  Total Docstrings:        {summary.total_docstrings_analyzed}")
    print(f"  Total Mentions:          {summary.total_components_mentioned}")
    print(f"  Existing Components:     {summary.existing_components}")
    print(f"  Cross-file References:   {summary.cross_file_mentions}")
    print(f"  Avg Existence Ratio:     {summary.avg_existence_ratio:.1%}")
    print(f"  Avg Hallucination Rate:  {summary.avg_hallucination_rate:.1%}")
    print(f"  Avg Mentions Per Doc:    {summary.avg_mentions_per_doc:.2f}")
    
    # Language breakdown
    if summary.by_language:
        print(f"\n📚 By Language:")
        for lang, stats in sorted(summary.by_language.items()):
            print(f"  - {lang}: {stats['docstrings']} docs, {stats['mentions']} mentions, {stats['avg_existence_ratio']:.1%} existence")
    
    # Save results
    output_dir.mkdir(parents=True, exist_ok=True)
    
    json_file = output_dir / f"{repo_label}_truthfulness_results.json"
    md_file = output_dir / f"{repo_label}_truthfulness_report.md"
    
    print(f"\n💾 Saving results...")
    evaluator.save_results_json(results, json_file)
    evaluator.generate_markdown_report(results, md_file)
    
    print(f"\n✅ Evaluation complete!")
    print(f"   Results: {json_file}")
    print(f"   Report:  {md_file}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

