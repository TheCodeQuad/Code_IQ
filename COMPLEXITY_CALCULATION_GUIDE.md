# Complexity Calculation - Hybrid Approach

## Overview

The Reader Agent now uses a **hybrid approach** for calculating code complexity, combining three complementary methods for maximum precision:

1. **Cognitive Complexity** (50% weight) - How hard is it for humans to understand?
2. **Nesting Depth Analysis** (40% weight) - How deeply nested is the code?
3. **Coupling Metrics** (10% weight) - How many dependencies does it have?

---

## Method 1: Cognitive Complexity (0-100 scale)

Focuses on **readability and mental effort** required to understand code.

### Scoring Factors:

| Factor | Points | Condition |
|--------|--------|-----------|
| Base | cyclomatic × 1.5 | From Navigator |
| Branches | +2 per branch | `num_branches` |
| Loops | +2 | If `has_loop = true` |
| Loops + Branches | +5 bonus | Interaction penalty |
| Try/Except | +3 | Error handling |
| Async Operations | +4 | `has_async_operations` |
| Infinite Loops | +8 | `has_infinite_loop` (anti-pattern) |

### Example:
```python
def process_data(items):           # cyclomatic = 2 → 3 points
    for item in items:             # loop → +2
        if condition:              # branch → +2
            try:
                process(item)      # try/except → +3
            except Exception:
                log(e)
        
# Total: 3 + 2 + 2 + 3 = 10 points → simple
```

---

## Method 2: Nesting Depth Analysis (0-10+ scale)

Counts **maximum indentation level** from source code (language-agnostic).

### Scoring:

- **Depth 0-3**: Normal (score = depth)
- **Depth 4-6**: Deep nesting (above IDE recommendation)
- **Depth 7+**: Extreme (compressed with √)

### Example:
```python
def foo():                    # depth 1
    if x:                     # depth 2
        for item in items:    # depth 3
            if check(item):   # depth 4 ← MAX DEPTH
                try:
                    process() # depth 5
                except:
                    pass
```

**Max nesting depth = 4** → score = 4 × 2.0 = **8 points**

### Penalization for Deep Nesting:
```python
if max_depth > 6:
    # Apply non-linear penalty
    score = (max_depth ** 0.7) * 2
    # depth 7 → 7^0.7 × 2 ≈ 8.4
    # depth 10 → 10^0.7 × 2 ≈ 11.8
```

---

## Method 3: Coupling Score (0-20 scale)

Measures **dependencies and parameters** (how much external context is needed).

### Scoring:

```python
score = (
    min(dependencies, 10) × 1.2 +  # External deps (80% of score)
    min(params, 8) × 0.8            # Parameters (20% of score)
)
```

### Example:
- 3 dependencies → 3 × 1.2 = 3.6
- 5 parameters → 5 × 0.8 = 4.0
- **Total: 7.6 points**

---

## Hybrid Calculation

### Formula:
```
total_score = (
    cognitive_score × 0.5 +      # 50% weight (readability)
    max_nesting × 2.0 +          # 40% weight (anti-pattern detection)
    coupling_score × 0.3         # 10% weight (dependencies)
)
```

### Example Calculation:

**Component:** A function with:
- Cyclomatic complexity: 3
- 4 branches, no loops, no try/except
- Max nesting depth: 4
- 2 dependencies, 5 parameters

**Step 1: Cognitive Complexity**
- Base: 3 × 1.5 = 4.5
- Branches: 4 × 2 = 8
- Subtotal: 12.5

**Step 2: Nesting Depth**
- Max depth: 4
- Score: 4 (direct value, no compression)

**Step 3: Coupling**
- Dependencies: min(2, 10) × 1.2 = 2.4
- Parameters: min(5, 8) × 0.8 = 4.0
- Subtotal: 6.4

**Step 4: Weighted Sum**
```
total = (12.5 × 0.5) + (4 × 2.0) + (6.4 × 0.3)
      = 6.25 + 8.0 + 1.92
      = 16.17
```

**Result:** Score 16.17 → **COMPLEX** (> 15)

---

## Classification Thresholds

| Score Range | Category | Meaning |
|------------|----------|---------|
| 0-5 | **SIMPLE** | Easy to understand, minimal context needed |
| 6-15 | **MODERATE** | Reasonable complexity, some context helpful |
| 16+ | **COMPLEX** | Difficult to understand, comprehensive docs needed |

---

## Language Agnosticism

✅ **No language-specific parsing**
- Uses Navigator's pre-extracted metadata
- Indentation-based nesting detection works for Python, JS, Go, etc.
- Control flow flags (loops, branches, async) language-neutral

✅ **Works with any language Navigator supports**
- Python, JavaScript, Go, Java, etc.
- Uses CodeComponent abstraction

---

## When Complexity Matters

The Reader Agent uses complexity levels to determine documentation depth:

| Complexity | Documentation Needs | Context Search |
|-----------|-------------------|-----------------|
| **SIMPLE** | Basic description only | Minimal (internal) |
| **MODERATE** | Full description + usage | Standard context search |
| **COMPLEX** | Extended docs + examples | Deep dependency search |

---

## Debugging Complexity Scores

Check the Reader Agent XML output:
```xml
<COMPLEXITY>simple|moderate|complex</COMPLEXITY>
```

Saved to: `data/intermediate/agent_output/reader/{component_id}_reader_xml_output.xml`

Each component's detailed complexity breakdown is logged during analysis.

---

## Implementation Details

**File:** `backend/agents/reader_agent.py`

**Methods:**
- `_calculate_complexity_level()` - Main entry point, orchestrates hybrid calculation
- `_calculate_cognitive_complexity()` - Method 1: Cognitive score
- `_extract_max_nesting_depth()` - Method 2: Nesting depth
- `_calculate_coupling_score()` - Method 3: Coupling score

---

## Future Improvements

Potential enhancements to complexity calculation:

1. **Halstead Metrics** - Count distinct operators/operands for more granular scoring
2. **Comment-to-Code Ratio** - Penalize undocumented complex code
3. **Change Frequency** - Higher churn = likely complex
4. **NPath Complexity** - Count execution paths instead of just branches
5. **Maintainability Index** - Combined metric for overall health
