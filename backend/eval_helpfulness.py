# eval_helpfulness.py
#
# Helpfulness evaluation for docstrings across all languages.
# Uses your existing LLM client (RemoteAPIClient / LocalLlamaClient)
# to score docstring quality on 3 aspects:
#   - Summary quality (1-5)
#   - Description quality (1-5)
#   - Parameter description quality (1-5)
#
# Works directly with your all_components dict from extractors.
#
# USAGE (CLI):
#   python eval_helpfulness.py path/to/file.java
#   python eval_helpfulness.py path/to/repo/ --max 10
#   python eval_helpfulness.py path/to/repo/ --save results/helpfulness.json
#
# USAGE (programmatic):
#   from eval_helpfulness import run_helpfulness_evaluation, print_helpfulness_results
#   results = run_helpfulness_evaluation(all_components)
#   print_helpfulness_results(results)

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from tabulate import tabulate

# Your existing LLM client — no new dependencies needed
from backend.utils.llm_client import get_llm_client, LLMRequest

from evaluator.helpfulness_summary import DocstringSummaryEvaluator
from evaluator.helpfulness_description import DocstringDescriptionEvaluator
from evaluator.helpfulness_parameters import DocstringParametersEvaluator


# ================================================================
# RESULT DATACLASS
# ================================================================

@dataclass
class HelpfulnessResult:
    """Stores the result of a single aspect evaluation."""
    component_id:   str
    component_name: str
    language:       str
    comp_type:      str
    aspect:         str    # "summary" | "description" | "parameters"
    score:          int    # 1-5
    suggestion:     str


# ================================================================
# CORE EVALUATION FUNCTION
# ================================================================

