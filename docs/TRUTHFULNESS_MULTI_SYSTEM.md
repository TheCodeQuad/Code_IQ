# Multi-System Docstring Truthfulness Evaluation

## Overview

This evaluation script assesses the **truthfulness** of AI-generated docstrings from five different systems by checking whether the components mentioned in docstrings actually exist in your codebase.

## What It Does

1. **Loads Docstrings**: Reads docstrings from 5 different systems in `completeness_evaluation_cleaned.json`
2. **Extracts Components**: Uses your local LLM (llama.cpp) to extract mentioned code components (classes, methods, functions)
3. **Verifies Existence**: Checks if each extracted component actually exists in the repository dependency graph
4. **Detects Cross-File References**: Identifies when a docstring correctly references components from other files
5. **Calculates Metrics**: Computes existence ratio, hallucination rate, and cross-file reference statistics
6. **Generates Reports**: Creates detailed JSON and Markdown reports comparing all systems

## Key Metrics

- **Existence Ratio**: Percentage of mentioned components that actually exist (higher is better)
- **Hallucination Rate**: Percentage of mentioned components that don't exist (lower is better)
- **Cross-File References**: Number of correctly identified dependencies from other files
- **Average Mentions per Docstring**: How many components are referenced on average

## Requirements

### 1. Input Data Format

Your `completeness_evaluation_cleaned.json` should have this structure:

```json
{
  "system_1": [
    {
      "id": "ComponentID",
      "component_id": "ComponentID",
      "name": "component_name",
      "language": "python",
      "type": "METHOD",
      "file_path": "path/to/file.py",
      "docstring": "Your AI-generated docstring here...",
      "location": {
        "file_path": "path/to/file.py",
        "start_line": 10,
        "end_line": 15
      }
    }
  ],
  "system_2": [...],
  "system_3": [...],
  "system_4": [...],
  "system_5": [...]
}
```

See `data/validation/sample_completeness_evaluation_cleaned.json` for a complete example.

### 2. Navigator Output

You need the repository dependency graph from the Navigator component:
- Location: `data/intermediate/navigator_output/`
- Contains: JSON files with all real components in your codebase
- Format: DAG exports or component maps

### 3. Local LLM Model

The script uses your local `llama.cpp` model by default:
- **Model**: `models/qwen2.5-coder-7b-instruct-q4_k_m.gguf`
- **No API key needed** (works offline)
- Automatically uses GPU if available

## Usage

### Basic Usage

```bash
python -m backend.eval_truthfulness_multi_system
```

This uses default paths:
- Input: `data/validation/completeness_evaluation_cleaned.json`
- Navigator: `data/intermediate/navigator_output`
- Output: `data/validation/truthfulness`

### Custom Paths

```bash
python -m backend.eval_truthfulness_multi_system \
    --input path/to/your/docstrings.json \
    --navigator-dir path/to/navigator/output \
    --output-dir path/to/results
```

### Fast Mode (Regex-Based)

If you want faster evaluation without LLM (less accurate but quicker):

```bash
python -m backend.eval_truthfulness_multi_system --no-llm
```

## Output Files

### 1. `docstring_truthfulness_evaluation.json`

Detailed results for each system and component:

```json
{
  "system_1": {
    "ComponentID": {
      "component_id": "ComponentID",
      "total_mentions": 3,
      "existing_mentions": 2,
      "cross_file_mentions": 1,
      "hallucination_rate": 0.33,
      "existence_ratio": 0.67,
      "mentioned_components": [
        {
          "name": "DataProcessor",
          "exists": true,
          "is_cross_file": true,
          "component_type": "CLASS",
          "file_path": "src/processor.py"
        },
        {
          "name": "validate_output",
          "exists": true,
          "is_cross_file": false
        },
        {
          "name": "NonExistentClass",
          "exists": false,
          "is_cross_file": false
        }
      ]
    }
  }
}
```

### 2. `docstring_truthfulness_report.md`

