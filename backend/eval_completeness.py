# eval_completeness.py
# Multi-language completeness evaluator.
# Supports: Python, Java, JavaScript, TypeScript
# All languages use Tree-sitter based flow via MultiLangCompletenessEvaluator.
# NO ast module. NO special Python case. Same logic for everything.

import os
import sys
from pathlib import Path
from typing import Dict, Any
from tabulate import tabulate

from evaluator.multilang_completeness import MultiLangCompletenessEvaluator


def run_multilang_evaluation(all_components: Dict) -> Dict[str, Any]:
    """
    Run completeness evaluation over all CodeComponents across all languages.
    Works for Python, Java, JavaScript, TypeScript — same logic for all.

    Args:
        all_components: Dict mapping component_id -> CodeComponent

    Returns:
        Dict with results by language, by component type, and overall stats.
    """
    evaluator = MultiLangCompletenessEvaluator()

    results = {
        "by_language": {},
        "by_type": {},
        "overall": {"total": 0, "scores": [], "average": 0.0},
        "components": []
    }

    for comp_id, component in all_components.items():
        language = getattr(component, 'language', None)
        if not language:
            continue

        comp_type = component.type.value
        name      = getattr(component, 'name', comp_id)
        score     = evaluator.evaluate_component(component)

        results["components"].append({
            "id":                comp_id,
            "name":              name,
            "language":          language,
            "type":              comp_type,
            "score":             score,
            "element_scores":    dict(evaluator.element_scores),
            "element_required":  dict(evaluator.element_required),
            "required_sections": list(evaluator.required_sections),
            "has_docstring":     bool(getattr(component, 'existing_docstring', None))
        })

        # Aggregate by language
        if language not in results["by_language"]:
            results["by_language"][language] = {
                "scores": [], "total": 0, "average": 0.0,
                "documented": 0, "undocumented": 0
            }
        results["by_language"][language]["scores"].append(score)
        results["by_language"][language]["total"] += 1
        if getattr(component, 'existing_docstring', None):
            results["by_language"][language]["documented"] += 1
        else:
            results["by_language"][language]["undocumented"] += 1

        # Aggregate by component type
        if comp_type not in results["by_type"]:
            results["by_type"][comp_type] = {"scores": [], "total": 0, "average": 0.0}
        results["by_type"][comp_type]["scores"].append(score)
        results["by_type"][comp_type]["total"] += 1

        results["overall"]["scores"].append(score)
        results["overall"]["total"] += 1

    # Calculate averages
    for data in results["by_language"].values():
        if data["scores"]:
            data["average"] = round(sum(data["scores"]) / len(data["scores"]), 3)

    for data in results["by_type"].values():
        if data["scores"]:
            data["average"] = round(sum(data["scores"]) / len(data["scores"]), 3)

    all_scores = results["overall"]["scores"]
    results["overall"]["average"] = round(
        sum(all_scores) / len(all_scores), 3
    ) if all_scores else 0.0

    return results


def _color_score(score: float, GREEN, YELLOW, RED, ENDC) -> str:
    if score >= 0.8:
        return f"{GREEN}{score:.2f}{ENDC}"
    elif score >= 0.5:
        return f"{YELLOW}{score:.2f}{ENDC}"
    else:
        return f"{RED}{score:.2f}{ENDC}"


def print_multilang_results(results: Dict[str, Any]) -> None:
    """Pretty print multi-language evaluation results with colors."""
    GREEN  = '\033[92m'
    RED    = '\033[91m'
    BLUE   = '\033[94m'
    YELLOW = '\033[93m'
    BOLD   = '\033[1m'
    ENDC   = '\033[0m'

    print(f"\n{BOLD}{'=' * 60}{ENDC}")
    print(f"{BOLD}  MULTI-LANGUAGE COMPLETENESS EVALUATION{ENDC}")
    print(f"{BOLD}{'=' * 60}{ENDC}")

    # By Language
    print(f"\n{BLUE}{BOLD}BY LANGUAGE:{ENDC}")
    lang_table = []
    for lang, data in sorted(results["by_language"].items()):
        doc_pct = round(data["documented"] / max(1, data["total"]) * 100, 1)
        lang_table.append([
            lang,
            data["total"],
            data["documented"],
            data["undocumented"],
            f"{doc_pct}%",
            _color_score(data["average"], GREEN, YELLOW, RED, ENDC)
        ])
    print(tabulate(lang_table,
        headers=["Language", "Total", "Documented", "Undocumented", "Doc%", "Avg Score"],
        tablefmt="grid"))

    # By Component Type
    print(f"\n{BLUE}{BOLD}BY COMPONENT TYPE:{ENDC}")
    type_table = []
    for comp_type, data in sorted(results["by_type"].items()):
        type_table.append([
            comp_type,
            data["total"],
            _color_score(data["average"], GREEN, YELLOW, RED, ENDC)
        ])
    print(tabulate(type_table,
        headers=["Type", "Total", "Avg Score"],
        tablefmt="grid"))

    # Overall
    print(f"\n{BLUE}{BOLD}OVERALL:{ENDC}")
    overall = results["overall"]
    print(tabulate([
        ["Total Components", overall["total"]],
        ["Overall Avg Score", _color_score(overall["average"], GREEN, YELLOW, RED, ENDC)]
    ], tablefmt="simple"))

    # Bottom 10 worst
    print(f"\n{BLUE}{BOLD}LOWEST SCORING COMPONENTS (bottom 10):{ENDC}")
    sorted_comps = sorted(results["components"], key=lambda x: x["score"])[:10]
    bottom_table = []
    for comp in sorted_comps:
        bottom_table.append([
            comp["name"],
            comp["language"],
            comp["type"],
            _color_score(comp["score"], GREEN, YELLOW, RED, ENDC),
            "✓" if comp["has_docstring"] else f"{RED}✗ Missing{ENDC}"
        ])
    print(tabulate(bottom_table,
        headers=["Name", "Language", "Type", "Score", "Has Docstring"],
        tablefmt="grid"))