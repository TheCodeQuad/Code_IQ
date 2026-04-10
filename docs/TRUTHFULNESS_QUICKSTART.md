# Quick Start: Multi-System Truthfulness Evaluation

## 🚀 Run Evaluation (Default Settings)

```bash
python -m backend.eval_truthfulness_multi_system
```

## 📋 What You Need

1. **Input File**: `data/validation/completeness_evaluation_cleaned.json`
   - Contains docstrings from 5 systems
   - See `data/validation/sample_completeness_evaluation_cleaned.json` for format

2. **Navigator Output**: `data/intermediate/navigator_output/`
   - Repository dependency graph
   - Run navigator first if missing: `python -m backend.navigator.scanner`

3. **Local Model**: `models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf`
   - Already configured to use your local model
   - No API keys needed!

## 📊 Output Files

Results saved to `data/validation/truthfulness/`:

- **docstring_truthfulness_evaluation.json**: Detailed results
- **docstring_truthfulness_report.md**: Comparative analysis with rankings

## ⚡ Command Options

```bash
# Custom paths
python -m backend.eval_truthfulness_multi_system \
    --input path/to/docstrings.json \
    --navigator-dir path/to/navigator \
    --output-dir path/to/results

# Fast mode (regex instead of LLM)
python -m backend.eval_truthfulness_multi_system --no-llm
```

## 📈 Key Metrics

- **Existence Ratio**: % of mentioned components that exist (higher = better)
- **Hallucination Rate**: % of fake components mentioned (lower = better)
- **Cross-File References**: Components correctly referenced from other files

## 🎯 Good Scores

- ✅ Existence Ratio > 80%
- ✅ Hallucination Rate < 20%
- ✅ High cross-file references (shows contextual awareness)

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| Model not found | Check `models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf` exists |
| Input file not found | Create/specify `completeness_evaluation_cleaned.json` |
| No navigator data | Run: `python -m backend.navigator.scanner` |
| Too slow | Use `--no-llm` flag |

## 📚 Full Documentation

See [TRUTHFULNESS_MULTI_SYSTEM.md](TRUTHFULNESS_MULTI_SYSTEM.md) for complete guide.

## 🆚 System Comparison

The report ranks all 5 systems by:
1. Best existence ratio (most accurate references)
2. Lowest hallucination rate (fewest fake components)
3. Most cross-file references (best contextual understanding)

---

**Time to results**: ~10-30 minutes for 1000+ docstrings (with LLM)
