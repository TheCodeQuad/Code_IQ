# ✅ Complete Workflow: Completeness → Truthfulness Evaluation

## Overview

Your completeness evaluation now **automatically saves results** in the format needed for truthfulness evaluation! Here's the complete workflow:

## Quick Start: Single System

```bash
# Step 1: Run completeness evaluation with auto-save
python backend/run_eval.py path/to/your/code --save-for-truthfulness

# Step 2: Run truthfulness evaluation (uses the saved file automatically)
python -m backend.eval_truthfulness_multi_system
```

That's it! ✨

---

## Complete Workflow Examples

### Example 1: Evaluate a Single Directory

```bash
# Evaluate and save results
cd c:\Users\shruti\OneDrive\Desktop\PROJECTs\Code_IQ

python backend/run_eval.py backend/ --save-for-truthfulness --verbose

# This creates: data/validation/completeness_evaluation_cleaned.json

# Now run truthfulness check
python -m backend.eval_truthfulness_multi_system

# Results saved to: data/validation/truthfulness/
```

### Example 2: Compare Multiple Systems

```bash
# System 1: Your baseline
python backend/run_eval.py backend/ \\
    --save-for-truthfulness \\
    --system-name system_1

# System 2: After improvements (append to same file)
python backend/run_eval.py backend/ \\
    --save-for-truthfulness \\
    --system-name system_2 \\
    --append

# System 3: Different approach
python backend/run_eval.py backend/ \\
    --save-for-truthfulness \\
    --system-name system_3 \\
    --append

# System 4 and 5: More variations
python backend/run_eval.py backend/ \\
    --save-for-truthfulness \\
    --system-name system_4 \\
    --append

python backend/run_eval.py backend/ \\
    --save-for-truthfulness \\
    --system-name system_5 \\
    --append

# Now compare all 5 systems side-by-side!
python -m backend.eval_truthfulness_multi_system
```

### Example 3: Custom Output Location

```bash
# Save to custom location
python backend/run_eval.py src/ \\
    --save results/my_completeness_results.json \\
    --system-name my_system

# Run truthfulness with custom input
python -m backend.eval_truthfulness_multi_system \\
    --input results/my_completeness_results.json \\
    --output-dir results/truthfulness
```

---

## Command Reference

### Completeness Evaluation (`run_eval.py`)

```bash
python backend/run_eval.py <path> [options]

Options:
  path                          File or directory to evaluate
  -v, --verbose                 Show per-file extraction details
  --save FILE                   Save to specific JSON file
  --save-for-truthfulness       Quick save to default location
  --system-name NAME            System name (default: system_1)
  --append                      Add to existing file (multi-system)
```

### Truthfulness Evaluation (`eval_truthfulness_multi_system.py`)

```bash
python -m backend.eval_truthfulness_multi_system [options]

Options:
  --input FILE                  Input JSON file (default: completeness_evaluation_cleaned.json)
  --navigator-dir DIR           Navigator output directory
  --output-dir DIR              Where to save results
  --no-llm                      Use regex instead of LLM (faster)
```

---

## What Gets Saved?

The completeness evaluation now saves:

```json
{
  "system_1": [
    {
      "id": "MyClass.my_method",
      "component_id": "MyClass.my_method",
      "name": "my_method",
      "language": "python",
      "type": "METHOD",
      "score": 0.85,
      "has_docstring": true,
      "docstring": "Complete docstring text here...",
      "file_path": "src/my_file.py",
      "location": {
        "file_path": "src/my_file.py",
        "start_line": 10,
        "end_line": 25
      },
      "element_scores": {...},
      "element_required": {...}
    }
  ]
}
```

This format is **exactly what truthfulness evaluation needs**! ✅

---

## Complete Example: Full Pipeline

