# Repository-Specific Truthfulness Evaluation Guide

## Overview

The truthfulness evaluator has been updated to **load only the specific repository's writer output file** instead of loading ALL files from the writer_output folder.

## File Naming Convention

Writer output files follow this naming pattern:
```
{repository_name}_writer_output.json
```

Examples:
- `testrepo_writer_output.json`
- `test_repo_writer_output.json`
- `my_app_writer_output.json`

## Usage

### Option 1: Evaluate Specific Repository (Recommended)

Evaluate truthfulness for a single repository:

```bash
python evaluate_repository_truthfulness.py --repo testrepo
```

**Features:**
- Loads ONLY `testrepo_writer_output.json`
- Evaluates all docstrings in that file
- Generates repository-specific reports
- Output: `testrepo_truthfulness_results.json` and `testrepo_truthfulness_report.md`

### Option 2: Using eval_truthfulness.py with Repository Filter

```bash
# Evaluate specific repository
python -m backend.eval_truthfulness --repo testrepo

# Evaluate all repositories
python -m backend.eval_truthfulness
```

### Option 3: Direct Python API

```python
from backend.evaluator.truthfulness_comprehensive import ComprehensiveTruthfulnessEvaluator

evaluator = ComprehensiveTruthfulnessEvaluator(
    navigator_output_dir="data/intermediate/navigator_output",
    writer_output_dir="data/intermediate/agent_output/writer",
    repository_name="testrepo"  # Only load this repo's files
)

# Evaluate all docstrings from this repository's writer output
results = evaluator.evaluate_repository_writer_output("testrepo")

# Generate reports
summary = evaluator.generate_summary_report(results)
evaluator.save_results_json(results, Path("results.json"))
evaluator.generate_markdown_report(results, Path("report.md"))
```

## Command-Line Examples

```bash
# Evaluate specific repository with LLM
python evaluate_repository_truthfulness.py --repo testrepo

# Evaluate specific repository without LLM (faster)
python evaluate_repository_truthfulness.py --repo testrepo --no-llm

# Evaluate specific repository with Gemini API
python evaluate_repository_truthfulness.py --repo testrepo --llm-mode gemini

# Save results to custom directory
python evaluate_repository_truthfulness.py --repo testrepo --output results/truthfulness/

# Custom writer output directory
python evaluate_repository_truthfulness.py \
  --repo testrepo \
  --writer-dir /path/to/writer_output \
  --navigator-dir /path/to/navigator_output \
  --output /path/to/results/
```

## How It Works

### Before (Old System - Issue)
```
writer_output/ folder
├── testrepo_writer_output.json
├── test_repo_writer_output.json
├── myapp_writer_output.json
└── other_repo_writer_output.json

❌ Old: Loaded ALL files → 37+ components being evaluated
```

### After (New System - Fix)
```
writer_output/ folder
├── testrepo_writer_output.json          ← Only this one
├── test_repo_writer_output.json
├── myapp_writer_output.json
└── other_repo_writer_output.json

✅ New: Loads ONLY testrepo_writer_output.json
```

## Repository Name Matching

The system auto-detects repository files using multiple naming patterns:

- `{repo_name}_writer_output.json` - Exact match
- `*{repo_name}*_writer_output.json` - Partial match
- `*{repo_name.replace('_', '-')}*_writer_output.json` - Underscore/dash handling
- `*{repo_name.replace('-', '_')}*_writer_output.json` - Dash/underscore handling

**Examples:**
- Looking for "testrepo" → finds `testrepo_writer_output.json`
- Looking for "test_repo" → finds `test_repo_writer_output.json` or `test-repo_writer_output.json`
- Looking for "my-app" → finds `my_app_writer_output.json`

## Output Files

After evaluation, you'll get:

1. **JSON Results** (`{repo}_truthfulness_results.json`)
   - Detailed per-docstring metrics
   - Component existence status
   - Cross-file reference information
   - Machine-readable format

