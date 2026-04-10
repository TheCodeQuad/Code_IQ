# Comprehensive Docstring Truthfulness Evaluator

## Overview

The **Comprehensive Docstring Truthfulness Evaluator** is a production-quality system for evaluating whether code components mentioned in generated docstrings actually exist in the repository and whether they are contextually correct.

### Core Evaluation Questions

- **When a docstring mentions functions/classes, are those actually real?**
- **Are they valid and exist in the context of the repository?**
- **Are cross-file dependencies correctly identified?**

---

## Architecture

### Key Components

#### 1. **ComprehensiveTruthfulnessEvaluator** (`backend/evaluator/truthfulness_comprehensive.py`)

Main evaluator class with full implementation of the truthfulness logic.

**Key Features:**
- LLM-based semantic component extraction (Gemini or local llama.cpp)
- Regex fallback pattern matching for component extraction
- Per-repository dependency graph caching
- Component existence validation against dependency graphs
- Cross-file reference detection
- Hallucination detection and reporting
- Comprehensive statistics and aggregation
- Markdown and JSON report generation

**Main Methods:**
```python
# Single docstring evaluation
result = evaluator.evaluate_docstring(
    component_id="module.ClassName",
    docstring="Documentation text...",
    file_path="src/module.py",
    repository_name="my_repo",
    language="python"
)

# Batch evaluation
results = evaluator.evaluate_batch(components_list)

# Generate summary statistics
summary = evaluator.generate_summary_report(results)

# Save results
evaluator.save_results_json(results, output_file)
evaluator.generate_markdown_report(results, output_file)
```

#### 2. **MultiSystemTruthfulnessEvaluator** (`backend/eval_truthfulness_multi_system.py`)

Orchestrator for evaluating docstrings from multiple systems simultaneously.

**Features:**
- Load docstrings from multiple systems in various formats
- Per-system comparative analysis
- Cross-system rankings and comparisons
- Language and repository breakdowns
- Detailed hallucination analysis
- Comprehensive comparative markdown reports

**Usage:**
```python
evaluator = MultiSystemTruthfulnessEvaluator(
    input_file="data/evaluation.json",
    navigator_output_dir="data/intermediate/navigator_output",
    use_llm=True,
    llm_mode="llama_cpp"
)

all_results = evaluator.evaluate_all_systems()
evaluator.generate_comparative_report(all_results, output_dir)
```

---

## Data Structures

### DocstringEvaluationResult

Represents the evaluation of a single docstring:

```python
@dataclass
class DocstringEvaluationResult:
    component_id: str              # Component identifier
    repository: str                # Repository name
    file_path: str                 # File path of component
    language: str                  # Programming language
    mentioned_components: List[ComponentMention]  # Extracted components
    total_mentions: int            # Total components mentioned
    existing_mentions: int         # Components that exist
    cross_file_mentions: int       # Cross-file references
    hallucination_rate: float      # Rate of hallucinations (0-1)
    existence_ratio: float         # Ratio of existing components (0-1)
```

### ComponentMention

Represents a single component mentioned in a docstring:

```python
@dataclass
class ComponentMention:
    name: str                      # Component name
    exists: bool                   # Whether it exists in repo
    is_cross_file: bool           # Cross-file reference
    component_type: Optional[str]  # Type (class, function, etc.)
    file_path: Optional[str]       # Where component is located
    repository: Optional[str]      # Repository containing component
```

### SystemEvaluationStats

Aggregate statistics across all docstrings in a system:

```python
@dataclass
class SystemEvaluationStats:
    system_name: str
    total_docstrings_analyzed: int
    total_components_mentioned: int
    existing_components: int
    cross_file_mentions: int
    avg_existence_ratio: float
    avg_hallucination_rate: float
    avg_mentions_per_doc: float
    by_language: Dict[str, Dict[str, Any]]
    by_repository: Dict[str, Dict[str, Any]]
    hallucinated_components: List[Tuple[str, str]]
```

---

## Metrics & Definitions

