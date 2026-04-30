# Code Component Extraction Validation System

## Overview

This validation framework measures how accurately your **CodeComponent/IR extraction layer** preserves the true structure of code, compared against ground truth and external benchmarks.

## Problem Statement

Your system has 2 layers:
1. **Gold**: Direct AST facts (tree-sitter)
2. **IR**: Normalized CodeComponent objects

**Question**: Does normalization lose information? Are extracted components correct?

**Solution**: Compare both layers systematically using 3 validation approaches.

---

## Architecture

### The Three-Layer Approach

```
Real Code (Python/JS/Java/etc)
    ↓
┌─────────────────────────────────────────────┐
│ Layer 1: Official AST                       │
│ (tree-sitter parse tree)                    │
└─────────────────────────────────────────────┘
    ↓
    ├─ Path A: Gold Extractor (minimal logic)
    │   └─ Extract raw facts: name, type, location, params, calls
    │   └─ Output: JSON with structural info
    │
    └─ Path B: Your Adapter (with normalization)
        └─ Extract CodeComponent objects
        └─ Include: metadata, dependencies, decorators, etc.
        └─ Output: Normalized IR

    ↓ Compare A vs B
┌─────────────────────────────────────────────┐
│ Validation Metrics                          │
│ - Precision, Recall, F1                     │
│ - Field-level accuracy                      │
│ - Missing/extra components                  │
│ - Error analysis                            │
└─────────────────────────────────────────────┘
```

---

## The Three Validation Approaches

### Approach 1️⃣: File-by-File Validation

**What**: Compare gold extractor vs your adapter on a single file

**How**:
```python
from backend.validators.validation_framework import ValidationFramework

validator = ValidationFramework()
metrics = validator.validate_file("path/to/file.py")

print(f"F1: {metrics.f1:.2%}")
print(f"Precision: {metrics.precision:.2%}")
print(f"Recall: {metrics.recall:.2%}")
print(f"Missing: {metrics.missing}")
print(f"Extra: {metrics.extra}")
```

**Output**:
```
Gold Components: 12
IR Components: 11
Matched: 10

Precision: 91% (10/11 IR components were correct)
Recall: 83% (10/12 gold components found)
F1: 87%

Field Accuracy:
  - type: 100%
  - location: 90%
  - signature: 85%
  - parameters: 80%
  - calls: 75%

Missing:
  - helper_function (function@15)
```

**Use Case**: Debug specific files, understand what breaks

---

### Approach 2️⃣: Directory Validation with Aggregation

**What**: Validate all files in a directory, aggregate by language

**How**:
```python
validator = ValidationFramework()
validator.validate_directory("backend/repos")
validator.print_summary()
validator.save_report("report.json")
```

**Output**:
```json
{
  "summary": {
    "languages": 3,
    "total_files": 45,
    "overall_f1": 0.91
  },
  "by_language": {
    "python": {
      "num_files": 15,
      "avg_precision": 0.94,
      "avg_recall": 0.89,
      "avg_f1": 0.91,
      "files": [...]
    },
    "javascript": {
      "num_files": 20,
      "avg_precision": 0.89,
      "avg_recall": 0.85,
      "avg_f1": 0.87,
      "files": [...]
    }
  }
}
```

**Use Case**: 
- Measure overall extraction quality
- Identify weak languages
- Track improvements over time

---

### Approach 3️⃣: CodeSearchNet Benchmark Validation

**What**: Validate against 6M+ real GitHub functions (published dataset)

**How**:
```python
from backend.validators.codesearchnet_validator import CodeSearchNetValidator

csn = CodeSearchNetValidator()
result = csn.validate_against_codesearchnet('python', max_samples=100)

print(f"F1: {result['avg_f1']:.2%}")
```

**Why**:
- ✅ External, unbiased benchmark
- ✅ Real-world code (GitHub)
- ✅ Published ground truth (no bias)
- ✅ Standard across industry
- ✅ Comparable to other extractors

**Use Case**: 
- Prove extraction quality to stakeholders
- Compare against other tools
- Understand real-world performance

---

## Metrics Explained

### Component-Level Metrics

| Metric | Formula | Meaning |
|--------|---------|---------|
| **Precision** | matched / total_ir | % of IR components that were correct |
| **Recall** | matched / total_gold | % of gold components that were found |
| **F1** | 2 × P×R / (P+R) | Harmonic mean (balanced metric) |

**Interpretation**:
- High precision, low recall → Missing components
- Low precision, high recall → Over-extracting
- Balanced (P≈R) → System is working well

### Field-Level Accuracy

Each component has multiple fields:

| Field | Accuracy Target | Notes |
|-------|-----------------|-------|
| `type` | >98% | Should almost always match |
| `location` | >95% | Allow ±1 line due to formatting |
| `signature` | >90% | Whitespace may differ |
| `parameters` | >85% | Type hints may be incomplete |
| `modifiers` | >90% | Decorators/annotations fairly stable |
| `calls` | >70% | Hardest—many false positives |

---

## Quality Targets

```
F1 Score Ranges:

0.95+  ✅ Excellent
       - Ready for production
       - Acceptable edge cases

0.85+  ⚠️ Good
       - Usable but needs refinement
       - Some systematic issues

0.75+  ❌ Acceptable
       - Significant issues
       - Not production-ready

<0.75  🔴 Poor
       - Major problems
       - Don't use without fixes
```

---

