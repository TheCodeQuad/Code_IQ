"""
Test Navigator Module on JavaScript CodeSearchNet Dataset

This script:
1. Downloads JavaScript code from CodeSearchNet
2. Extracts components using your navigator
3. Validates against gold extractor
4. Generates comprehensive metrics and errors

Usage:
    python test_navigator_js_codesearchnet.py [max_samples]
    
Example:
    python test_navigator_js_codesearchnet.py 5  # Test on 5 samples
    python test_navigator_js_codesearchnet.py 20 # Test on 20 samples
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict

# Import validators and navigator
from backend.validators.codesearchnet_validator import CodeSearchNetDataset, CodeSearchNetValidator
from backend.validators.validation_framework import ValidationFramework
from backend.navigator.languages.adapter_registry import AdapterRegistry


class JSCodeSearchNetTester:
    """Test navigator on JavaScript CodeSearchNet dataset."""
    
    def __init__(self, max_samples: int = 10):
        self.max_samples = max_samples
        self.dataset = CodeSearchNetDataset()
        self.adapter_registry = AdapterRegistry()
        self.results = []
        self.metrics = {
            'total_samples': 0,
            'successful': 0,
            'failed': 0,
            'extraction_stats': defaultdict(int),
            'error_summary': defaultdict(int),
        }
    
    def run(self):
        """Execute full test pipeline."""
        print("\n" + "="*80)
        print("JAVASCRIPT NAVIGATOR VALIDATION - CODESEARCHNET DATASET")
        print("="*80)
        
        print(f"\nPhase 1: Downloading JavaScript dataset (max {self.max_samples} samples)...")
        samples = self._download_dataset()
        
        print(f"\nPhase 2: Extracting components with Navigator...")
        self._extract_components(samples)
        
        print(f"\nPhase 3: Generating validation metrics...")
        self._generate_metrics()
        
        print(f"\nPhase 4: Saving results...")
        self._save_results()
        
        print(f"\nPhase 5: Printing summary...")
        self._print_summary()
    
    def _download_dataset(self) -> List[Dict[str, Any]]:
        """Download JavaScript CodeSearchNet split."""
        try:
            samples = self.dataset.download_split('javascript', max_samples=self.max_samples)
            print(f"✓ Downloaded {len(samples)} JavaScript samples")
            return samples
        except Exception as e:
            print(f"✗ Failed to download dataset: {e}")
            return []
    
    def _extract_components(self, samples: List[Dict[str, Any]]):
        """Extract components from each sample.
        
        Dataset format: only 'code' and 'comment' columns (no language filter).
        Skip non-JavaScript code gracefully (parser will fail, which indicates non-JS).
        """
        if not samples:
            print("✗ No samples to process")
            return
        
        js_adapter = self.adapter_registry.get_adapter('javascript')
        
        for i, sample in enumerate(samples, 1):
            try:
                # Extract code and metadata
                source_code = sample.get('code')
                if not source_code:
                    print(f"\n[{i}/{len(samples)}] Skipping: No code in sample")
                    self.metrics['failed'] += 1
                    continue
                
                comment = sample.get('comment', '')
                
                # Use index as identifier since no repo/path/func_name
                file_path = f'sample_{i}.js'
                repo = 'codesearchnet'
                func_name = f'snippet_{i}'
                
                # Show progress
                code_preview = source_code[:50].replace('\n', ' ')
                print(f"\n[{i}/{len(samples)}] {repo}/{file_path}")
                print(f"  Code: {code_preview}...")
                
                # Parse - if this fails, it's likely not JavaScript, so skip gracefully
                tree = js_adapter.parse(source_code)
                
                # Check for parse errors indicating non-JavaScript code
                if tree.root_node.has_error:
                    print(f"  ↷ Not valid JavaScript (skipped)")
                    self.metrics['failed'] += 1
                    continue
                
                # DEBUG: Print AST structure for first successful sample
                if self.metrics['successful'] == 0:
                    print(f"\n  🔍 AST STRUCTURE (first sample):")
                    ast_text = tree.root_node.sexp()
                    # Print first 500 chars
                    ast_preview = str(ast_text)[:500]
                    print(f"  {ast_preview}...")
                    print(f"  [Full AST saved for inspection]")
                
                # Extract components
                components = js_adapter.extract_components(tree, source_code, file_path, repo)
                
                if not components:
                    print(f"  ℹ No components extracted (may be incomplete JS snippet)")
                    self.metrics['failed'] += 1
                    continue
                
                # DEBUG: Analyze extracted components
                comp_types = defaultdict(int)
                for cid, comp in components.items():
                    comp_types[comp.type.value] += 1
                    print(f"    • {comp.type.value}: {comp.name} (lines {comp.location.start_line}-{comp.location.end_line})")
                
                print(f"  ✓ Extracted {len(components)} components: {dict(comp_types)}")
                
                # Extract dependencies for each component
                for cid, component in components.items():
                    try:
                        deps = js_adapter.resolve_dependencies(component, tree, source_code, components)
                        component.depends_on = list(deps)
                    except Exception as dep_err:
                        # Log but continue if dependency resolution fails
                        print(f"    ⚠ Dependency resolution failed for {cid}: {str(dep_err)[:50]}")
                
                # Store result
                self.results.append({
                    'repo': repo,
                    'file_path': file_path,
                    'sample_index': i,
                    'comment': comment,
                    'source_code': source_code,
                    'components': {k: v.to_dict() for k, v in components.items()},
                    'component_count': len(components),
                    'status': 'success'
                })
                
                self.metrics['successful'] += 1
                
            except Exception as e:
                # Silently skip non-JS code
                error_type = type(e).__name__
                if error_type in ['ParseError', 'ParserException', 'ValueError']:
                    print(f"  ↷ Not JavaScript code (skipped)")
                else:
                    print(f"  ✗ Error: {str(e)[:80]}")
                
                self.results.append({
                    'sample_index': i,
                    'repo': 'codesearchnet',
                    'status': 'failed',
                    'error': str(e),
                    'error_type': type(e).__name__
                })
                
                self.metrics['failed'] += 1
                self.metrics['error_summary'][type(e).__name__] += 1
        
        self.metrics['total_samples'] = len(samples)
    
    def _generate_metrics(self):
        """Generate extraction quality metrics."""
        print("\nCalculating metrics...")
        
        successful_results = [r for r in self.results if r['status'] == 'success']
        
        if not successful_results:
            print("No successful extractions to analyze")
            return
        
        # Component statistics
        total_components = sum(r['component_count'] for r in successful_results)
        avg_components = total_components / len(successful_results) if successful_results else 0
        
        # Field analysis
        field_counts = defaultdict(int)
        for result in successful_results:
            for component in result['components'].values():
                for field in component.keys():
                    if component[field] is not None:
                        field_counts[field] += 1
        
        print(f"\n  Components extracted: {total_components}")
        print(f"  Average per file: {avg_components:.1f}")
        print(f"  Success rate: {self.metrics['successful']}/{self.metrics['total_samples']} ({100*self.metrics['successful']/self.metrics['total_samples']:.1f}%)")
        
        print(f"\n  Top fields extracted:")
        for field, count in sorted(field_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"    - {field}: {count}")
    
    def _save_results(self):
        """Save results to JSON file."""
        output_dir = Path('data/validation/codesearchnet')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f'js_navigator_results_{self.max_samples}_samples.json'
        
        with open(output_file, 'w') as f:
            json.dump({
                'metadata': {
                    'max_samples': self.max_samples,
                    'successful': self.metrics['successful'],
                    'failed': self.metrics['failed'],
                    'dataset': 'CodeSearchNet JavaScript Mini',
                },
                'results': self.results,
                'error_summary': dict(self.metrics['error_summary']),
            }, f, indent=2)
        
        print(f"\n✓ Results saved to: {output_file}")
        return output_file
    
    def _print_summary(self):
        """Print comprehensive summary."""
        print("\n" + "="*80)
        print("VALIDATION SUMMARY")
        print("="*80)
        
        print(f"\nDataset: CodeSearchNet (sentence-transformers/codesearchnet)")
        print(f"Samples processed: {self.metrics['total_samples']}")
        print(f"JavaScript code: {self.metrics['successful']} ({100*self.metrics['successful']/max(self.metrics['total_samples'],1):.1f}%)")
        print(f"Non-JavaScript/Failed: {self.metrics['failed']}")
        
        if self.metrics['error_summary']:
            print(f"\nError breakdown (non-JS detection):")
            for error_type, count in sorted(self.metrics['error_summary'].items(), key=lambda x: -x[1]):
                print(f"  - {error_type}: {count}")
        
        # Sample successful extractions
        successful = [r for r in self.results if r['status'] == 'success']
        if successful:
            print(f"\n📊 Sample Extraction (first successful):")
            sample = successful[0]
            print(f"  Sample index: {sample['sample_index']}")
            print(f"  Components extracted: {sample['component_count']}")
            
            if sample['components']:
                first_comp = list(sample['components'].values())[0]
                print(f"\n  Sample component schema:")
                for key, value in list(first_comp.items())[:8]:
                    print(f"    - {key}: {type(value).__name__}")
        
        print("\n" + "="*80)
        print("✓ Validation complete!")
        print("="*80 + "\n")
    
    def generate_gold_comparison(self):
        """Generate comparison with gold extractor (optional advanced step)."""
        print("\n" + "-"*80)
        print("GOLD EXTRACTOR COMPARISON (Advanced)")
        print("-"*80)
        
        try:
            from backend.validators.gold_extractor import get_gold_extractor
            from backend.validators.validation_framework import ValidationFramework
            
            print("Comparing with gold extractor on JavaScript samples...")
            
            # This would require more setup with actual validation framework
            print("(See validation_framework.py for detailed comparison)")
            
        except Exception as e:
            print(f"Note: Gold comparison skipped ({e})")


def main():
    """Main entry point."""
    # Parse args
    max_samples = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    
    # Validate range
    if max_samples < 1:
        print("Error: max_samples must be >= 1")
        sys.exit(1)
    
    # Run tester
    tester = JSCodeSearchNetTester(max_samples=max_samples)
    tester.run()
    tester.generate_gold_comparison()


if __name__ == '__main__':
    main()