def run_helpfulness_evaluation(
    all_components: Dict,
    max_components: Optional[int] = None,
    skip_private:   bool = True,
) -> Dict[str, Any]:
    """
    Run helpfulness evaluation on all components using LLM-as-judge.

    Uses your existing LLM client (configured via config/llm.yaml).
    Evaluates 3 aspects for each component that has a docstring:
    - Summary: Does it add value beyond the signature?
    - Description: Does it explain motivation, usage, integration?
    - Parameters: Do param descriptions explain more than just types?

    Args:
        all_components: Dict mapping component_id -> CodeComponent
                        (output from your extractor pipeline)
        max_components: Limit evaluation to N components (useful for testing).
        skip_private: Skip private components (is_private=True).

    Returns:
        Dict with results by language, by aspect, overall stats,
        and per-component details.
    """
    # Get your existing LLM client — uses whatever is configured in llm.yaml
    llm = get_llm_client()

    evaluators = {
        "summary":     DocstringSummaryEvaluator(),
        "description": DocstringDescriptionEvaluator(),
        "parameters":  DocstringParametersEvaluator(),
    }

    results = {
        "by_language":          {},
        "by_aspect":            {},
        "by_type":              {},
        "overall":              {"total": 0, "scores": [], "average": 0.0},
        "components":           [],
        "skipped_no_docstring": 0,
        "skipped_private":      0,
        "errors":               [],
    }

    # Filter components
    components_to_eval = []
    for comp_id, component in all_components.items():
        docstring = getattr(component, "existing_docstring", None)
        if not docstring:
            results["skipped_no_docstring"] += 1
            continue

        if skip_private and getattr(component, "is_private", False):
            results["skipped_private"] += 1
            continue

        components_to_eval.append((comp_id, component))

    if max_components:
        components_to_eval = components_to_eval[:max_components]

    total = len(components_to_eval)
    print(f"\n📊 Evaluating {total} components with docstrings...")
    print(f"   Skipped {results['skipped_no_docstring']} (no docstring)")
    print(f"   Skipped {results['skipped_private']} (private)\n")

    all_results: List[HelpfulnessResult] = []

    for idx, (comp_id, component) in enumerate(components_to_eval):
        language    = getattr(component, "language", "unknown")
        comp_type   = component.type.value
        name        = getattr(component, "name", comp_id)
        docstring   = component.existing_docstring
        source_code = getattr(component, "source_code", "") or ""
        parameters  = getattr(component, "parameters", []) or []

        # Determine eval_type for prompt
        if comp_type == "class":
            eval_type = "class"
        elif comp_type in ("method", "constructor"):
            eval_type = "method"
        else:
            eval_type = "function"

        print(f"[{idx+1}/{total}] {language} {comp_type}: {name}")

        # Decide which aspects to evaluate
        aspects_to_run = ["summary"]

        desc_eval = DocstringDescriptionEvaluator()
        if desc_eval._extract_description(docstring):
            aspects_to_run.append("description")

        if parameters and len(parameters) > 0:
            aspects_to_run.append("parameters")

        # Evaluate each aspect
        for aspect in aspects_to_run:
            evaluator = evaluators[aspect]
            try:
                prompt = evaluator.get_evaluation_prompt(source_code, docstring, eval_type)

                if prompt.startswith("The docstring does not have"):
                    continue

                # Use generate_with_messages — works for both Local and Remote client
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are an expert code documentation quality evaluator. "
                            "Be precise and consistent in your scoring."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]

                response = llm.generate_with_messages(
                    agent_name="helpfulness_evaluator",
                    messages=messages,
                    temperature=0.1,
                    max_tokens=1024,
                )

                score, suggestion = evaluator.parse_llm_response(response.content)

                print(f"   {aspect}: {score}/5")

                all_results.append(HelpfulnessResult(
                    component_id=comp_id,
                    component_name=name,
                    language=language,
                    comp_type=comp_type,
                    aspect=aspect,
                    score=score,
                    suggestion=suggestion,
                ))

            except Exception as e:
                error_msg = f"Error evaluating {comp_id} [{aspect}]: {e}"
                print(f"   ⚠️  {error_msg}")
                results["errors"].append(error_msg)

    # ---- Aggregate ----
    for r in all_results:
        # Per component
        comp_entry = next(
            (c for c in results["components"] if c["id"] == r.component_id), None
        )
        if comp_entry is None:
            comp_entry = {
                "id":       r.component_id,
                "name":     r.component_name,
                "language": r.language,
                "type":     r.comp_type,
                "aspects":  {},
                "average":  0.0,
            }
            results["components"].append(comp_entry)

        comp_entry["aspects"][r.aspect] = {
            "score":      r.score,
            "suggestion": r.suggestion,
        }

        # By language
        if r.language not in results["by_language"]:
            results["by_language"][r.language] = {"scores": [], "average": 0.0, "total": 0}
        results["by_language"][r.language]["scores"].append(r.score)
        results["by_language"][r.language]["total"] += 1

        # By aspect
        if r.aspect not in results["by_aspect"]:
            results["by_aspect"][r.aspect] = {"scores": [], "average": 0.0, "total": 0}
        results["by_aspect"][r.aspect]["scores"].append(r.score)
        results["by_aspect"][r.aspect]["total"] += 1

        # By type
        if r.comp_type not in results["by_type"]:
            results["by_type"][r.comp_type] = {"scores": [], "average": 0.0, "total": 0}
        results["by_type"][r.comp_type]["scores"].append(r.score)
        results["by_type"][r.comp_type]["total"] += 1

        results["overall"]["scores"].append(r.score)
        results["overall"]["total"] += 1

    # Calculate averages
    for data in results["by_language"].values():
        if data["scores"]:
            data["average"] = round(sum(data["scores"]) / len(data["scores"]), 2)

    for data in results["by_aspect"].values():
        if data["scores"]:
            data["average"] = round(sum(data["scores"]) / len(data["scores"]), 2)

    for data in results["by_type"].values():
        if data["scores"]:
            data["average"] = round(sum(data["scores"]) / len(data["scores"]), 2)

    for comp in results["components"]:
        scores = [v["score"] for v in comp["aspects"].values()]
        comp["average"] = round(sum(scores) / len(scores), 2) if scores else 0.0

    all_scores = results["overall"]["scores"]
    results["overall"]["average"] = round(
        sum(all_scores) / len(all_scores), 2
    ) if all_scores else 0.0

    # Print LLM stats
    try:
        stats = llm.get_stats()
        print(f"\n📈 LLM Usage: {stats['total_requests']} requests, "
              f"{stats['total_tokens']} tokens, "
              f"cost=${stats.get('total_cost', 0):.4f}")
    except Exception:
        pass

    return results