### **Existence Ratio**
```
existence_ratio = existing_components / total_components_mentioned
```
- **Measures**: Hallucination rate (how accurate the docstrings are)
- **Range**: 0-1 (0% to 100%)
- **Interpretation**: 
  - > 80%: Excellent, highly trustworthy
  - 60-80%: Good, generally reliable
  - < 60%: Poor, needs improvement

### **Hallucination Rate**
```
hallucination_rate = (total_mentions - existing_mentions) / total_mentions
```
- **Measures**: Percentage of mentioned components that don't actually exist
- **Range**: 0-1 (0% to 100%)
- **Interpretation**:
  - < 20%: Excellent, very few false positives
  - 20-40%: Acceptable
  - > 40%: Poor, many hallucinations

### **Cross-File Ratio**
```
cross_file_ratio = cross_file_mentions / existing_components
```
- **Measures**: Context awareness and understanding of codebase dependencies
- **Higher values**: System understands cross-file relationships

### **Average Mentions Per Docstring**
```
avg_mentions_per_doc = total_mentions / docstrings_analyzed
```
- **Measures**: Documentation richness and detail level
- **Higher values**: More comprehensive documentation

---

## Component Extraction Strategy

### LLM-Based Extraction (Primary)

When LLM is available, the system:

1. **Sends docstring to LLM** with prompt to extract custom code components
2. **Filters out common library names** (List, Dict, String, print, console, etc.)
3. **Returns structured list** of extracted component names

**Supported LLMs:**
- `gemini`: Google Gemini API (cloud-based)
- `llama_cpp`: Local Qwen2.5 Coder model (7B parameters, quantized)

### Regex-Based Fallback (Automatic)

If LLM is unavailable or fails, system uses regex patterns:

**Patterns Matched:**
- Backtick-wrapped identifiers: `` `ComponentName` ``
- Function calls: `function_name()`
- Method calls: `.method_name`
- CamelCase class names: `ClassName`
- Filters out 150+ common library/English words

---

## Component Validation

### Matching Strategy

For each extracted component, the system:

1. **Exact Match**: Component ID or name directly in dependency graph
2. **Case-Insensitive Match**: Name matches ignoring case
3. **Part-of-ID Match**: Component appears in full component ID

### Cross-File Detection

After finding a component:

1. **Normalize file paths** (handle Windows/Unix paths)
2. **Compare file paths**: Docstring file vs. component file
3. **Different files** → Mark as `is_cross_file=True`

---

## Dependency Graph Loading

### Supported Formats

The system automatically handles multiple navigator output formats:

```json
// IR Format (Intermediate Representation)
{
  "eval.User": {
    "id": "eval.User",
    "name": "User",
    "type": "class",
    "location": {
      "file_path": "/path/to/file.py",
      "start_line": 1,
      "end_line": 46
    },
    ...
  }
}

// DAG Format (Directed Acyclic Graph)
{
  "nodes": [
    {"id": "eval.User", "type": "class", ...}
  ]
}

// Component Map Format
{
  "components": {
    "eval.User": {...}
  }
}
```

### Caching Strategy

- **Per-Repository Cache**: Graphs cached by repository name
- **Lazy Loading**: Loaded on first access
- **Memory Efficient**: Significant speedup for multiple docstrings from same repo

---

## Usage Examples

### Basic Single Docstring Evaluation

```python
from backend.evaluator.truthfulness_comprehensive import ComprehensiveTruthfulnessEvaluator

# Initialize evaluator
evaluator = ComprehensiveTruthfulnessEvaluator(
    navigator_output_dir="data/intermediate/navigator_output",
    use_llm=True,
    llm_mode="llama_cpp"
)

# Evaluate a docstring
result = evaluator.evaluate_docstring(
    component_id="module.MyClass.method",
    docstring="This method uses the `User` class and calls `validate()`.",
    file_path="src/module.py",
    repository_name="my_repo",
    language="python"
)

# Access results
print(f"Existence Ratio: {result.existence_ratio:.1%}")
print(f"Hallucination Rate: {result.hallucination_rate:.1%}")
print(f"Cross-file References: {result.cross_file_mentions}")

for mention in result.mentioned_components:
    status = "✅" if mention.exists else "❌"
    print(f"  {mention.name}: {status}")
```

