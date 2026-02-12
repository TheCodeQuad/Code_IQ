"""
CodeSearchNet Integration - Load and validate against ground truth dataset.

CodeSearchNet is a curated dataset of ~6M code snippets from GitHub with:
- Function signatures, parameters, return types
- Docstrings
- Full source code
- Language diversity (Python, JavaScript, Go, Java, PHP, Ruby)

This module allows you to:
1. Download CodeSearchNet dataset
2. Extract ground truth facts
3. Run your adapter on the same code
4. Compare extraction accuracy
"""

import json
import requests
from typing import Dict, List, Any, Optional
from pathlib import Path
import gzip
from collections import defaultdict

# CodeSearchNet splits available
CODESEARCHNET_SPLITS = {
    'python': 'https://s3.amazonaws.com/code-search-net/CodeSearchNet/v2/python_mini.jsonl.gz',
    'javascript': 'https://s3.amazonaws.com/code-search-net/CodeSearchNet/v2/javascript_mini.jsonl.gz',
    'java': 'https://s3.amazonaws.com/code-search-net/CodeSearchNet/v2/java_mini.jsonl.gz',
    'go': 'https://s3.amazonaws.com/code-search-net/CodeSearchNet/v2/go_mini.jsonl.gz',
    'php': 'https://s3.amazonaws.com/code-search-net/CodeSearchNet/v2/php_mini.jsonl.gz',
    'ruby': 'https://s3.amazonaws.com/code-search-net/CodeSearchNet/v2/ruby_mini.jsonl.gz',
}