## Interpreting Results

### If Precision is Low

**Symptom**: High recall but low precision
```
Gold: 10 components
IR: 20 components (only 10 matched)
F1: 66% (P=50%, R=100%)
```

**Cause**: Over-extracting components

**Examples**:
- Global variables being extracted too aggressively
- Comments parsed as docstrings
- Anonymous functions counted separately

**Fix**: Add stricter filtering criteria

### If Recall is Low

**Symptom**: High precision but low recall
```
Gold: 10 components
IR: 5 components (all matched)
F1: 66% (P=100%, R=50%)
```

**Cause**: Missing components

**Examples**:
- Nested functions not extracted
- Lambda functions ignored
- Private methods skipped

**Fix**: Walk AST more thoroughly, handle nested structures

### If Field Accuracy is Low

**Symptom**: Components matched but field values differ
```
Matched: 8/10
But: 6/8 have wrong parameter count
     4/8 have wrong return type
```

**Cause**: Type inference or parsing issue

**Examples**:
- Type hints not fully extracted
- Optional parameters missed
- Overloaded methods not handled

**Fix**: Improve type extraction logic

---

## Running the Validation System

### Quick Start

```bash
# Validate a single file
python -c "
from backend.validators.validation_framework import ValidationFramework
v = ValidationFramework()
m = v.validate_file('backend/repos/some_repo/src/main.py')
print(f'F1: {m.f1:.2%}')
"

# Validate entire directory
python -c "
from backend.validators.validation_framework import ValidationFramework
v = ValidationFramework()
v.validate_directory('backend/repos')
v.print_summary()
v.save_report('report.json')
"

# Validate against CodeSearchNet
python -c "
from backend.validators.codesearchnet_validator import CodeSearchNetValidator
c = CodeSearchNetValidator()
r = c.validate_against_codesearchnet('python', 50)
print(f\"F1: {r['avg_f1']:.2%}\")
"
```

### Full Guide

```bash
python backend/validators/validation_guide.py 1    # Single file
python backend/validators/validation_guide.py 2    # Directory
python backend/validators/validation_guide.py 3    # CodeSearchNet
python backend/validators/validation_guide.py all  # All approaches
```

---

## Debugging Failed Validation

### Step 1: Find Problem File

```python
report = json.load(open('validation_report_aggregated.json'))

# Find lowest F1
files_by_score = sorted(
    report['by_language']['python']['files'],
    key=lambda x: x['f1']
)
worst = files_by_score[0]
print(f"Worst: {worst['file']} (F1={worst['f1']:.2%})")
```

### Step 2: Deep-Dive on File

```python
from backend.validators.validation_framework import ValidationFramework

v = ValidationFramework()
m = v.validate_file(worst['file'])

print(f"Missing: {m.missing}")  # In gold, not IR
print(f"Extra: {m.extra}")      # In IR, not gold
print(f"Errors: {m.type_errors} type errors")

# Compare the actual components
print("\nGold components:")
for c in m.gold_components:
    print(f"  {c['name']} ({c['type']}) @ line {c['location']['start_line']}")

print("\nIR components:")
for c in m.ir_components:
    print(f"  {c.name} ({c.type}) @ line {c.location.start_line}")
```

### Step 3: Fix and Re-Validate

```python
# After fixing adapter code...
m = v.validate_file(worst['file'])
print(f"New F1: {m.f1:.2%}")  # Should improve
```

---

## Integration with Your Pipeline

### Pre-Commit Validation

```python
# In CI/CD pipeline
from backend.validators.validation_framework import ValidationFramework

validator = ValidationFramework()
validator.validate_directory('backend/repos')
report = validator.aggregate_results()

# Fail if F1 < threshold
if report['summary']['overall_f1'] < 0.85:
    raise Exception("Extraction quality below threshold!")
```

### Incremental Improvement

```
Week 1: Establish baseline
  python validation_guide.py 2 > baseline.txt
  # Overall F1: 0.78

Week 2: Fix Python extraction
  # Focus on missing components
  # Re-run: F1 → 0.82 ✓

Week 3: Fix JavaScript extraction  
  # Focus on parameter accuracy
  # Re-run: F1 → 0.86 ✓

Week 4: Fix dependency resolution
  # Re-run CodeSearchNet validation
```

---

## Advanced: Custom Validation Rules

You can extend the framework:

```python
from backend.validators.validation_framework import ValidationFramework

class CustomValidator(ValidationFramework):
    def validate_dependencies(self, components):
        """Check that dependency resolution is correct"""
        for comp in components:
            for dep in comp.depends_on:
                if dep not in components:
                    print(f"ERROR: {comp.id} depends on missing {dep}")
    
    def validate_consistency(self, components):
        """Check for consistency violations"""
        for comp in components:
            # Example: method should have parent class
            if comp.type == 'method' and not comp.parent:
                print(f"ERROR: Method {comp.id} has no parent class")

cv = CustomValidator()
cv.validate_directory('backend/repos')
```

---

## Summary

| Approach | When to Use | Metrics | Time |
|----------|-----------|---------|------|
| **File** | Debugging specific cases | F1, precision, recall, fields | 1s |
| **Directory** | Measure overall quality | Aggregate by language | 5-30min |
| **CodeSearchNet** | External benchmark | Real-world F1 | 1-2min |

**Recommended**: Run approach 2 (directory) regularly, approach 3 (CodeSearchNet) monthly.