# ================================================================
# PRINT RESULTS
# ================================================================

def _color_score(score: float, GREEN, YELLOW, RED, ENDC) -> str:
    if score >= 4.0:
        return f"{GREEN}{score}{ENDC}"
    elif score >= 2.5:
        return f"{YELLOW}{score}{ENDC}"
    else:
        return f"{RED}{score}{ENDC}"


def print_helpfulness_results(results: Dict[str, Any]) -> None:
    """Pretty print helpfulness evaluation results."""
    GREEN  = '\033[92m'
    RED    = '\033[91m'
    BLUE   = '\033[94m'
    YELLOW = '\033[93m'
    BOLD   = '\033[1m'
    ENDC   = '\033[0m'

    print(f"\n{BOLD}{'=' * 60}{ENDC}")
    print(f"{BOLD}  DOCSTRING HELPFULNESS EVALUATION (LLM-as-Judge){ENDC}")
    print(f"{BOLD}  Scale: 1 (Poor) → 5 (Excellent){ENDC}")
    print(f"{BOLD}{'=' * 60}{ENDC}")

    print(f"\n{BLUE}{BOLD}BY ASPECT:{ENDC}")
    aspect_table = []
    for aspect, data in sorted(results["by_aspect"].items()):
        aspect_table.append([aspect, data["total"],
            _color_score(data["average"], GREEN, YELLOW, RED, ENDC)])
    print(tabulate(aspect_table,
        headers=["Aspect", "Evaluated", "Avg Score (1-5)"], tablefmt="grid"))

    print(f"\n{BLUE}{BOLD}BY LANGUAGE:{ENDC}")
    lang_table = []
    for lang, data in sorted(results["by_language"].items()):
        lang_table.append([lang, data["total"],
            _color_score(data["average"], GREEN, YELLOW, RED, ENDC)])
    print(tabulate(lang_table,
        headers=["Language", "Evaluations", "Avg Score (1-5)"], tablefmt="grid"))

    print(f"\n{BLUE}{BOLD}BY COMPONENT TYPE:{ENDC}")
    type_table = []
    for comp_type, data in sorted(results["by_type"].items()):
        type_table.append([comp_type, data["total"],
            _color_score(data["average"], GREEN, YELLOW, RED, ENDC)])
    print(tabulate(type_table,
        headers=["Type", "Evaluations", "Avg Score (1-5)"], tablefmt="grid"))

    print(f"\n{BLUE}{BOLD}OVERALL:{ENDC}")
    overall = results["overall"]
    print(tabulate([
        ["Total Evaluations",     overall["total"]],
        ["Overall Avg Score",     _color_score(overall["average"], GREEN, YELLOW, RED, ENDC)],
        ["Skipped (no docstring)", results["skipped_no_docstring"]],
        ["Skipped (private)",     results["skipped_private"]],
        ["Errors",                len(results["errors"])],
    ], tablefmt="simple"))

    if results["components"]:
        print(f"\n{BLUE}{BOLD}COMPONENTS NEEDING MOST IMPROVEMENT (bottom 10):{ENDC}")
        sorted_comps = sorted(results["components"], key=lambda x: x["average"])[:10]
        bottom_table = []
        for comp in sorted_comps:
            aspect_scores = " | ".join(
                f"{a}:{v['score']}" for a, v in comp["aspects"].items()
            )
            bottom_table.append([
                comp["name"], comp["language"], comp["type"],
                _color_score(comp["average"], GREEN, YELLOW, RED, ENDC),
                aspect_scores,
            ])
        print(tabulate(bottom_table,
            headers=["Name", "Language", "Type", "Avg", "Aspect Scores"],
            tablefmt="grid"))

    print(f"\n{BLUE}{BOLD}TOP IMPROVEMENT SUGGESTIONS:{ENDC}")
    suggestions = []
    for comp in results["components"]:
        for aspect, data in comp["aspects"].items():
            if data["score"] <= 2 and data["suggestion"]:
                suggestions.append({
                    "component":  comp["name"],
                    "aspect":     aspect,
                    "score":      data["score"],
                    "suggestion": data["suggestion"][:120] + "..."
                                  if len(data["suggestion"]) > 120
                                  else data["suggestion"],
                })

    if suggestions:
        suggestions.sort(key=lambda x: x["score"])
        for s in suggestions[:5]:
            print(f"\n  {RED}[{s['component']} - {s['aspect']} score:{s['score']}]{ENDC}")
            print(f"  → {s['suggestion']}")
    else:
        print(f"  {GREEN}All components scored above 2/5!{ENDC}")