Comprehensive Markdown report with:
- **System Comparison Table**: Side-by-side metrics for all systems
- **Rankings**: Best to worst by different criteria
- **Language-Specific Analysis**: Performance breakdown by programming language
- **Hallucination Examples**: Specific cases of non-existent components
- **Key Insights**: Actionable recommendations

## Example Workflow

### Step 1: Prepare Your Data

Ensure you have docstrings from 5 systems in the correct format:

```bash
# Check your input file exists
ls data/validation/completeness_evaluation_cleaned.json

# Check navigator output exists
ls data/intermediate/navigator_output/
```

### Step 2: Run Evaluation

```bash
cd c:\Users\shruti\OneDrive\Desktop\PROJECTs\Code_IQ

python -m backend.eval_truthfulness_multi_system
```

You'll see progress:
```
======================================================================
Multi-System Docstring Truthfulness Evaluation
======================================================================
Input file: data/validation/completeness_evaluation_cleaned.json
Navigator output: data/intermediate/navigator_output
Output directory: data/validation/truthfulness
Using LLM: True (llama.cpp local model)
======================================================================

Loaded 2547 components from navigator output
Loaded data for 5 systems
  system_1: 250 components
  system_2: 250 components
  system_3: 250 components
  system_4: 250 components
  system_5: 250 components

Starting multi-system evaluation...
Evaluating system_1: 100%|████████████████████| 250/250
Evaluating system_2: 100%|████████████████████| 250/250
...
```

### Step 3: Review Results

```bash
# View the markdown report
code data/validation/truthfulness/docstring_truthfulness_report.md

# Or open in browser
start data/validation/truthfulness/docstring_truthfulness_report.md
```

## Understanding the Results

### High Existence Ratio (>80%)
✅ **Good**: The system produces accurate docstrings that reference real components

### Low Hallucination Rate (<20%)
✅ **Good**: The system rarely invents non-existent components

### Many Cross-File References
✅ **Good**: The system understands dependencies and can reference components from other files

### Low Existence Ratio (<60%)
⚠️ **Warning**: The system frequently references non-existent components (hallucinations)

## Troubleshooting

### Issue: "Model not found"
**Solution**: Ensure the model exists at `models/qwen2.5-coder-7b-instruct-q4_k_m.gguf`

### Issue: "Input file not found"
**Solution**: Create or specify the correct path to `completeness_evaluation_cleaned.json`

### Issue: "No components loaded from navigator"
**Solution**: Run the Navigator first to generate the dependency graph:
```bash
python -m backend.navigator.scanner --output data/intermediate/navigator_output
```

### Issue: LLM extraction too slow
**Solution**: Use regex-based extraction for faster results:
```bash
python -m backend.eval_truthfulness_multi_system --no-llm
```

## Advanced Options

### Evaluate Subset of Systems

Edit the input JSON to include only specific systems:
```json
{
  "system_1": [...],
  "system_3": [...]
}
```

### Custom Component Extraction

Modify `backend/evaluator/truthfulness.py` to adjust:
- Component extraction patterns
- Filtering rules for common/standard library names
- Cross-file detection logic

## Performance Notes

- **With LLM**: ~5-10 docstrings per minute (more accurate)
- **Without LLM (regex)**: ~100+ docstrings per minute (less accurate)
- **GPU Acceleration**: Automatically used if available through llama.cpp

## Integration with Other Evaluators

This truthfulness evaluator complements:
- **Completeness**: Checks if docstrings have all required sections
- **Helpfulness**: Assesses the quality and usefulness of docstring content
- **Truthfulness**: Verifies component references are real (this tool)

Run all three for comprehensive docstring evaluation!

## Citation

If you use this evaluation in research, please cite:
```
Code_IQ Multi-System Truthfulness Evaluation
https://github.com/yourusername/Code_IQ
```

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the sample input file: `data/validation/sample_completeness_evaluation_cleaned.json`
3. Verify your navigator output contains component data
4. Open an issue on GitHub
