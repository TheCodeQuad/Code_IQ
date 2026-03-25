"""
Multi-System Docstring Truthfulness Evaluator

Evaluates and compares the truthfulness of AI-generated docstrings from multiple systems.

Workflow:
1. Load docstrings data from input file (contains multiple systems)
2. For each docstring from each system, extract mentioned components
3. Check if extracted components actually exist in the repository dependency graph
4. Calculate statistics: existence ratio, cross-file references, hallucination rate
5. Generate comparative report comparing all systems

Features:
- Per-system evaluation with aggregated statistics
- Component extraction via LLM with regex fallback
- Cross-file reference detection
- Hallucination detection
- Comprehensive comparative reporting
- Language and repository breakdowns

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

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.utils.logger import get_logger
from backend.evaluator.truthfulness_comprehensive import (
    ComprehensiveTruthfulnessEvaluator,
    DocstringEvaluationResult,
    SystemEvaluationStats
)

logger = get_logger(__name__)


class MultiSystemTruthfulnessEvaluator:
    """
    Evaluates truthfulness across multiple docstring generation systems.
    
    This class orchestrates the evaluation of docstrings from different systems,
    providing comparative analysis and detailed statistics.
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
            input_file: Path to input file with docstrings from all systems
            navigator_output_dir: Directory containing navigator output (dependency graphs)
            use_llm: Whether to use LLM for component extraction
            llm_mode: Which LLM to use ("llama_cpp" or "gemini")
        """
        self.input_file = Path(input_file)
        self.navigator_output_dir = Path(navigator_output_dir)
        
        # Initialize comprehensive truthfulness evaluator
        self.evaluator = ComprehensiveTruthfulnessEvaluator(
            navigator_output_dir=str(navigator_output_dir),
            use_llm=use_llm,
            llm_mode=llm_mode,
            cache_graphs=True
        )
        
        logger.info(f"Initialized ComprehensiveTruthfulnessEvaluator")
    
    def load_multi_system_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load docstrings from multiple systems.
        
        Handles multiple input formats:
        - system_1, system_2, etc. keys
        - 'system' field in each component
        - Direct list of components
        
        Returns:
            Dictionary mapping system_name to list of component data
        """
        if not self.input_file.exists():
            raise FileNotFoundError(f"Input file not found: {self.input_file}")
        
        with open(self.input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        systems_data = {}
        
        if isinstance(data, dict):
            # Check if it has system_1, system_2, etc.
            system_keys = sorted([k for k in data.keys() if k.startswith('system_')])
            
            if system_keys:
                # Direct system mapping
                for system_key in system_keys:
                    systems_data[system_key] = data[system_key]
            else:
                # Try to find components with system indicators
                by_system = defaultdict(list)
                components = data.get('components', [])
                
                if components:
                    for comp in components:
                        system = comp.get('system', 'default_system')
                        by_system[system].append(comp)
                else:
                    # Assume whole dict is components grouped by key
                    for key, value in data.items():
                        if isinstance(value, list):
                            by_system[key] = value
                        elif isinstance(value, dict):
                            by_system[key] = [value]
                
                systems_data = dict(by_system)
        
        elif isinstance(data, list):
            # List of components, group by system field
            by_system = defaultdict(list)
            for comp in data:
                if isinstance(comp, dict):
                    system = comp.get('system', 'default_system')
                    by_system[system].append(comp)
            systems_data = dict(by_system)
        
        if not systems_data:
            logger.warning("No systems found in input data")
            systems_data['default_system'] = [data] if isinstance(data, dict) else []
        
        logger.info(f"Loaded data for {len(systems_data)} systems:")
        for system, components in systems_data.items():
            logger.info(f"  - {system}: {len(components)} components")
        
        return systems_data
    
    def evaluate_system(
        self,
        system_name: str,
        components: List[Dict[str, Any]]
    ) -> List[DocstringEvaluationResult]:
        """
        Evaluate all docstrings from a single system.
        
        Args:
            system_name: Name of the system being evaluated
            components: List of component dictionaries with docstrings
            
        Returns:
            List of DocstringEvaluationResult objects
        """
        results = []
        
        logger.info(f"Evaluating {system_name} ({len(components)} components)...")
        
        for comp_data in tqdm(components, desc=f"Evaluating {system_name}", leave=False):
            try:
                # Extract necessary fields
                component_id = comp_data.get('id', comp_data.get('component_id', 'unknown'))
                docstring = comp_data.get('docstring', comp_data.get('generated_docstring', ''))
                language = comp_data.get('language', 'python')
                file_path = comp_data.get('file_path', '')
                repository = comp_data.get('repository', comp_data.get('repo', 'unknown'))
                
                # Handle location field
                if not file_path and 'location' in comp_data:
                    location = comp_data['location']
                    if isinstance(location, dict):
                        file_path = location.get('file_path', '')
                
                if not docstring or not docstring.strip():
                    logger.debug(f"Skipping {component_id} - empty docstring")
                    continue
                
                # Evaluate this docstring
                result = self.evaluator.evaluate_docstring(
                    component_id=component_id,
                    docstring=docstring,
                    file_path=file_path,
                    repository_name=repository,
                    language=language
                )
                
                results.append(result)
            
            except Exception as e:
                logger.error(f"Error evaluating {comp_data.get('component_id', 'unknown')}: {e}")
        
        return results
    
    def evaluate_all_systems(self) -> Dict[str, List[DocstringEvaluationResult]]:
        """
        Evaluate all systems.
        
        Returns:
            Dictionary mapping system_name to list of evaluation results
        """
        systems_data = self.load_multi_system_data()
        all_results = {}
        
        for system_name, components in systems_data.items():
            if not components:
                logger.warning(f"System '{system_name}' has no components")
                continue
            
            results = self.evaluate_system(system_name, components)
            all_results[system_name] = results
        
        return all_results
    
    def calculate_system_stats(
        self,
        system_name: str,
        results: List[DocstringEvaluationResult]
    ) -> SystemEvaluationStats:
        """Calculate aggregate statistics for a system"""
        
        if not results:
            return SystemEvaluationStats(system_name=system_name)
        
        # Use the evaluator's built-in summary generation
        summary = self.evaluator.generate_summary_report(results)
        summary.system_name = system_name
        
        return summary
    
    def generate_comparative_report(
        self,
        all_results: Dict[str, List[DocstringEvaluationResult]],
        output_dir: Path
    ):
        """
        Generate comprehensive comparative report for all systems.
        
        Args:
            all_results: Dictionary mapping system_name to list of results
            output_dir: Directory to save reports
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Calculate statistics for each system
        system_stats = {}
        for system_name, results in all_results.items():
            system_stats[system_name] = self.calculate_system_stats(system_name, results)
        
        # Save detailed JSON results
        self._save_detailed_results(all_results, output_dir)
        
        # Generate markdown report
        self._generate_markdown_report(system_stats, all_results, output_dir)
        
        logger.info("Comparative report generation complete")
    
    def _save_detailed_results(
        self,
        all_results: Dict[str, List[DocstringEvaluationResult]],
        output_dir: Path
    ):
        """Save detailed results as JSON"""
        
        detailed_results = {}
        
        for system_name, results in all_results.items():
            detailed_results[system_name] = []
            
            for result in results:
                detailed_results[system_name].append({
                    "component_id": result.component_id,
                    "repository": result.repository,
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
                            "file_path": cm.file_path,
                            "repository": cm.repository
                        }
                        for cm in result.mentioned_components
                    ]
                })
        
        json_output = output_dir / "truthfulness_detailed_results.json"
        with open(json_output, 'w', encoding='utf-8') as f:
            json.dump(detailed_results, f, indent=2)
        
        logger.info(f"Saved detailed results to {json_output}")
    
    def _generate_markdown_report(
        self,
        system_stats: Dict[str, SystemEvaluationStats],
        all_results: Dict[str, List[DocstringEvaluationResult]],
        output_dir: Path
    ):
        """Generate comprehensive markdown report"""
        
        report = "# Multi-System Docstring Truthfulness Evaluation Report\n\n"
        report += "**Comprehensive evaluation of AI-generated docstrings across multiple systems**\n\n"
        report += "---\n\n"
        
        # Sort systems by existence ratio (best to worst)
        sorted_systems = sorted(
            system_stats.items(),
            key=lambda x: x[1].avg_existence_ratio,
            reverse=True
        )
        
        # System Comparison Table
        report += "## System Comparison Summary\n\n"
        report += "| Rank | System | Docstrings | Mentions | Existing | Cross-File | Existence Ratio | Hallucination Rate | Avg/Doc |\n"
        report += "|------|--------|-----------|----------|----------|------------|-----------------|-------------------|----------|\n"
        
        for rank, (system_name, stats) in enumerate(sorted_systems, 1):
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
            report += f"| {medal} | **{system_name}** | {stats.total_docstrings_analyzed} | "
            report += f"{stats.total_components_mentioned} | {stats.existing_components} | "
            report += f"{stats.cross_file_mentions} | **{stats.avg_existence_ratio:.1%}** | "
            report += f"{stats.avg_hallucination_rate:.1%} | {stats.avg_mentions_per_doc:.2f} |\n"
        
        # Key Metrics Explanation
        report += "\n## Metrics Definition\n\n"
        report += "- **Existence Ratio**: % of mentioned components that exist in codebase (higher = better)\n"
        report += "- **Hallucination Rate**: % of mentioned components that don't exist (lower = better)\n"
        report += "- **Cross-File References**: Count of dependencies from other files (higher = better context awareness)\n"
        report += "- **Avg/Doc**: Average component mentions per docstring (richness metric)\n\n"
        
        # Rankings
        report += "## Rankings\n\n"
        
        report += "### 🎯 By Existence Ratio (Lower Hallucination)\n\n"
        for i, (system_name, stats) in enumerate(sorted_systems, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "   "
            report += f"{medal} {i}. **{system_name}**: {stats.avg_existence_ratio:.1%} ({stats.existing_components}/{stats.total_components_mentioned})\n"
        
        sorted_by_hallucination = sorted(system_stats.items(), key=lambda x: x[1].avg_hallucination_rate)
        report += "\n### 🚨 By Hallucination Rate\n\n"
        for i, (system_name, stats) in enumerate(sorted_by_hallucination, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "   "
            report += f"{medal} {i}. **{system_name}**: {stats.avg_hallucination_rate:.1%} hallucinations\n"
        
        sorted_by_crossfile = sorted(system_stats.items(), key=lambda x: x[1].cross_file_mentions, reverse=True)
        report += "\n### 🔗 By Cross-File Awareness\n\n"
        for i, (system_name, stats) in enumerate(sorted_by_crossfile, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "   "
            report += f"{medal} {i}. **{system_name}**: {stats.cross_file_mentions} cross-file references\n"
        
        sorted_by_richness = sorted(system_stats.items(), key=lambda x: x[1].avg_mentions_per_doc, reverse=True)
        report += "\n### 📚 By Documentation Richness\n\n"
        for i, (system_name, stats) in enumerate(sorted_by_richness, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "   "
            report += f"{medal} {i}. **{system_name}**: {stats.avg_mentions_per_doc:.2f} mentions/docstring\n"
        
        # Language Breakdown
        report += "\n## Language-Specific Analysis\n\n"
        
        all_languages = set()
        for stats in system_stats.values():
            all_languages.update(stats.by_language.keys())
        
        for language in sorted(all_languages):
            report += f"### {language.title()}\n\n"
            report += "| System | Docstrings | Mentions | Existing | Existence Ratio |\n"
            report += "|--------|-----------|----------|----------|----------------|\n"
            
            for system_name, stats in sorted_systems:
                if language in stats.by_language:
                    lang_stats = stats.by_language[language]
                    report += f"| {system_name} | {lang_stats['docstrings']} | "
                    report += f"{lang_stats['mentions']} | {lang_stats['existing']} | "
                    report += f"{lang_stats['avg_existence_ratio']:.1%} |\n"
                else:
                    report += f"| {system_name} | - | - | - | - |\n"
            
            report += "\n"
        
        # Hallucination Analysis
        report += "## Hallucination Analysis\n\n"
        
        for system_name, results in sorted(all_results.items()):
            hallucinations = []
            for result in results:
                for cm in result.mentioned_components:
                    if not cm.exists:
                        hallucinations.append((result.component_id, cm.name, result.language))
            
            report += f"### {system_name}\n\n"
            
            if hallucinations:
                report += f"**{len(hallucinations)}** hallucinated component references found.\n\n"
                report += "| Component | Language | Hallucinated Reference |\n"
                report += "|-----------|----------|------------------------|\n"
                
                for comp_id, comp_name, lang in hallucinations[:15]:
                    report += f"| {comp_id} | {lang} | `{comp_name}` |\n"
                
                if len(hallucinations) > 15:
                    report += f"\n*... and {len(hallucinations) - 15} more hallucinations*\n"
            else:
                report += "✅ **No hallucinations detected!**\n"
            
            report += "\n"
        
        # Cross-File References
        report += "## Cross-File Reference Analysis\n\n"
        report += "Components referenced from different files indicate understanding of codebase structure.\n\n"
        
        for system_name, results in sorted(all_results.items()):
            cross_file_refs = []
            for result in results:
                for cm in result.mentioned_components:
                    if cm.is_cross_file and cm.exists:
                        cross_file_refs.append((result.component_id, cm.name, cm.file_path))
            
            report += f"### {system_name}\n\n"
            
            if cross_file_refs:
                report += f"**{len(cross_file_refs)}** cross-file references found.\n\n"
                report += "| Component | Reference | Source File |\n"
                report += "|-----------|-----------|-------------|\n"
                
                for comp_id, ref_name, file_path in cross_file_refs[:12]:
                    file_display = Path(file_path).name if file_path else "Unknown"
                    report += f"| {comp_id} | `{ref_name}` | {file_display} |\n"
                
                if len(cross_file_refs) > 12:
                    report += f"\n*... and {len(cross_file_refs) - 12} more*\n"
            else:
                report += "No cross-file references found.\n"
            
            report += "\n"
        
        # Key Insights  
        report += "## Key Insights & Recommendations\n\n"
        
        best_system = sorted_systems[0]
        worst_system = sorted_systems[-1]
        gap = best_system[1].avg_existence_ratio - worst_system[1].avg_existence_ratio
        
        report += f"1. **Top Performer**: {best_system[0]} achieves {best_system[1].avg_existence_ratio:.1%} existence ratio\n"
        report += f"2. **Needs Work**: {worst_system[0]} has {worst_system[1].avg_existence_ratio:.1%} existence ratio\n"
        report += f"3. **Performance Gap**: {gap:.1%} difference between best and worst systems\n\n"
        
        report += "### Recommendations\n\n"
        report += "- **Existence Ratio > 80%**: System produces highly accurate, trustworthy docstrings\n"
        report += "- **Hallucination Rate < 20%**: System is reliable for code documentation\n"
        report += "- **Cross-File References**: Indicates understanding of codebase dependencies\n"
        report += "- **Priority**: Improve systems with existence ratios below 60%\n"
        
        # Save report
        md_output = output_dir / "truthfulness_comparative_report.md"
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
        help='Path to input JSON file with docstrings from all systems'
    )
    parser.add_argument(
        '--navigator-dir',
        type=str,
        default='data/intermediate/navigator_output',
        help='Directory with navigator output (dependency graphs)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/validation/truthfulness',
        help='Directory to save results'
    )
    parser.add_argument(
        '--no-llm',
        action='store_true',
        help='Use regex-based extraction only (faster but less accurate)'
    )
    
    args = parser.parse_args()
    
    if not args.input:
        parser.error('--input is required')
    
    # Resolve paths
    input_file = Path(args.input) if Path(args.input).is_absolute() else project_root / args.input
    navigator_dir = Path(args.navigator_dir) if Path(args.navigator_dir).is_absolute() else project_root / args.navigator_dir
    output_dir = Path(args.output_dir) if Path(args.output_dir).is_absolute() else project_root / args.output_dir
    
    print("=" * 80)
    print("Multi-System Docstring Truthfulness Evaluation")
    print("=" * 80)
    print(f"Input file:      {input_file}")
    print(f"Navigator dir:   {navigator_dir}")
    print(f"Output dir:      {output_dir}")
    print(f"Using LLM:       {'No (regex only)' if args.no_llm else 'Yes (llama.cpp)'}")
    print("=" * 80)
    print()
    
    # Create evaluator
    evaluator = MultiSystemTruthfulnessEvaluator(
        input_file=str(input_file),
        navigator_output_dir=str(navigator_dir),
        use_llm=not args.no_llm,
        llm_mode="llama_cpp"
    )
    
    # Run evaluation
    print("Starting multi-system evaluation...")
    all_results = evaluator.evaluate_all_systems()
    
    total_evaluated = sum(len(results) for results in all_results.values())
    print(f"✅ Evaluated {total_evaluated} docstrings across {len(all_results)} systems")
    
    # Generate comparative report
    print("\nGenerating comparative reports...")
    evaluator.generate_comparative_report(all_results, output_dir)
    
    print(f"\n✅ Reports saved to {output_dir}")
    print("\nGenerated files:")
    print(f"  - truthfulness_detailed_results.json (detailed per-docstring results)")
    print(f"  - truthfulness_comparative_report.md (comparative analysis and rankings)")
    print("\n🎉 Evaluation complete!")


if __name__ == "__main__":
    main()
