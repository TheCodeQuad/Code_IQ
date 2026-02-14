"""
Validation Framework for Code Component Extraction

This package provides comprehensive validation of the IR/CodeComponent extraction:

1. **Gold Extractors** (`gold_extractor.py`)
   - Direct AST walkers that extract raw structural facts
   - No normalization, just facts: name, type, location, params, calls
   - Used as ground truth for validation

2. **Validation Framework** (`validation_framework.py`)
   - Compare gold extraction vs adapter-based extraction
   - Compute: precision, recall, F1, field-level accuracy
   - Identify missing/extra components and errors

3. **CodeSearchNet Validator** (`codesearchnet_validator.py`)
   - Validate against standard dataset (6M+ code snippets)
   - Provides external benchmark for extraction quality

Quick Start:

    from backend.validators.validation_framework import ValidationFramework
    
    validator = ValidationFramework()
    validator.validate_directory('backend/repos/some_repo')
    validator.print_summary()
    validator.save_report('report.json')

Or validate against CodeSearchNet:

    from backend.validators.codesearchnet_validator import CodeSearchNetValidator
    
    csn_validator = CodeSearchNetValidator()
    result = csn_validator.validate_against_codesearchnet('python', max_samples=100)
    print(f"F1: {result['avg_f1']:.2%}")
"""

from .gold_extractor import (
    GoldExtractor,
    PythonGoldExtractor,
    JavaScriptGoldExtractor,
    JavaGoldExtractor,
    get_gold_extractor,
)

from .validation_framework import (
    ValidationFramework,
    ValidationMetrics,
)

from .codesearchnet_validator import (
    CodeSearchNetDataset,
    CodeSearchNetValidator,
)

__all__ = [
    'GoldExtractor',
    'PythonGoldExtractor',
    'JavaScriptGoldExtractor',
    'JavaGoldExtractor',
    'get_gold_extractor',
    'ValidationFramework',
    'ValidationMetrics',
    'CodeSearchNetDataset',
    'CodeSearchNetValidator',
]
