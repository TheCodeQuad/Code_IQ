"""
Test Navigator Module on Python CodeSearchNet Dataset

This script:
1. Downloads Python code from sentence-transformers/codesearchnet
2. Extracts components using your navigator
3. Validates extraction quality
4. Generates comprehensive metrics and errors

Usage:
    python test_navigator_python_codesearchnet.py [max_samples]
    
Example:
    python test_navigator_python_codesearchnet.py 5  # Test on 5 samples
    python test_navigator_python_codesearchnet.py 100 # Test on 100 samples
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
from datasets import load_dataset

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Import validators and navigator
from backend.validators.validation_framework import ValidationFramework
from backend.navigator.languages.adapter_registry import AdapterRegistry


class PythonCodeSearchNetTester:
    """Test navigator on Python CodeSearchNet dataset."""
    
    def __init__(self, max_samples: int = 10):
        self.max_samples = max_samples
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
        print("PYTHON NAVIGATOR VALIDATION - CODESEARCHNET DATASET")
        print("="*80)
        
        print(f"\nPhase 1: Downloading Python dataset (max {self.max_samples} samples)...")
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
        """Download Python CodeSearchNet dataset split.
        
        CodeSearchNet has mixed languages, so we load the full dataset and will
        filter for Python samples by parsing during extraction.
        """
        try:
            print(f"Loading CodeSearchNet validation split (may load more than needed)...")
            dataset = load_dataset(
                "sentence-transformers/codesearchnet",
                split="train"
            )
            
            # Convert to list of samples (up to max_samples to avoid memory issues)
            samples = []
            for i, sample in enumerate(dataset):
                if i >= self.max_samples * 2:  # Load more than needed to account for filtering
                    break
                samples.append(sample)
            
            print(f"✓ Loaded {len(samples)} samples from CodeSearchNet")
            return samples
        except Exception as e:
            print(f"✗ Failed to load dataset: {e}")
            return []
    
    def _extract_components(self, samples: List[Dict[str, Any]]):
        """Extract components from each sample.
        
        CodeSearchNet dataset format: 'code' and 'comment' fields.
        Skip non-Python code gracefully (parser will fail, which indicates non-Python).
        """
        if not samples:
            print("✗ No samples to process")
            return
        
        python_adapter = self.adapter_registry.get_adapter('python')
        
        for i, sample in enumerate(samples, 1):
            try:
                # Extract code and metadata from CodeSearchNet format
                source_code = sample.get('code')
                if not source_code:
                    print(f"\n[{i}/{len(samples)}] Skipping: No code in sample")
                    self.metrics['failed'] += 1
                    continue
                
                # Extract metadata from available fields
                comment = sample.get('comment', '')
                url = sample.get('url', '')
                
                # Use index as identifier since no repo/path/func_name in standard format
                file_path = f'sample_{i}.py'
                repo = 'codesearchnet'
                
                # Show progress
                code_preview = source_code[:50].replace('\n', ' ')
                print(f"\n[{i}/{len(samples)}] {repo}/{file_path}")
                print(f"  Code: {code_preview}...")
                
                # Parse - if this fails, it's likely not Python, so skip gracefully
                tree = python_adapter.parse(source_code)
                
                # Check for parse errors indicating non-Python code
                if tree.root_node.has_error:
                    print(f"  ↷ Not valid Python (skipped)")
                    self.metrics['failed'] += 1
                    self.metrics['error_summary']['Not valid Python'] += 1
                    continue
                components = python_adapter.extract_components(tree, source_code, file_path, repo)
                
                if not components:
                    print(f"  ℹ No components extracted (may be incomplete Python snippet)")
                    self.metrics['failed'] += 1
                    self.metrics['error_summary']['No components extracted'] += 1
                    continue
                
                # DEBUG: Analyze extracted components
                comp_types = defaultdict(int)
                for cid, comp in components.items():
                    comp_types[comp.type.value] += 1
                    print(f"    • {comp.type.value}: {comp.name} (lines {comp.location.start_line}-{comp.location.end_line})")
                
                print(f"  ✓ Extracted {len(components)} components: {dict(comp_types)}")
                
                # Track extraction stats
                for comp_type, count in comp_types.items():
                    self.metrics['extraction_stats'][comp_type] += count
                
                # Extract dependencies for each component
                for cid, component in components.items():
                    try:
                        deps = python_adapter.resolve_dependencies(component, tree, source_code, components)
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
                print(f"  ✗ Error: {str(e)[:100]}")
                self.metrics['failed'] += 1
                self.metrics['error_summary'][type(e).__name__] += 1
                
                self.results.append({
                    'repo': repo,
                    'file_path': file_path,
                    'sample_index': i,
                    'comment': comment,
                    'source_code': source_code[:100] if 'source_code' in locals() else '',
                    'components': {},
                    'component_count': 0,
                    'status': 'error',
                    'error': str(e)[:200]
                })
        
        self.metrics['total_samples'] = len(samples)
    
    def _generate_metrics(self):
        """Generate validation metrics from results."""
        print("\nMetrics generated:")
        print(f"  Total samples: {self.metrics['total_samples']}")
        print(f"  Successful: {self.metrics['successful']}")
        print(f"  Failed: {self.metrics['failed']}")
        
        if self.metrics['extraction_stats']:
            print(f"\n  Component types extracted:")
            for comp_type, count in sorted(self.metrics['extraction_stats'].items()):
                print(f"    - {comp_type}: {count}")
        
        if self.metrics['error_summary']:
            print(f"\n  Error breakdown:")
            for error_type, count in sorted(self.metrics['error_summary'].items(), 
                                           key=lambda x: x[1], reverse=True):
                print(f"    - {error_type}: {count}")
    
    def _save_results(self):
        """Save results to JSON file."""
        output_dir = project_root / 'data' / 'validation' / 'codesearchnet'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"python_navigator_results_{self.max_samples}_samples.json"
        filepath = output_dir / filename
        
        output = {
            'metadata': {
                'language': 'python',
                'dataset': 'codesearchnet',
                'max_samples': self.max_samples,
                'total_processed': self.metrics['total_samples'],
            },
            'metrics': dict(self.metrics),
            'results': self.results,
            'error_summary': dict(self.metrics['error_summary']),
        }
        
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"✓ Results saved to {filepath}")
    
    def _print_summary(self):
        """Print test summary."""
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        
        total = self.metrics['total_samples']
        successful = self.metrics['successful']
        failed = self.metrics['failed']
        
        if total > 0:
            success_rate = successful / total * 100
            print(f"\n✓ Success Rate: {successful}/{total} ({success_rate:.1f}%)")
        else:
            print(f"\n✗ No samples processed")
            return
        
        if self.metrics['extraction_stats']:
            total_components = sum(self.metrics['extraction_stats'].values())
            avg_components = total_components / successful if successful > 0 else 0
            print(f"\n✓ Components Extracted:")
            print(f"  Total: {total_components}")
            print(f"  Average per file: {avg_components:.1f}")
            for comp_type, count in sorted(self.metrics['extraction_stats'].items()):
                pct = count / total_components * 100 if total_components > 0 else 0
                print(f"  - {comp_type}: {count} ({pct:.1f}%)")
        
        if self.metrics['error_summary'] and failed > 0:
            print(f"\n⚠ Top Failures:")
            for error_type, count in sorted(self.metrics['error_summary'].items(), 
                                           key=lambda x: x[1], reverse=True)[:5]:
                pct = count / failed * 100
                print(f"  - {error_type}: {count} ({pct:.1f}%)")
        
        print("\n" + "="*80)


def main():
    """Main entry point."""
    max_samples = 10
    
    if len(sys.argv) > 1:
        try:
            max_samples = int(sys.argv[1])
        except ValueError:
            print(f"Invalid sample count: {sys.argv[1]}")
            sys.exit(1)
    
    tester = PythonCodeSearchNetTester(max_samples=max_samples)
    tester.run()


if __name__ == '__main__':
    main()