```bash
# 1. Navigate to project
cd c:\Users\shruti\OneDrive\Desktop\PROJECTs\Code_IQ

# 2. Run completeness evaluation on your code
python backend/run_eval.py backend/ \\
    --save-for-truthfulness \\
    --system-name system_1 \\
    --verbose

# Output:
# =============================================================================
#   MULTI-LANGUAGE COMPLETENESS EVALUATION
# =============================================================================
#
# BY LANGUAGE:
# ╔═════════════╦═══════╦═════════════╦═══════════════╦══════╦═══════════╗
# ║ Language    ║ Total ║ Documented  ║ Undocumented  ║ Doc% ║ Avg Score ║
# ╠═════════════╬═══════╬═════════════╬═══════════════╬══════╬═══════════╣
# ║ python      ║   250 ║         230 ║            20 ║ 92.0 ║      0.82 ║
# ╚═════════════╩═══════╩═════════════╩═══════════════╩══════╩═══════════╝
#
# ✅ Saved 230 components to data/validation/completeness_evaluation_cleaned.json
#    System: system_1
#    Ready for truthfulness evaluation!
#
# 🎯 Next step: Run truthfulness evaluation:
#    python -m backend.eval_truthfulness_multi_system --input data/validation/completeness_evaluation_cleaned.json

# 3. Run truthfulness evaluation
python -m backend.eval_truthfulness_multi_system

# Output:
# ======================================================================
# Multi-System Docstring Truthfulness Evaluation
# ======================================================================
# Input file: data/validation/completeness_evaluation_cleaned.json
# Navigator output: data/intermediate/navigator_output
# Output directory: data/validation/truthfulness
# Using LLM: True (llama.cpp local model)
# ======================================================================
#
# Loaded 2547 components from navigator output
# Loaded data for 1 systems
#   system_1: 230 components
#
# Starting multi-system evaluation...
# Evaluating system_1: 100%|████████████████████| 230/230
#
# ✅ Evaluated 230 docstrings across 1 systems
#
# Generating comparative report...
# ✅ Reports saved to data/validation/truthfulness
#
# Generated files:
#   - docstring_truthfulness_evaluation.json (detailed results)
#   - docstring_truthfulness_report.md (comparative analysis)
#
# 🎉 Evaluation complete!

# 4. View the results
code data/validation/truthfulness/docstring_truthfulness_report.md
```

---

## Understanding the Output Files

### From Completeness Evaluation

**File**: `data/validation/completeness_evaluation_cleaned.json`
- Multi-system format
- Contains all docstrings
- Ready for truthfulness check

### From Truthfulness Evaluation

**File 1**: `docstring_truthfulness_evaluation.json`
- Detailed component-level results
- Shows which mentioned components exist
- Identifies hallucinations

**File 2**: `docstring_truthfulness_report.md`
- Human-readable summary
- System rankings and comparisons
- Actionable insights

---

## Tips & Best Practices

### 1. Always Save Completeness Results
```bash
# ✅ Good - saves for later use
python backend/run_eval.py backend/ --save-for-truthfulness

# ❌ Missing opportunity - no saved data
python backend/run_eval.py backend/
```

### 2. Use System Names for Comparison
```bash
# Clear naming helps track different approaches
--system-name baseline
--system-name with_llm_improvements
--system-name fine_tuned_model
```

### 3. Append When Building Multi-System Data
```bash
# First system - no append needed
python backend/run_eval.py backend/ --save-for-truthfulness --system-name system_1

# Additional systems - use --append
python backend/run_eval.py backend/ --save-for-truthfulness --system-name system_2 --append
python backend/run_eval.py backend/ --save-for-truthfulness --system-name system_3 --append
```

### 4. Verify Navigator Output Exists
```bash
# Check if navigator has created the dependency graph
ls data/intermediate/navigator_output/

# If empty, run navigator first (if you have it set up)
# python -m backend.navigator.scanner --output data/intermediate/navigator_output
```

---

## Troubleshooting

### Issue: "No components found to evaluate"
**Solution**: Make sure you're pointing to a directory with code files:
```bash
python backend/run_eval.py backend/ --save-for-truthfulness
```

### Issue: "Input file not found" (truthfulness)
**Solution**: Run completeness evaluation first with `--save-for-truthfulness`:
```bash
python backend/run_eval.py backend/ --save-for-truthfulness
```

### Issue: "No components loaded from navigator"
**Solution**: The truthfulness evaluator needs the repository dependency graph. If you don't have navigator output yet, the truthfulness check will have limited functionality (can't verify component existence).

### Issue: Only seeing 1 system in truthfulness report
**Solution**: Use `--append` when adding additional systems:
```bash
# First system
python backend/run_eval.py backend/ --save-for-truthfulness --system-name system_1

# Second system - ADD --append
python backend/run_eval.py backend/ --save-for-truthfulness --system-name system_2 --append
```

---

## Summary: Your Workflow is Now Connected! 🎉

```
┌─────────────────────────────────────────────────────┐
│  Step 1: Completeness Evaluation                    │
│  python backend/run_eval.py backend/ \\             │
│      --save-for-truthfulness \\                     │
│      --system-name system_1                         │
└─────────────────┬───────────────────────────────────┘
                  │
                  │ Creates: completeness_evaluation_cleaned.json
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│  Step 2: Truthfulness Evaluation                    │
│  python -m backend.eval_truthfulness_multi_system   │
└─────────────────┬───────────────────────────────────┘
                  │
                  │ Creates: truthfulness reports
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│  Results: Comprehensive Quality Assessment          │
│  - Completeness scores (has all sections?)          │
│  - Truthfulness scores (mentions real components?)  │
│  - Hallucination detection                          │
│  - Multi-system comparison                          │
└─────────────────────────────────────────────────────┘
```

**You're all set!** Your completeness evaluation now flows directly into truthfulness evaluation. 🚀