### Batch Evaluation with Summary

```python
# Prepare components list
components = [
    {
        "component_id": "auth.authenticate",
        "docstring": "Authenticate using `User.validate()`.",
        "file_path": "src/auth.py",
        "repository": "myapp",
        "language": "python"
    },
    # ... more components
]

# Batch evaluate
results = evaluator.evaluate_batch(components)

# Generate summary
summary = evaluator.generate_summary_report(results)

print(f"Total Docstrings: {summary.total_docstrings_analyzed}")
print(f"Average Existence: {summary.avg_existence_ratio:.1%}")
print(f"Average Hallucination: {summary.avg_hallucination_rate:.1%}")
```

### Multi-System Comparative Analysis

```python
from backend.eval_truthfulness_multi_system import MultiSystemTruthfulnessEvaluator

# Initialize with input containing multiple systems
evaluator = MultiSystemTruthfulnessEvaluator(
    input_file="data/multi_system_docstrings.json",
    navigator_output_dir="data/intermediate/navigator_output",
    use_llm=True
)

# Evaluate all systems
all_results = evaluator.evaluate_all_systems()

# Generate comparative report
evaluator.generate_comparative_report(all_results, Path("output/"))
```

### Input Format for Multi-System Evaluation

```json
{
  "system_1": [
    {
      "component_id": "UserAuth",
      "docstring": "Authenticates users with `User` class.",
      "file_path": "auth.py",
      "repository": "testrepo",
      "language": "python"
    }
  ],
  "system_2": [
    {
      "component_id": "UserAuth",
      "docstring": "User authentication module.",
      "file_path": "auth.py",
      "repository": "testrepo",
      "language": "python"
    }
  ]
}
```

---

## Output Files

### JSON Output (`truthfulness_detailed_results.json`)

Detailed per-docstring evaluation results:

```json
{
  "component_id": {
    "component_id": "...",
    "repository": "...",
    "file_path": "...",
    "language": "python",
    "total_mentions": 5,
    "existing_mentions": 4,
    "cross_file_mentions": 2,
    "hallucination_rate": 0.2,
    "existence_ratio": 0.8,
    "mentioned_components": [
      {
        "name": "User",
        "exists": true,
        "is_cross_file": false,
        "component_type": "class",
        "file_path": "model.py",
        "repository": "testrepo"
      }
    ]
  }
}
```

### Markdown Report (`truthfulness_report.md` / `truthfulness_comparative_report.md`)

Comprehensive human-readable report with:
- Executive summary with key metrics
- System comparison table (for multi-system)
- Rankings by various metrics
- Language-specific analysis
- Repository-specific analysis
- Hallucination analysis with examples
- Cross-file reference analysis
- Key insights and recommendations

---

## Command-Line Usage

### Single Repository Evaluation

```bash
python -m backend.evaluator.truthfulness_comprehensive \
  --input data/agent_output/writer_docs.json \
  --navigator-dir data/intermediate/navigator_output \
  --output-dir data/validation/truthfulness \
  --llm-mode llama_cpp
```

### Multi-System Comparative Evaluation

```bash
python -m backend.eval_truthfulness_multi_system \
  --input data/validation/completeness_evaluation_cleaned.json \
  --navigator-dir data/intermediate/navigator_output \
  --output-dir data/validation/truthfulness
```

### Without LLM (Regex-Only)

```bash
python -m backend.eval_truthfulness_multi_system \
  --input data/evaluation.json \
  --navigator-dir data/intermediate/navigator_output \
  --output-dir data/validation/truthfulness \
  --no-llm
```

---

## Configuration & Customization

### Environment Variables

```bash
# For Gemini API support
export GEMINI_API_KEY="your-api-key"

# For local model path
export LLAMA_MODEL_PATH="/path/to/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
```

