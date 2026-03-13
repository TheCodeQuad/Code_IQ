"""
JavaScript Docstring Quality Validator

Feeds CodeSearchNet JavaScript samples through the Writer agent (standalone,
no Reader/Searcher context) and compares the generated docstring against the
original human-written comment.

Outputs:
  1. A side-by-side JSONL file with original + generated for each sample
  2. A summary report printed to console with simple quality metrics

Usage:
    python validate_js_docstrings.py [max_samples]

Examples:
    python validate_js_docstrings.py 5   # Quick smoke-test
    python validate_js_docstrings.py 20  # Moderate run
"""

import sys
import json
import re
import time
import hashlib
import textwrap
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# ---------------------------------------------------------------------------
# Project root setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Ensure working directory is the project root so config/llm.yaml is found
import os
os.chdir(project_root)

from backend.agents.writer_agent import WriterAgent
from backend.agents.base_agent import AgentContext
from backend.models.code_component import (
    CodeComponent, ComponentType, Location, Parameter,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
INPUT_FILE = Path(__file__).parent / "data" / "validation" / "codesearchnet" / "javascript_code_comments.jsonl"
OUTPUT_DIR = Path(__file__).parent / "data" / "validation" / "codesearchnet"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_id(name: str, code: str) -> str:
    """Deterministic short ID from function name + code hash."""
    h = hashlib.md5(code.encode()).hexdigest()[:8]
    return f"{name}_{h}"


def _extract_params_from_js(code: str) -> List[Parameter]:
    """Best-effort parameter extraction from a JS function signature."""
    # Match: function name(a, b, c) or (a, b) =>
    m = re.search(r'(?:function\s*\w*\s*|)\(([^)]*)\)', code)
    if not m:
        return []
    raw = m.group(1).strip()
    if not raw:
        return []
    params = []
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        # Handle default values: x = 10
        if '=' in part:
            name, default = part.split('=', 1)
            params.append(Parameter(name=name.strip(), default_value=default.strip()))
        else:
            params.append(Parameter(name=part))
    return params


def _detect_component_type(code: str, func_name: str) -> ComponentType:
    """Heuristic to choose the right ComponentType."""
    if re.search(r'\bmodule\.exports\b|\bexports\.', code):
        return ComponentType.FUNCTION
    if func_name and func_name[0].isupper():
        # Constructors are typically PascalCase in JS
        if re.search(r'\bthis\.\w+\s*=', code):
            return ComponentType.CONSTRUCTOR
    if re.search(r'\.prototype\.', code):
        return ComponentType.METHOD
    return ComponentType.FUNCTION


def _extract_signature(code: str) -> str:
    """Extract the first line / signature from JS code."""
    for line in code.splitlines():
        line = line.strip()
        if line and not line.startswith('//') and not line.startswith('/*'):
            return line
    return code.splitlines()[0] if code else ""


def _extract_docstring_content(raw_response: str) -> str:
    """Pull text from between <DOCSTRING> tags, or return raw if missing."""
    m = re.search(r'<DOCSTRING>(.*?)</DOCSTRING>', raw_response, re.DOTALL)
    if m:
        return m.group(1).strip()
    return raw_response.strip()


def _has_throws_section(text: str) -> bool:
    return bool(re.search(r'@throws\b', text, re.IGNORECASE))


def _has_literal_throw(code: str) -> bool:
    return bool(re.search(r'\bthrow\s+', code))


def _simple_bleu_1gram(reference: str, hypothesis: str) -> float:
    """Unigram precision (very rough BLEU-1 approximation)."""
    ref_tokens = set(reference.lower().split())
    hyp_tokens = hypothesis.lower().split()
    if not hyp_tokens:
        return 0.0
    matches = sum(1 for t in hyp_tokens if t in ref_tokens)
    return matches / len(hyp_tokens)


def _word_overlap(a: str, b: str) -> float:
    """Jaccard similarity on word sets."""
    sa = set(a.lower().split())
    sb = set(b.lower().split())
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


# ---------------------------------------------------------------------------
# Core: build CodeComponent + run writer
# ---------------------------------------------------------------------------

def build_component(sample: Dict[str, Any]) -> CodeComponent:
    """Convert a JSONL sample into a CodeComponent for the writer."""
    code = sample["code"]
    func_name = sample.get("function_name", "unknown")
    repo = sample.get("repo", "unknown")

    params = _extract_params_from_js(code)
    comp_type = _detect_component_type(code, func_name)
    sig = _extract_signature(code)
    loc = Location(file_path=f"{repo}/{func_name}.js", start_line=1,
                   end_line=code.count('\n') + 1)

    return CodeComponent(
        id=_make_id(func_name, code),
        name=func_name,
        type=comp_type,
        location=loc,
        source_code=code,
        signature=sig,
        parameters=params,
        language="javascript",
        is_async=bool(re.search(r'\basync\b', code)),
        lines_of_code=code.count('\n') + 1,
    )


def run_writer_on_sample(writer: WriterAgent, sample: Dict[str, Any]) -> Dict[str, Any]:
    """Run the writer agent on a single sample and return comparison data."""
    component = build_component(sample)
    context = AgentContext(component=component)

    t0 = time.time()
    result = writer.process(context)
    elapsed = time.time() - t0

    original_comment = sample.get("comment", "")
    raw_generated = result.output.docstring if result.output else ""
    generated = _extract_docstring_content(raw_generated)

    # --- Quality signals ---
    has_throw_in_code = _has_literal_throw(sample["code"])
    gen_has_throws = _has_throws_section(generated)
    throws_correct = (gen_has_throws == has_throw_in_code)

    overlap = _word_overlap(original_comment, generated)
    bleu1 = _simple_bleu_1gram(original_comment, generated)

    # Check for generic opener
    generic_opener = bool(re.match(
        r'^(This function|A function|Helper|Used to)\b',
        generated, re.IGNORECASE
    ))

    return {
        "repo": sample.get("repo", ""),
        "function_name": sample.get("function_name", ""),
        "component_type": component.type.value,
        "original_comment": original_comment,
        "generated_docstring": generated,
        "raw_llm_response": raw_generated,
        "success": result.is_success(),
        "elapsed_sec": round(elapsed, 2),
        "metrics": {
            "word_overlap": round(overlap, 3),
            "bleu1": round(bleu1, 3),
            "throws_in_code": has_throw_in_code,
            "throws_in_doc": gen_has_throws,
            "throws_correct": throws_correct,
            "generic_opener": generic_opener,
            "generated_lines": len(generated.splitlines()),
        }
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(results: List[Dict[str, Any]]):
    """Print a readable summary report."""
    total = len(results)
    if total == 0:
        print("No results to report.")
        return

    successes = sum(1 for r in results if r["success"])
    throws_correct = sum(1 for r in results if r["metrics"]["throws_correct"])
    throws_hallucinated = sum(
        1 for r in results
        if r["metrics"]["throws_in_doc"] and not r["metrics"]["throws_in_code"]
    )
    generic_openers = sum(1 for r in results if r["metrics"]["generic_opener"])
    avg_overlap = sum(r["metrics"]["word_overlap"] for r in results) / total
    avg_bleu1 = sum(r["metrics"]["bleu1"] for r in results) / total
    avg_lines = sum(r["metrics"]["generated_lines"] for r in results) / total
    avg_time = sum(r["elapsed_sec"] for r in results) / total

    print("\n" + "=" * 80)
    print("  JAVASCRIPT DOCSTRING QUALITY REPORT")
    print("=" * 80)
    print(f"  Samples processed     : {total}")
    print(f"  Writer success rate   : {successes}/{total} ({100*successes/total:.0f}%)")
    print(f"  Avg generation time   : {avg_time:.1f}s")
    print()
    print("  --- Hallucination Metrics ---")
    print(f"  @throws correctness   : {throws_correct}/{total} ({100*throws_correct/total:.0f}%)")
    print(f"  @throws hallucinated  : {throws_hallucinated}/{total}"
          f"  ← should be 0")
    print(f"  Generic opener used   : {generic_openers}/{total}"
          f"  ← should be 0")
    print()
    print("  --- Similarity to Original ---")
    print(f"  Avg word overlap      : {avg_overlap:.3f}")
    print(f"  Avg BLEU-1 (unigram)  : {avg_bleu1:.3f}")
    print(f"  Avg generated lines   : {avg_lines:.1f}")
    print("=" * 80)

    # Show worst @throws hallucinations
    hallucinations = [r for r in results
                      if r["metrics"]["throws_in_doc"] and not r["metrics"]["throws_in_code"]]
    if hallucinations:
        print("\n⚠  HALLUCINATED @throws (generated @throws with no throw in code):")
        for h in hallucinations[:5]:
            print(f"  • {h['repo']}/{h['function_name']}")
            print(f"    Generated: {h['generated_docstring'][:120]}...")
            print()

    # Show a few side-by-side samples
    print("\n" + "-" * 80)
    print("  SAMPLE COMPARISONS (first 5)")
    print("-" * 80)
    for r in results[:5]:
        print(f"\n  Function: {r['function_name']}  ({r['repo']})")
        print(f"  Type: {r['component_type']}  |  Time: {r['elapsed_sec']}s")
        print(f"  Overlap: {r['metrics']['word_overlap']:.2f}  |  BLEU-1: {r['metrics']['bleu1']:.2f}")
        print()
        print("  ORIGINAL:")
        for line in r["original_comment"].splitlines()[:6]:
            print(f"    {line}")
        print()
        print("  GENERATED:")
        for line in r["generated_docstring"].splitlines()[:8]:
            print(f"    {line}")
        print("  " + "~" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    max_samples = 10
    if len(sys.argv) > 1:
        try:
            max_samples = int(sys.argv[1])
        except ValueError:
            print(f"Invalid max_samples: {sys.argv[1]}")
            sys.exit(1)

    if not INPUT_FILE.exists():
        print(f"❌ Input file not found: {INPUT_FILE}")
        print("   Run JS_extract.py first to generate the JSONL.")
        sys.exit(1)

    # Load samples
    samples = []
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if len(samples) >= max_samples:
                break
            samples.append(json.loads(line))

    print(f"Loaded {len(samples)} JavaScript samples from {INPUT_FILE.name}")
    print(f"Initializing WriterAgent...\n")

    writer = WriterAgent()

    results = []
    for i, sample in enumerate(samples, 1):
        fname = sample.get("function_name", "?")
        print(f"[{i}/{len(samples)}] Processing: {fname} ...", end=" ", flush=True)
        try:
            r = run_writer_on_sample(writer, sample)
            results.append(r)
            status = "✓" if r["success"] else "✗"
            print(f"{status}  ({r['elapsed_sec']}s)")
        except Exception as e:
            print(f"✗  ERROR: {e}")
            results.append({
                "repo": sample.get("repo", ""),
                "function_name": fname,
                "component_type": "unknown",
                "original_comment": sample.get("comment", ""),
                "generated_docstring": "",
                "raw_llm_response": "",
                "success": False,
                "elapsed_sec": 0,
                "metrics": {
                    "word_overlap": 0, "bleu1": 0,
                    "throws_in_code": False, "throws_in_doc": False,
                    "throws_correct": True, "generic_opener": False,
                    "generated_lines": 0,
                },
            })

    # Save full results
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = OUTPUT_DIR / f"js_docstring_comparison_{len(results)}_{ts}.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n💾 Full results saved to: {out_file}")

    # Print report
    print_report(results)


if __name__ == "__main__":
    main()