2. **Markdown Report** (`{repo}_truthfulness_report.md`)
   - Executive summary
   - Key metrics and statistics
   - Language-specific breakdown
   - Hallucination analysis
   - Cross-file reference analysis
   - Recommendations

## Metrics Explained

| Metric | What It Means | Target |
|--------|---------------|--------|
| **Existence Ratio** | % of mentioned components that actually exist | > 80% |
| **Hallucination Rate** | % of mentioned components that don't exist | < 20% |
| **Cross-file References** | Count of dependencies from other files | Higher is better |
| **Mentions Per Docstring** | Average richness/detail level | Domain-specific |

## Example Output

```
================================================================================
Repository Truthfulness Evaluation: testrepo
================================================================================
Writer output dir:   C:\BIA6\CodeIQ\Code_IQ\data\intermediate\agent_output\writer
Navigator dir:       C:\BIA6\CodeIQ\Code_IQ\data\intermediate\navigator_output
Output dir:          C:\BIA6\CodeIQ\Code_IQ\data\validation\truthfulness
Using LLM:           Yes (llama.cpp)
================================================================================

Loading and evaluating docstrings for repository: testrepo
✅ Evaluated 3 docstrings

📊 Summary Metrics:
  Total Docstrings:        3
  Total Mentions:          12
  Existing Components:     11
  Cross-file References:   2
  Avg Existence Ratio:     91.7%
  Avg Hallucination Rate:  8.3%
  Avg Mentions Per Doc:    4.00

📚 By Language:
  - python: 3 docs, 12 mentions, 91.7% existence

💾 Saving results...

✅ Evaluation complete!
   Results: C:\BIA6\CodeIQ\Code_IQ\data\validation\truthfulness\testrepo_truthfulness_results.json
   Report:  C:\BIA6\CodeIQ\Code_IQ\data\validation\truthfulness\testrepo_truthfulness_report.md
```

## Troubleshooting

### "No writer output files found for repository 'testrepo'"

1. Check that the file exists in the writer_output directory:
   - Look for `testrepo_writer_output.json`
   - Check for variations like `test_repo_writer_output.json` or `testrepo-output.json`

2. Verify the writer_output directory path:
   ```bash
   ls -la data/intermediate/agent_output/writer/
   ```

3. Try listing available files:
   ```bash
   python evaluate_repository_truthfulness.py --repo unknown_repo
   # Will show available files
   ```

### Too many components being evaluated

If you're still seeing "Found 37 writer output files", make sure you're using the repository filter:

```bash
# ❌ Wrong - loads all files
python -m backend.eval_truthfulness

# ✅ Right - loads only this repo
python -m backend.eval_truthfulness --repo testrepo
```

### Component not found in dependency graph

1. Check that navigator output files exist:
   ```bash
   ls -la data/intermediate/navigator_output/
   ```

2. Verify the repository name matches:
   - Navigator files: `ir_testrepo.json`, `dag_testrepo.json`
   - Writer files: `testrepo_writer_output.json`
   - Command: `--repo testrepo`

## Integration with Existing Pipeline

The new system is backward compatible - replace your evaluation call with:

```python
# Old way (not recommended)
results = old_evaluator.evaluate_all()

# New way (recommended)
evaluator = ComprehensiveTruthfulnessEvaluator(
    navigator_output_dir="...",
    writer_output_dir="..."
)
results = evaluator.evaluate_repository_writer_output("testrepo")
```

## Performance

- **Single repo evaluation**: 5-30 seconds (depends on docstring count and LLM mode)
- **Regex-only mode** (`--no-llm`): 1-5 seconds
- **With LLM enabled**: 5-30 seconds
- **Memory usage**: ~50-200 MB per repository

## Next Steps

1. **Verify repository name** matches file naming convention
2. **Run evaluation** for your repository
3. **Review the markdown report** for insights
4. **Check the JSON results** for detailed metrics
5. **Iterate** if needed (adjust docstring generation system)

---

For more information, see `docs/TRUTHFULNESS_EVALUATOR.md`