### Tuning Parameters

**Component Database Caching:**
```python
evaluator = ComprehensiveTruthfulnessEvaluator(
    navigator_output_dir="...",
    cache_graphs=True,  # Enable caching (default)
    llm_mode="llama_cpp"
)
```

**Common Words Filtering:**
Edit the `common_words` set in `_extract_with_regex()` to add domain-specific terms.

---

## Testing

Run theintegration test suite:

```bash
python test_truthfulness_evaluator.py
```

Tests included:
1. Single docstring evaluation
2. Batch evaluation
3. Summary statistics generation
4. Multi-system comparative evaluation
5. Component extraction demonstration
6. Cross-file reference detection
7. Dependency graph loading

---

## Performance Characteristics

### Computational Aspects

- **Single Docstring**: ~100-500ms (depends on LLM availability)
- **Batch of 100**: ~10-50s (with LLM), ~1-5s (regex-only)
- **Dependency Graph Loading**: ~50-200ms per repository
- **Memory**: ~50-200MB for typical graphs

### Optimization Tips

1. **Enable Caching**: Always use `cache_graphs=True` for multi-repo evaluations
2. **Batch Processing**: Use `evaluate_batch()` instead of single calls
3. **Regex-Only Mode**: Use `--no-llm` for quick tests/demos
4. **Parallel Processing**: Distribute systems across cores manually if needed

---

## Error Handling & Robustness

### Automatic Fallbacks

- **LLM Unavailable** → Switches to regex extraction
- **Missing Model** → Uses regex-only mode with warning
- **Invalid Input** → Logs error, continues processing
- **Missing Component DB** → Returns empty graph with warning

### Input Validation

- Handles missing/invalid file paths
- Supports multiple docstring field names (docstring/generated_docstring)
- Flexible component ID formats
- Multiple repository naming conventions

---

## Best Practices

1. **Use LLM for Accuracy**: LLM-based extraction is more accurate than regex
2. **Enable Caching**: Significantly speeds up multi-docstring evaluation
3. **Validate Input Data**: Ensure component IDs and file paths are correct
4. **Review First Few Results**: Validate evaluation accuracy on sample docstrings
5. **Use Batch Mode**: More efficient than processing individually
6. **Store Detailed Results**: JSON output enables further analysis
7. **Review Reports**: Markdown reports provide actionable insights

---

## Troubleshooting

### No Components Extracted

- Check that docstring contains code references (backticks, function calls, method chains)
- Verify LLM is working (check logs for API errors)
- Try regex-only mode: `--no-llm`

### High Hallucination Rate

- Check that component naming is consistent
- Verify dependency graph is complete and accurate
- Consider that docstring may refer to external libraries

### Cross-file References Not Detected

- Ensure file paths in dependency graph and docstrings use consistent format
- Check path normalization (Windows vs. Unix)

### Memory Issues

- Process repositories one at a time
- Disable caching for very large graphs
- Use regex-only mode

---

## Integration with Existing Pipeline

The new system seamlessly replaces the existing truthfulness evaluation:

1. **Import new module**: `from backend.evaluator.truthfulness_comprehensive import ...`
2. **Use new API**: Create evaluator, call `evaluate_docstring()` or `evaluate_batch()`
3. **Backwards compatible**: Same input/output structures as original system
4. **Drop-in replacement**: Works with existing data formats and pipelines

---

## Future Enhancements

Potential improvements for future versions:

- [ ] Support for additional LLMs (Claude, GPT-4, etc.)
- [ ] Semantic similarity matching for approximate component matches
- [ ] Machine learning-based hallucination detection
- [ ] Type-aware component matching
- [ ] Incremental evaluation and caching
- [ ] Distributed evaluation across multiple machines
- [ ] Real-time streaming evaluation
- [ ] Integration with code quality tools

---

## License & Attribution

Part of the Code_IQ project for docstring quality evaluation.

For questions or issues, refer to the main project documentation.
