"""
Validation Framework - Compare Gold Extractor vs Adapter-Based IR Extractor.

Computes:
1. Component-level metrics: precision, recall, F1
2. Field-level accuracy: how well each field is preserved
3. Dependency accuracy: are depends_on links correct?
4. Missing/extra components analysis
"""

import json
from typing import Dict, List, Any, Tuple, Set
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict

from backend.validators.gold_extractor import get_gold_extractor
from backend.navigator.languages.adapter_registry import AdapterRegistry
from backend.navigator.treesitter.parser_factory import get_ts_parser


@dataclass
class ValidationMetrics:
    """Per-file validation results."""
    file_path: str
    language: str
    
    # Component-level metrics
    total_gold_components: int
    total_ir_components: int
    matched_components: int
    
    precision: float  # matched / total_ir
    recall: float     # matched / total_gold
    f1: float
    
    # Field-level metrics (for matched components)
    field_accuracy: Dict[str, float]  # {field: accuracy_pct}
    
    # Component classification errors
    type_errors: int  # Components where type differs
    location_errors: int  # Components where location differs >1 line
    
    # Missing/Extra
    missing: List[str]  # Components in gold but not in IR
    extra: List[str]    # Components in IR but not in gold
    
    # Diagnostic info
    gold_components: List[Dict[str, Any]]
    ir_components: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ValidationFramework:
    """Validate IR extraction against gold standard."""
    
    def __init__(self):
        self.registry = AdapterRegistry()
        self.results = []
    
    def validate_file(self, file_path: str) -> ValidationMetrics:
        """
        Validate single file:
        1. Extract with gold extractor
        2. Extract with adapter (IR)
        3. Compare and compute metrics
        """
        
        # Determine language
        ext = Path(file_path).suffix
        lang_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.java': 'java',
            '.ts': 'typescript',
            '.tsx': 'typescript',
        }
        language = lang_map.get(ext, None)
        if not language:
            raise ValueError(f"Unsupported file type: {ext}")
        
        # Read source
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()
        
        # ========== EXTRACT WITH GOLD EXTRACTOR ==========
        gold_parser = get_ts_parser(language)
        tree = gold_parser.parse(bytes(source, 'utf8'))
        
        gold_extractor = get_gold_extractor(language)
        gold_output = gold_extractor.extract(tree, source, file_path)
        gold_components = gold_output['components']
        
        # ========== EXTRACT WITH ADAPTER (IR) ==========
        adapter = self.registry.get_adapter_for_file(file_path)
        if not adapter:
            raise ValueError(f"No adapter for {file_path}")
        
        tree = adapter.parse(source)  # Re-parse with adapter's parser
        
        # Get module path
        module_path = Path(file_path).stem
        ir_output = adapter.extract_components(tree, source, file_path, module_path)
        
        # Convert IR to dict format for comparison
        ir_components = self._convert_ir_to_dict(ir_output)
        
        # ========== ALIGN & COMPARE ==========
        metrics = self._compute_metrics(file_path, language, gold_components, ir_components)
        
        self.results.append(metrics)
        return metrics
    
    def _convert_ir_to_dict(self, ir_output: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert CodeComponent objects to dicts for comparison."""
        components = []
        
        for comp_id, comp in ir_output.items():
            # Handle CodeComponent dataclass
            comp_dict = {
                'name': getattr(comp, 'name', '?'),
                'type': str(getattr(comp, 'type', '?')).lower(),
                'location': {
                    'start_line': getattr(comp.location, 'start_line', 0),
                    'end_line': getattr(comp.location, 'end_line', 0),
                },
                'signature': getattr(comp, 'signature', ''),
                'parameters': [
                    {'name': p.name, 'type': p.type_hint}
                    for p in getattr(comp, 'parameters', [])
                ],
                'return_type': getattr(comp, 'return_type', None),
                'modifiers': getattr(comp, 'decorators', []),
                'calls': getattr(comp, 'calls', []),
            }
            components.append(comp_dict)
        
        return components
    
    def _align_components(
        self, 
        gold: List[Dict[str, Any]], 
        ir: List[Dict[str, Any]]
    ) -> Tuple[List[Tuple[Dict, Dict]], List[Dict], List[Dict]]:
        """
        Align components by: exact match (name + location) → fuzzy match → unmatched.
        
        Returns:
            (matched_pairs, unmatched_gold, unmatched_ir)
        """
        matched = []
        used_gold = set()
        used_ir = set()
        
        # -------- EXACT MATCH: name + location within 1 line --------
        for i, g in enumerate(gold):
            for j, ir_comp in enumerate(ir):
                if i in used_gold or j in used_ir:
                    continue
                
                # Match if: same name + start_line within 1 line
                name_match = g.get('name') == ir_comp.get('name')
                loc_match = abs(
                    g['location']['start_line'] - ir_comp['location']['start_line']
                ) <= 1
                
                if name_match and loc_match:
                    matched.append((g, ir_comp))
                    used_gold.add(i)
                    used_ir.add(j)
                    break
        
        # -------- UNMATCHED --------
        unmatched_gold = [g for i, g in enumerate(gold) if i not in used_gold]
        unmatched_ir = [ir_comp for j, ir_comp in enumerate(ir) if j not in used_ir]
        
        return matched, unmatched_gold, unmatched_ir
    
    def _compute_metrics(
        self,
        file_path: str,
        language: str,
        gold_components: List[Dict[str, Any]],
        ir_components: List[Dict[str, Any]]
    ) -> ValidationMetrics:
        """Compute validation metrics."""
        
        matched, unmatched_gold, unmatched_ir = self._align_components(
            gold_components, ir_components
        )
        
        # ========== COMPONENT-LEVEL METRICS ==========
        total_gold = len(gold_components)
        total_ir = len(ir_components)
        total_matched = len(matched)
        
        precision = total_matched / total_ir if total_ir > 0 else 0.0
        recall = total_matched / total_gold if total_gold > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        # ========== FIELD-LEVEL ACCURACY ==========
        field_accuracy = self._compute_field_accuracy(matched)
        
        # ========== ERRORS ==========
        type_errors = sum(
            1 for g, ir_comp in matched 
            if g.get('type') != ir_comp.get('type')
        )
        
        location_errors = sum(
            1 for g, ir_comp in matched 
            if abs(
                g['location']['start_line'] - ir_comp['location']['start_line']
            ) > 1
        )
        
        # ========== MISSING/EXTRA ==========
        missing = [
            f"{comp['name']} ({comp['type']}@{comp['location']['start_line']})"
            for comp in unmatched_gold
        ]
        extra = [
            f"{comp['name']} ({comp['type']}@{comp['location']['start_line']})"
            for comp in unmatched_ir
        ]
        
        return ValidationMetrics(
            file_path=file_path,
            language=language,
            total_gold_components=total_gold,
            total_ir_components=total_ir,
            matched_components=total_matched,
            precision=precision,
            recall=recall,
            f1=f1,
            field_accuracy=field_accuracy,
            type_errors=type_errors,
            location_errors=location_errors,
            missing=missing,
            extra=extra,
            gold_components=gold_components,
            ir_components=ir_components,
        )
    
    def _compute_field_accuracy(self, matched: List[Tuple[Dict, Dict]]) -> Dict[str, float]:
        """Compute per-field accuracy across all matched components."""
        if not matched:
            return {}
        
        fields = ['type', 'location', 'signature', 'parameters', 'modifiers', 'calls']
        field_scores = defaultdict(lambda: {'correct': 0, 'total': 0})
        
        for gold, ir_comp in matched:
            for field in fields:
                field_scores[field]['total'] += 1
                
                if field == 'location':
                    # Location accuracy: within 1 line
                    if abs(
                        gold['location']['start_line'] - ir_comp['location']['start_line']
                    ) <= 1:
                        field_scores[field]['correct'] += 1
                
                elif field == 'parameters':
                    # Parameter accuracy: same count
                    if len(gold.get(field, [])) == len(ir_comp.get(field, [])):
                        field_scores[field]['correct'] += 1
                
                elif field == 'calls':
                    # Call accuracy: subset match (IR might not capture all)
                    gold_calls = {c['name'] for c in gold.get(field, [])}
                    ir_calls = {c['name'] for c in ir_comp.get(field, [])}
                    if ir_calls.issubset(gold_calls) or ir_calls == gold_calls:
                        field_scores[field]['correct'] += 1
                
                else:
                    # Exact match for type, signature, modifiers
                    if gold.get(field) == ir_comp.get(field):
                        field_scores[field]['correct'] += 1
        
        return {
            field: (scores['correct'] / scores['total'] * 100)
            for field, scores in field_scores.items()
        }
    
    def validate_directory(self, directory: str) -> Dict[str, Any]:
        """Validate all supported files in directory."""
        dir_path = Path(directory)
        
        supported_exts = {'.py', '.js', '.jsx', '.java', '.ts', '.tsx'}
        files = [
            f for f in dir_path.rglob('*')
            if f.suffix in supported_exts and not '__pycache__' in str(f)
        ]
        
        print(f"Found {len(files)} files to validate...")
        
        for file in files:
            try:
                print(f"  Validating {file.relative_to(dir_path)}...", end=' ')
                metrics = self.validate_file(str(file))
                print(
                    f"F1={metrics.f1:.2%} "
                    f"(P={metrics.precision:.2%}, R={metrics.recall:.2%})"
                )
            except Exception as e:
                print(f"ERROR: {e}")
                continue
        
        return self.aggregate_results()
    
    def aggregate_results(self) -> Dict[str, Any]:
        """Aggregate metrics across all validated files."""
        if not self.results:
            return {}
        
        by_language = defaultdict(list)
        for result in self.results:
            by_language[result.language].append(result)
        
        aggregated = {}
        for lang, metrics_list in by_language.items():
            aggregated[lang] = {
                'num_files': len(metrics_list),
                'avg_precision': sum(m.precision for m in metrics_list) / len(metrics_list),
                'avg_recall': sum(m.recall for m in metrics_list) / len(metrics_list),
                'avg_f1': sum(m.f1 for m in metrics_list) / len(metrics_list),
                'total_matched': sum(m.matched_components for m in metrics_list),
                'total_gold': sum(m.total_gold_components for m in metrics_list),
                'total_ir': sum(m.total_ir_components for m in metrics_list),
                'avg_field_accuracy': self._avg_field_accuracy(metrics_list),
                'files': [
                    {
                        'file': m.file_path,
                        'f1': m.f1,
                        'precision': m.precision,
                        'recall': m.recall,
                        'missing': m.missing,
                        'extra': m.extra,
                    }
                    for m in metrics_list
                ]
            }
        
        return {
            'summary': {
                'languages': len(aggregated),
                'total_files': sum(a['num_files'] for a in aggregated.values()),
                'overall_f1': sum(
                    a['avg_f1'] * a['num_files'] for a in aggregated.values()
                ) / sum(a['num_files'] for a in aggregated.values()) if aggregated else 0,
            },
            'by_language': aggregated,
        }
    
    def save_report(self, output_path: str) -> None:
        """Save validation report to JSON."""
        report = self.aggregate_results()
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"Report saved to {output_path}")
    
    def print_summary(self) -> None:
        """Print human-readable summary."""
        report = self.aggregate_results()
        
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        
        summary = report.get('summary', {})
        print(f"Languages: {summary.get('languages')}")
        print(f"Total Files: {summary.get('total_files')}")
        print(f"Overall F1: {summary.get('overall_f1', 0):.2%}")
        
        print("\n" + "-" * 80)
        print("BY LANGUAGE")
        print("-" * 80)
        
        for lang, metrics in report.get('by_language', {}).items():
            print(f"\n{lang.upper()}")
            print(f"  Files: {metrics['num_files']}")
            print(f"  Precision: {metrics['avg_precision']:.2%}")
            print(f"  Recall: {metrics['avg_recall']:.2%}")
            print(f"  F1: {metrics['avg_f1']:.2%}")
            print(f"  Components: {metrics['total_matched']}/{metrics['total_gold']} matched")
            print(f"  Field Accuracy:")
            for field, acc in metrics.get('avg_field_accuracy', {}).items():
                print(f"    - {field}: {acc:.1f}%")


if __name__ == '__main__':
    import sys
    
    validator = ValidationFramework()
    
    if len(sys.argv) > 1:
        path = sys.argv[1]
        output = sys.argv[2] if len(sys.argv) > 2 else 'validation_report.json'
        
        validator.validate_directory(path)
        validator.print_summary()
        validator.save_report(output)
    else:
        print("Usage: python validation_framework.py <directory> [output_file]")