class CodeSearchNetDataset:
    """Load and interact with CodeSearchNet dataset."""
    
    def __init__(self, cache_dir: str = 'data/validation/codesearchnet'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def download_split(self, language: str, max_samples: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Download and decompress CodeSearchNet split.
        
        Each sample has:
        {
            'repo': 'owner/repo',
            'path': 'file/path.py',
            'func_name': 'function_name',
            'original_string': 'def func_name(...):\\n    ...',
            'language': 'python',
            'code': 'def func_name(...):\\n    ...',
            'code_tokens': [...],
            'docstring': 'Function docstring if exists',
            'docstring_tokens': [...],
            'url': 'https://github.com/...',
            ... more fields
        }
        """
        
        if language not in CODESEARCHNET_SPLITS:
            raise ValueError(f"Language {language} not in CodeSearchNet. Available: {list(CODESEARCHNET_SPLITS.keys())}")
        
        cache_file = self.cache_dir / f'{language}_mini.jsonl'
        
        # Check if already downloaded
        if cache_file.exists():
            print(f"Loading {language} from cache...")
            return self._load_jsonl(cache_file, max_samples)
        
        # Download
        print(f"Downloading CodeSearchNet {language}...")
        url = CODESEARCHNET_SPLITS[language]
        
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Decompress on-the-fly
        with gzip.GzipFile(fileobj=response.raw) as gz:
            with open(cache_file, 'wb') as f:
                f.write(gz.read())
        
        print(f"Saved to {cache_file}")
        return self._load_jsonl(cache_file, max_samples)
    
    def _load_jsonl(self, file_path: Path, max_samples: Optional[int] = None) -> List[Dict[str, Any]]:
        """Load JSONL file (one JSON per line)."""
        samples = []
        
        with open(file_path, 'r') as f:
            for i, line in enumerate(f):
                if max_samples and i >= max_samples:
                    break
                samples.append(json.loads(line))
        
        return samples
    
    def extract_ground_truth(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract ground truth facts from CodeSearchNet samples.
        
        Returns:
        {
            'functions': [
                {
                    'name': 'func_name',
                    'language': 'python',
                    'source': 'def func_name(...)...',
                    'parameters': [...],
                    'return_type': ...,
                    'docstring': '...',
                    'calls': [...],
                }
            ]
        }
        """
        
        functions = []
        
        for sample in samples:
            func_info = {
                'repo': sample.get('repo'),
                'file_path': sample.get('path'),
                'name': sample.get('func_name'),
                'language': sample.get('language'),
                'source_code': sample.get('code', sample.get('original_string')),
                'docstring': sample.get('docstring'),
                'url': sample.get('url'),
                # These would require parsing to extract
                'code_tokens': sample.get('code_tokens', []),
                'docstring_tokens': sample.get('docstring_tokens', []),
            }
            functions.append(func_info)
        
        return {
            'source': 'CodeSearchNet',
            'num_functions': len(functions),
            'functions': functions
        }


class CodeSearchNetValidator:
    """Validate your adapter against CodeSearchNet ground truth."""
    
    def __init__(self):
        self.dataset = CodeSearchNetDataset()
        from backend.validators.gold_extractor import get_gold_extractor
        from backend.navigator.languages.adapter_registry import AdapterRegistry
        self.gold_extractors = {
            'python': get_gold_extractor('python'),
            'javascript': get_gold_extractor('javascript'),
            'java': get_gold_extractor('java'),
        }
        self.registry = AdapterRegistry()
    
    def validate_against_codesearchnet(
        self,
        language: str,
        max_samples: int = 100
    ) -> Dict[str, Any]:
        """
        Run validation against CodeSearchNet.
        
        Returns metrics of form:
        {
            'language': 'python',
            'samples_tested': 100,
            'successfully_parsed': 95,
            'parse_errors': 5,
            'avg_precision': 0.92,
            'avg_recall': 0.88,
            'avg_f1': 0.90,
            'samples': [
                {
                    'name': 'func_name',
                    'f1': 0.95,
                    'precision': 0.96,
                    'recall': 0.94,
                }
            ]
        }
        """
        
        if language not in self.gold_extractors:
            raise ValueError(f"No validator for language: {language}")
        
        print(f"\nValidating against CodeSearchNet ({language})...")
        
        # Download dataset
        samples = self.dataset.download_split(language, max_samples)
        print(f"Loaded {len(samples)} samples from CodeSearchNet")
        
        # Extract ground truth
        ground_truth = self.dataset.extract_ground_truth(samples)
        
        gold_extractor = self.gold_extractors[language]
        from backend.navigator.treesitter.parser_factory import get_ts_parser
        
        results = {
            'language': language,
            'samples_tested': len(samples),
            'successfully_parsed': 0,
            'parse_errors': 0,
            'precision_scores': [],
            'recall_scores': [],
            'f1_scores': [],
            'samples': []
        }
        
        for i, func in enumerate(ground_truth['functions']):
            try:
                source = func['source_code']
                if not source:
                    continue
                
                # Parse with gold extractor
                parser = get_ts_parser(language)
                tree = parser.parse(bytes(source, 'utf8'))
                gold_output = gold_extractor.extract(tree, source, 'codesearchnet.py')
                gold_components = gold_output['components']
                
                # Extract with adapter (if available)
                try:
                    adapter = self.registry.get_adapter_for_file(f'dummy.{self._get_ext(language)}')
                    if adapter:
                        tree = adapter.parse(source)
                        ir_output = adapter.extract_components(tree, source, 'codesearchnet.py', 'codesearchnet')
                        ir_components = list(ir_output.values())
                    else:
                        ir_components = []
                except Exception as e:
                    ir_components = []
                
                # Simple metrics: did we find the main function?
                gold_names = {c['name'] for c in gold_components}
                ir_names = {c.get('name', '?') for c in ir_components} if ir_components else set()
                
                if gold_names:
                    precision = len(gold_names & ir_names) / len(ir_names) if ir_names else 0
                    recall = len(gold_names & ir_names) / len(gold_names)
                    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
                    
                    results['precision_scores'].append(precision)
                    results['recall_scores'].append(recall)
                    results['f1_scores'].append(f1)
                    
                    results['samples'].append({
                        'name': func['name'],
                        'repo': func['repo'],
                        'precision': precision,
                        'recall': recall,
                        'f1': f1,
                        'gold_components': len(gold_components),
                        'ir_components': len(ir_components),
                    })
                    
                    results['successfully_parsed'] += 1
                
            except Exception as e:
                results['parse_errors'] += 1
                if i < 5:  # Print first 5 errors
                    print(f"  Error on {func['name']}: {e}")
        
        # Aggregate
        if results['precision_scores']:
            results['avg_precision'] = sum(results['precision_scores']) / len(results['precision_scores'])
            results['avg_recall'] = sum(results['recall_scores']) / len(results['recall_scores'])
            results['avg_f1'] = sum(results['f1_scores']) / len(results['f1_scores'])
        
        return results
    
    def _get_ext(self, language: str) -> str:
        """Get file extension for language."""
        exts = {
            'python': 'py',
            'javascript': 'js',
            'java': 'java',
            'go': 'go',
            'php': 'php',
            'ruby': 'rb',
        }
        return exts.get(language, 'py')


if __name__ == '__main__':
    import sys
    
    validator = CodeSearchNetValidator()
    
    language = sys.argv[1] if len(sys.argv) > 1 else 'python'
    max_samples = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    
    result = validator.validate_against_codesearchnet(language, max_samples)
    
    print("\n" + "=" * 80)
    print(f"CODESEARCHNET VALIDATION - {language.upper()}")
    print("=" * 80)
    print(f"Samples tested: {result['successfully_parsed']}/{result['samples_tested']}")
    print(f"Avg Precision: {result.get('avg_precision', 0):.2%}")
    print(f"Avg Recall: {result.get('avg_recall', 0):.2%}")
    print(f"Avg F1: {result.get('avg_f1', 0):.2%}")
    
    # Save results
    output = f'validation_codesearchnet_{language}.json'
    with open(output, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved to {output}")
