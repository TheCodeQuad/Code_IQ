"""
Multi-System Docstring Truthfulness Evaluator

Evaluates and compares the truthfulness of AI-generated docstrings from five different systems.

Workflow:
1. Load docstrings data from completeness_evaluation_cleaned.json (contains 5 systems)
2. For each docstring, use local LLM (llama.cpp) to extract mentioned components
3. Check if extracted components actually exist in the repository dependency graph
4. Calculate statistics: existence ratio, cross-file references, hallucination rate
5. Generate comparative report (docstring_truthfulness_report.md)

Usage:
    python -m backend.eval_truthfulness_multi_system \\
        --input data/validation/completeness_evaluation_cleaned.json \\
        --navigator-dir data/intermediate/navigator_output \\
        --output-dir data/validation/truthfulness
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict
from dataclasses import dataclass, asdict
from tqdm import tqdm

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.utils.logger import get_logger
from backend.evaluator.truthfulness import TruthfulnessEvaluator, TruthfulnessResult, ComponentMention

logger = get_logger(__name__)


@dataclass
class SystemComparison:
    """Comparison statistics for a single system"""
    system_name: str
    total_docstrings: int
    total_mentions: int
    existing_mentions: int
    cross_file_mentions: int
    avg_existence_ratio: float
    avg_hallucination_rate: float
    avg_mentions_per_doc: float
    by_language: Dict[str, Dict[str, Any]]


class MultiSystemTruthfulnessEvaluator:
    """
    Evaluates truthfulness across multiple docstring generation systems.
    """
    
    def __init__(
        self,
        input_file: str,
        navigator_output_dir: str,
        use_llm: bool = True,
        llm_mode: str = "llama_cpp"
    ):
        """
        Initialize multi-system evaluator.
        
        Args:
            input_file: Path to completeness_evaluation_cleaned.json
            navigator_output_dir: Directory containing navigator output (DAGs, components)
            use_llm: Whether to use LLM for component extraction
            llm_mode: Which LLM to use ("llama_cpp" for local model)
        """
        self.input_file = Path(input_file)
        self.navigator_output_dir = Path(navigator_output_dir)
        
        # Initialize base truthfulness evaluator
        self.base_evaluator = TruthfulnessEvaluator(
            writer_output_dir=str(self.input_file.parent),  # Dummy, not used
            navigator_output_dir=str(navigator_output_dir),
            use_llm=use_llm,
            llm_mode=llm_mode
        )
        
        logger.info(f"Initialized with {len(self.base_evaluator.component_db)} components from navigator")
    
    def load_multi_system_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load docstrings from multiple systems.
        
        Expected format in input file:
        {
            "system_1": [...components with docstrings...],
            "system_2": [...components with docstrings...],
            ...
        }
        
        Returns:
            Dictionary mapping system_name to list of component data
        """
        if not self.input_file.exists():
            raise FileNotFoundError(f"Input file not found: {self.input_file}")
        
        with open(self.input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle different possible formats
        systems_data = {}
        
        if isinstance(data, dict):
            # Check if it has system_1, system_2, etc.
            system_keys = [k for k in data.keys() if k.startswith('system_')]
            
            if system_keys:
                # Direct system mapping
                for system_key in system_keys:
                    systems_data[system_key] = data[system_key]
            else:
                # Try to find components with system indicators
                # Assume each component has a 'system' field
                by_system = defaultdict(list)
                components = data.get('components', [])
                
                for comp in components:
                    system = comp.get('system', 'system_1')
                    by_system[system].append(comp)
                
                systems_data = dict(by_system)
        
        elif isinstance(data, list):
            # List of components, group by system field
            by_system = defaultdict(list)
            for comp in data:
                system = comp.get('system', 'system_1')
                by_system[system].append(comp)
            systems_data = dict(by_system)
        
        logger.info(f"Loaded data for {len(systems_data)} systems")
        for system, components in systems_data.items():
            logger.info(f"  {system}: {len(components)} components")
        
        return systems_data
    
    def evaluate_system(
        self,
        system_name: str,
        components: List[Dict[str, Any]]
    ) -> Dict[str, TruthfulnessResult]:
        """
        Evaluate all docstrings from a single system.
        
        Args:
            system_name: Name of the system being evaluated
            components: List of component dictionaries with docstrings
            
        Returns:
            Dictionary mapping component_id to TruthfulnessResult
        """
        results = {}
        
        logger.info(f"Evaluating {system_name}...")
        
        for comp_data in tqdm(components, desc=f"Evaluating {system_name}"):
            try:
                # Extract necessary fields
                component_id = comp_data.get('id', comp_data.get('component_id', 'unknown'))
                docstring = comp_data.get('docstring', comp_data.get('generated_docstring', ''))
                language = comp_data.get('language', 'python')
                file_path = comp_data.get('file_path', '')
                
                # Also check in location field
                if not file_path and 'location' in comp_data:
                    location = comp_data['location']
                    if isinstance(location, dict):
                        file_path = location.get('file_path', '')
                
                if not docstring:
                    continue
                
                # Use base evaluator to evaluate this docstring
                result = self.base_evaluator.evaluate_docstring(
                    component_id=component_id,
                    docstring=docstring,
                    file_path=file_path,
                    language=language
                )
                
                results[component_id] = result
            
            except Exception as e:
                logger.error(f"Error evaluating component {comp_data.get('id', 'unknown')}: {e}")
        
        return results
    
    def evaluate_all_systems(self) -> Dict[str, Dict[str, TruthfulnessResult]]:
        """
        Evaluate all systems.
        
        Returns:
            Dictionary mapping system_name to results dictionary
        """
        systems_data = self.load_multi_system_data()
        all_results = {}
        
        for system_name, components in systems_data.items():
            results = self.evaluate_system(system_name, components)
            all_results[system_name] = results
        
        return all_results
    
    def calculate_system_stats(
        self,
        system_name: str,
        results: Dict[str, TruthfulnessResult]
    ) -> SystemComparison:
        """Calculate aggregate statistics for a system"""
        
        if not results:
            return SystemComparison(
                system_name=system_name,
                total_docstrings=0,
                total_mentions=0,
                existing_mentions=0,
                cross_file_mentions=0,
                avg_existence_ratio=0.0,
                avg_hallucination_rate=0.0,
                avg_mentions_per_doc=0.0,
                by_language={}
            )
        
        total_docstrings = len(results)
        total_mentions = sum(r.total_mentions for r in results.values())
        existing_mentions = sum(r.existing_mentions for r in results.values())
        cross_file_mentions = sum(r.cross_file_mentions for r in results.values())
        
        avg_existence_ratio = sum(r.existence_ratio for r in results.values()) / total_docstrings
        avg_hallucination_rate = sum(r.hallucination_rate for r in results.values()) / total_docstrings
        avg_mentions_per_doc = total_mentions / total_docstrings
        
        # Group by language
        by_language = defaultdict(lambda: {
            'docstrings': 0,
            'mentions': 0,
            'existing': 0,
            'cross_file': 0,
            'existence_ratios': []
        })
        
        for result in results.values():
            lang = result.language
            by_language[lang]['docstrings'] += 1
            by_language[lang]['mentions'] += result.total_mentions
            by_language[lang]['existing'] += result.existing_mentions
            by_language[lang]['cross_file'] += result.cross_file_mentions
            by_language[lang]['existence_ratios'].append(result.existence_ratio)
        
        # Calculate language averages
        by_language_stats = {}
        for lang, stats in by_language.items():
            avg_existence = sum(stats['existence_ratios']) / len(stats['existence_ratios'])
            by_language_stats[lang] = {
                'docstrings': stats['docstrings'],
                'mentions': stats['mentions'],
                'existing': stats['existing'],
                'cross_file': stats['cross_file'],
                'avg_existence_ratio': avg_existence
            }
        
        return SystemComparison(
            system_name=system_name,
            total_docstrings=total_docstrings,
            total_mentions=total_mentions,
            existing_mentions=existing_mentions,
            cross_file_mentions=cross_file_mentions,
            avg_existence_ratio=avg_existence_ratio,
            avg_hallucination_rate=avg_hallucination_rate,
            avg_mentions_per_doc=avg_mentions_per_doc,
            by_language=by_language_stats
        )
    
    def generate_comparative_report(
        self,
        all_results: Dict[str, Dict[str, TruthfulnessResult]],
        output_dir: Path
    ):
        """
        Generate comprehensive comparative report for all systems.
        
        Args:
            all_results: Dictionary mapping system_name to results
            output_dir: Directory to save reports
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Calculate statistics for each system
        system_stats = {}
        for system_name, results in all_results.items():
            system_stats[system_name] = self.calculate_system_stats(system_name, results)
        
        # Save detailed JSON results
        detailed_results = {}
        for system_name, results in all_results.items():
            detailed_results[system_name] = {
                comp_id: {
                    "component_id": result.component_id,
                    "file_path": result.file_path,
                    "language": result.language,
                    "total_mentions": result.total_mentions,
                    "existing_mentions": result.existing_mentions,
                    "cross_file_mentions": result.cross_file_mentions,
                    "hallucination_rate": result.hallucination_rate,
                    "existence_ratio": result.existence_ratio,
                    "mentioned_components": [
                        {
                            "name": cm.name,
                            "exists": cm.exists,
                            "is_cross_file": cm.is_cross_file,
                            "component_type": cm.component_type,
                            "file_path": cm.file_path
                        }
                        for cm in result.mentioned_components
                    ]
                }
                for comp_id, result in results.items()
            }
        
        json_output = output_dir / "docstring_truthfulness_evaluation.json"
        with open(json_output, 'w', encoding='utf-8') as f:
            json.dump(detailed_results, f, indent=2)
        
        logger.info(f"Saved detailed results to {json_output}")
        
        # Generate markdown report
        self._generate_markdown_report(system_stats, all_results, output_dir)
    
    def _generate_markdown_report(
        self,
        system_stats: Dict[str, SystemComparison],
        all_results: Dict[str, Dict[str, TruthfulnessResult]],
        output_dir: Path
    ):
        """Generate comparative markdown report"""
        
        report = "# Multi-System Docstring Truthfulness Evaluation Report\n\n"
        report += "**Evaluation of AI-Generated Docstrings from Five Different Systems**\n\n"
        report += "---\n\n"
        
        # System Comparison Table
        report += "## System Comparison Summary\n\n"
        report += "| System | Docstrings | Total Mentions | Existing | Cross-File | Existence Ratio | Hallucination Rate | Avg Mentions/Doc |\n"
        report += "|--------|-----------|---------------|----------|------------|-----------------|-------------------|------------------|\n"
        
        # Sort systems by existence ratio (best to worst)
        sorted_systems = sorted(
            system_stats.items(),
            key=lambda x: x[1].avg_existence_ratio,
            reverse=True
        )
        
        for system_name, stats in sorted_systems:
            report += f"| **{system_name}** | {stats.total_docstrings} | {stats.total_mentions} | "
            report += f"{stats.existing_mentions} | {stats.cross_file_mentions} | "
            report += f"**{stats.avg_existence_ratio:.2%}** | {stats.avg_hallucination_rate:.2%} | "
            report += f"{stats.avg_mentions_per_doc:.2f} |\n"
        
        # Ranking
        report += "\n## System Rankings\n\n"
        report += "### By Existence Ratio (Higher is Better)\n\n"
        for i, (system_name, stats) in enumerate(sorted_systems, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            report += f"{emoji} **{system_name}**: {stats.avg_existence_ratio:.2%} existence ratio\n"
        
        report += "\n### By Hallucination Rate (Lower is Better)\n\n"
        sorted_by_hallucination = sorted(
            system_stats.items(),
            key=lambda x: x[1].avg_hallucination_rate
        )
        for i, (system_name, stats) in enumerate(sorted_by_hallucination, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            report += f"{emoji} **{system_name}**: {stats.avg_hallucination_rate:.2%} hallucination rate\n"
        
        report += "\n### By Cross-File References (Higher is Better)\n\n"
        sorted_by_crossfile = sorted(
            system_stats.items(),
            key=lambda x: x[1].cross_file_mentions,
            reverse=True
        )
        for i, (system_name, stats) in enumerate(sorted_by_crossfile, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            report += f"{emoji} **{system_name}**: {stats.cross_file_mentions} cross-file references\n"
        
        # Language-specific breakdown
        report += "\n## Language-Specific Analysis\n\n"
        
        # Collect all languages
        all_languages = set()
        for stats in system_stats.values():
            all_languages.update(stats.by_language.keys())
        
        for language in sorted(all_languages):
            report += f"### {language.title()}\n\n"
            report += "| System | Docstrings | Mentions | Existing | Cross-File | Existence Ratio |\n"
            report += "|--------|-----------|----------|----------|------------|----------------|\n"
            
            for system_name, stats in sorted_systems:
                if language in stats.by_language:
                    lang_stats = stats.by_language[language]
                    report += f"| {system_name} | {lang_stats['docstrings']} | "
                    report += f"{lang_stats['mentions']} | {lang_stats['existing']} | "
                    report += f"{lang_stats['cross_file']} | "
                    report += f"{lang_stats['avg_existence_ratio']:.2%} |\n"
                else:
                    report += f"| {system_name} | - | - | - | - | - |\n"
            
            report += "\n"
        
        # Hallucination Examples
        report += "## Hallucination Examples by System\n\n"
        report += "*Components mentioned in docstrings that don't actually exist in the codebase*\n\n"
        
        for system_name, results in sorted(all_results.items()):
            hallucinations = []
            for comp_id, result in results.items():
                for cm in result.mentioned_components:
                    if not cm.exists:
                        hallucinations.append((comp_id, cm.name, result.language))
            
            report += f"### {system_name}\n\n"
            if hallucinations:
                report += f"Found **{len(hallucinations)}** hallucinated components.\n\n"
                report += "| Component ID | Language | Hallucinated Component |\n"
                report += "|-------------|----------|------------------------|\n"
                
                for comp_id, comp_name, language in hallucinations[:10]:  # Show first 10
                    report += f"| {comp_id} | {language} | `{comp_name}` |\n"
                
                if len(hallucinations) > 10:
                    report += f"\n*... and {len(hallucinations) - 10} more*\n"
            else:
                report += "✅ **No hallucinations detected!**\n"
            
            report += "\n"
        
        # Key Insights
        report += "## Key Insights\n\n"
        
        best_system = sorted_systems[0][0]
        best_ratio = sorted_systems[0][1].avg_existence_ratio
        worst_system = sorted_systems[-1][0]
        worst_ratio = sorted_systems[-1][1].avg_existence_ratio
        
        report += f"1. **Best Performing System**: {best_system} with {best_ratio:.2%} existence ratio\n"
        report += f"2. **Needs Improvement**: {worst_system} with {worst_ratio:.2%} existence ratio\n"
        report += f"3. **Performance Gap**: {(best_ratio - worst_ratio):.2%} difference between best and worst\n\n"
        
        # Cross-file awareness
        total_cross_file = sum(stats.cross_file_mentions for stats in system_stats.values())
        if total_cross_file > 0:
            best_crossfile_system = sorted_by_crossfile[0][0]
            report += f"4. **Best Cross-File Awareness**: {best_crossfile_system} demonstrates the best understanding of dependencies\n"
        
        report += "\n"
        report += "### Recommendations\n\n"
        report += "- Systems with **high existence ratios** (>80%) produce accurate, trustworthy docstrings\n"
        report += "- Systems with **low hallucination rates** (<20%) are more reliable for code documentation\n"
        report += "- **Cross-file references** indicate better contextual understanding of the codebase\n"
        report += "- Focus improvement efforts on systems with existence ratios below 60%\n"
        
        # Save report
        md_output = output_dir / "docstring_truthfulness_report.md"
        with open(md_output, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"Saved markdown report to {md_output}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Evaluate truthfulness across multiple docstring generation systems'
    )
    parser.add_argument(
        '--input',
        type=str,
        default='data/validation/completeness_evaluation_cleaned.json',
        help='Path to input JSON file containing docstrings from all systems'
    )
    parser.add_argument(
        '--navigator-dir',
        type=str,
        default='data/intermediate/navigator_output',
        help='Directory containing navigator output (dependency graph)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/validation/truthfulness',
        help='Directory to save evaluation results'
    )
    parser.add_argument(
        '--no-llm',
        action='store_true',
        default=False,
        help='Disable LLM and use regex-based extraction only (faster but less accurate)'
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    input_file = project_root / args.input
    navigator_dir = project_root / args.navigator_dir
    output_dir = project_root / args.output_dir
    
    print("=" * 70)
    print("Multi-System Docstring Truthfulness Evaluation")
    print("=" * 70)
    print(f"Input file: {input_file}")
    print(f"Navigator output: {navigator_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Using LLM: {not args.no_llm} (llama.cpp local model)")
    print("=" * 70)
    print()
    
    # Create evaluator
    evaluator = MultiSystemTruthfulnessEvaluator(
        input_file=str(input_file),
        navigator_output_dir=str(navigator_dir),
        use_llm=not args.no_llm,
        llm_mode="llama_cpp"  # Always use local model
    )
    
    # Run evaluation
    print("Starting multi-system evaluation...")
    all_results = evaluator.evaluate_all_systems()
    
    total_evaluated = sum(len(results) for results in all_results.values())
    print(f"\n✅ Evaluated {total_evaluated} docstrings across {len(all_results)} systems")
    
    # Generate comparative report
    print("\nGenerating comparative report...")
    evaluator.generate_comparative_report(all_results, output_dir)
    
    print(f"\n✅ Reports saved to {output_dir}")
    print("\nGenerated files:")
    print(f"  - docstring_truthfulness_evaluation.json (detailed results)")
    print(f"  - docstring_truthfulness_report.md (comparative analysis)")
    print("\n🎉 Evaluation complete!")


if __name__ == "__main__":
    main()