def save_results(results: Dict[str, Any], output_path: str) -> None:
    """Save results to JSON file."""
    serializable = {
        "by_language":          results["by_language"],
        "by_aspect":            results["by_aspect"],
        "by_type":              results["by_type"],
        "overall":              {k: v for k, v in results["overall"].items() if k != "scores"},
        "components":           results["components"],
        "skipped_no_docstring": results["skipped_no_docstring"],
        "skipped_private":      results["skipped_private"],
        "errors":               results["errors"],
    }
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)
    print(f"\n💾 Results saved to: {output_path}")


# ================================================================
# CLI ENTRY POINT
# ================================================================

def main():
    parser = argparse.ArgumentParser(
        description="LLM-based docstring helpfulness evaluator"
    )
    parser.add_argument("path", help="File or directory to evaluate")
    parser.add_argument("--max", type=int, default=None,
                        help="Max components to evaluate (for testing)")
    parser.add_argument("--save", default=None,
                        help="Path to save JSON results")
    parser.add_argument("--include-private", action="store_true",
                        help="Include private components")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()
    target = Path(args.path)

    if not target.exists():
        print(f"❌ Path not found: {args.path}")
        sys.exit(1)

    # Extract components using your existing extractors
    from tree_sitter import Parser
    from tree_sitter_languages import get_language
    from navigator.languages.java.extractor import extract_components as java_extract
    from navigator.languages.javascript.extractor import extract_components as js_extract
    from navigator.languages.typescript.extractor import extract_components as ts_extract
    from navigator.languages.python.extractor import extract_components as python_extract

    EXTRACTORS = {
        "java": java_extract, "javascript": js_extract,
        "typescript": ts_extract, "python": python_extract,
    }
    EXT_MAP = {".java": "java", ".js": "javascript", ".ts": "typescript", ".py": "python"}

    def process_file(file_path: str) -> dict:
        ext = Path(file_path).suffix.lower()
        language = EXT_MAP.get(ext)
        if not language:
            return {}
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        if not source.strip():
            return {}
        if args.verbose:
            print(f"📄 [{language}]: {Path(file_path).name}")
        try:
            p = Parser()
            p.set_language(get_language(language))
            tree = p.parse(bytes(source, "utf8"))
            return EXTRACTORS[language](tree, source, file_path, Path(file_path).stem)
        except Exception as e:
            print(f"⚠️  Extraction error {file_path}: {e}")
            return {}

    all_components = {}
    if target.is_file():
        all_components = process_file(str(target))
    elif target.is_dir():
        for fp in sorted(target.rglob("*")):
            if fp.suffix.lower() in EXT_MAP:
                all_components.update(process_file(str(fp)))

    if not all_components:
        print("⚠️  No components extracted.")
        sys.exit(0)

    print(f"✓ Extracted {len(all_components)} components")

    results = run_helpfulness_evaluation(
        all_components,
        max_components=args.max,
        skip_private=not args.include_private,
    )

    print_helpfulness_results(results)

    if args.save:
        save_results(results, args.save)


if __name__ == "__main__":
    main()